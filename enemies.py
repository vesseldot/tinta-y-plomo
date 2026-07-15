"""
enemies.py — Enemigos billboard animados por spritesheet, con IA a distancia,
barra de vida propia y pooling. Estilo Rubber Hose años 30.

DIFERENCIA CON LA VERSIÓN ANTERIOR (8 direcciones / melee)
----------------------------------------------------------
Los sprites nuevos son de UNA sola vista (frente), así que no hay lógica de
8 direcciones: el enemigo simplemente encara la cámara (billboard en C++) y
reproduce ANIMACIONES por fotograma (idle / disparo). El combate es A
DISTANCIA: al detectar al jugador se detiene, lo mira y le lanza balas
(EnemyBullet), en vez de golpearlo de cerca.

RECORTE DEL SPRITESHEET POR UV (sin cargar texturas nuevas)
-----------------------------------------------------------
Cada animación es un rectángulo de píxeles {x, y, fw, fh} + nº de frames
(ver ENEMY_TYPES en config.py). Mostrar el frame i = mover texture_offset y
fijar texture_scale al tamaño de una celda: la GPU nunca hace rebind de
textura y todos los enemigos del mismo tipo comparten material. Avanzar la
animación es cambiar un offset UV a `fps` cuadros por segundo, no a 60.

BILLBOARD EN C++
----------------
setBillboardAxis() (Panda3D) rota el nodo hacia la cámara durante el
recorrido de escena, en C++, con coste por enemigo casi nulo para Python.
"Axis" lo restringe al eje vertical: el sprite gira como un recorte de
cartón, justo el look retro. La barra de vida usa el mismo truco.

ACTIVACIÓN POR PISO
-------------------
Un enemigo arranca INACTIVO (`active=False`): no piensa, no se mueve, no
dispara. El WaveManager lo activa solo cuando el jugador llega físicamente
a su piso. Así los enemigos de pisos superiores permanecen quietos hasta
que subes.
"""

import random

from ursina import BoxCollider, Entity, Vec2, Vec3, color, raycast, time
from ursina.shaders import unlit_shader

from config import (ENEMY_FLASH_TIME, ENEMY_HB_HEIGHT, ENEMY_HB_WIDTH,
                    ENEMY_TYPES, floor_from_y)


def _frame_uv(tex_w, tex_h, x, y, fw, fh, i, pad=1.0):
    """(texture_offset, texture_scale) del frame i de una tira horizontal.

    Recorta 1 px por lado (pad) para que el filtrado bilineal no "sangre"
    el frame vecino. Las UV tienen origen ABAJO-izquierda; los píxeles,
    ARRIBA-izquierda: de ahí el 1 - (y+fh)/tex_h.
    """
    fx = x + i * fw
    offset = Vec2((fx + pad) / tex_w, 1.0 - (y + fh - pad) / tex_h)
    tscale = Vec2((fw - 2 * pad) / tex_w, (fh - 2 * pad) / tex_h)
    return offset, tscale


class Enemy(Entity):
    """Enemigo billboard animado. Nodo raíz = posición + collider + IA;
    el sprite y la barra de vida son hijos billboard.

    Separar raíz/sprite mantiene el collider alineado a los ejes del mundo
    (barato y estable para el raycast del arma del jugador) mientras solo el
    quad visual gira hacia la cámara.
    """

    def __init__(self, type_key, player, bullets):
        super().__init__()
        self.type_key = type_key
        self.cfg = ENEMY_TYPES[type_key]
        self.player = player
        self.bullets = bullets          # BulletManager compartido.
        self.is_boss = self.cfg.get('is_boss', False)

        # ---- Estado de combate (combat.py del jugador lee height/hp) ----
        self.max_hp = self.cfg['hp']
        self.hp = self.max_hp
        self.height = self.cfg['world_height']   # Para el cálculo de headshot.
        self.display_name = 'JEFE' if self.is_boss else type_key.upper()

        # ---- IA ----
        self.active = False             # Lo enciende el WaveManager por piso.
        self.floor_y = 0.0              # Y del suelo de su piso (no cae nunca).
        self._floor_index = 0           # Índice de piso (lo fija spawn()).
        self._fire_cd = random.uniform(0, self.cfg['fire_interval'])
        self._flash_timer = 0.0

        # ---- Callbacks (los instala el WaveManager / HUD) ----
        self.on_death = None            # WaveManager: contar bajas de la oleada.
        self.on_hp_changed = None       # HUD: barra superior del jefe.

        # ---- Collider de caja: barato y estable para el hitscan ----
        cw = self.cfg['col_w'] * self.height
        self.collider = BoxCollider(self, center=Vec3(0, self.height / 2, 0),
                                    size=Vec3(cw, self.height, cw * 0.6))

        # ---- Sprite billboard (recorte del spritesheet) ----
        self._pivot = Entity(parent=self, y=self.height / 2)
        self._pivot.setBillboardAxis()
        tw, th = self.cfg['tex']
        idle = self.cfg['anims']['idle']
        # El quad respeta la PROPORCIÓN de la celda (fw/fh) para no deformar
        # el dibujo; los personajes llenan casi toda su celda, así que el
        # alto del quad ≈ altura real del enemigo.
        aspect = idle['fw'] / idle['fh']
        # rotation_y=180 corrige el sentido del billboard de Panda (si tu
        # sprite se ve espejado, elimina esta rotación).
        self.sprite = Entity(parent=self._pivot, model='quad', rotation_y=180,
                             texture=self.cfg['sheet'],
                             scale=(self.height * aspect, self.height),
                             double_sided=True, shader=unlit_shader)

        # ---- Estado de animación ----
        self._anim = 'idle'
        self._frame = 0
        self._anim_timer = 0.0
        self._apply_frame()

        # ---- Barra de vida propia (billboard sobre la cabeza) ----
        self._hb_pivot = Entity(parent=self, y=self.height + 0.35)
        self._hb_pivot.setBillboardAxis()
        Entity(parent=self._hb_pivot, model='quad', color=color.dark_gray,
               scale=(ENEMY_HB_WIDTH + 0.04, ENEMY_HB_HEIGHT + 0.04), z=0.01)
        # Relleno con origin en el borde izquierdo: se "vacía" hacia la
        # derecha cambiando SOLO scale_x (un quad sin textura).
        self._hb_fill = Entity(parent=self._hb_pivot, model='quad',
                               origin=(-0.5, 0), color=color.lime,
                               position=Vec3(-ENEMY_HB_WIDTH / 2, 0, 0),
                               scale=(ENEMY_HB_WIDTH, ENEMY_HB_HEIGHT))
        self._hb_pivot.enabled = False   # Oculta hasta activarse.

    # ================================================== ciclo de vida ====
    def spawn(self, position, floor_y):
        """Coloca y reinicia el enemigo (lo llama el WaveManager)."""
        self.floor_y = floor_y
        self._floor_index = floor_from_y(floor_y)   # Su piso (para no disparar
                                                    # a otros pisos).
        self.position = Vec3(position.x, floor_y, position.z)
        self.hp = self.max_hp
        self.active = False
        self._fire_cd = random.uniform(0, self.cfg['fire_interval'])
        self._flash_timer = 0.0
        self._set_anim('idle')
        self.sprite.color = color.white
        self._refresh_health_bar()
        self.enabled = True
        self._hb_pivot.enabled = False   # Se enciende al activar.
        if self.on_hp_changed:           # Barra del jefe reaparece llena.
            self.on_hp_changed(self.hp, self.max_hp)

    def activate(self):
        """El jugador llegó a este piso: el enemigo empieza a pensar."""
        self.active = True
        self._hb_pivot.enabled = True

    # ========================================================== IA =======
    def update(self):
        if not self.active:              # Piso aún no alcanzado: congelado.
            return

        # Flash de daño (temporizador propio, sin Sequences).
        if self._flash_timer > 0:
            self._flash_timer -= time.dt
            if self._flash_timer <= 0:
                self.sprite.color = color.white

        # REGLA DE PISO: un enemigo solo persigue/dispara si el jugador está
        # en SU mismo piso. Así, aunque el hueco esté abierto, los de arriba
        # ignoran al jugador cuando este baja (y no disparan entre pisos).
        same_floor = floor_from_y(self.player.y) == self._floor_index
        self._fire_cd -= time.dt

        if not same_floor:
            self._set_anim('idle')               # Inofensivo en reposo.
            self._advance_animation()
            return

        to_player = self.player.world_position - self.world_position
        dist = to_player.length()

        if dist <= self.cfg['vision_range']:
            # -- En rango: detenerse, mirar y disparar SOLO si hay línea de
            #    visión (un muro/cobertura en medio lo protege al jugador). --
            if (self._anim != 'shoot' and self._fire_cd <= 0
                    and self._has_los()):
                self._set_anim('shoot')          # Arranca la ráfaga.
                self._fire_cd = self.cfg['fire_interval']
        else:
            # -- Fuera de rango: avanzar hacia el jugador SIN atravesar muros
            #    ni cobertura (un raycast corto por delante lo frena). --
            direction = Vec3(to_player.x, 0, to_player.z)
            if direction.length() > 0.01:
                direction = direction.normalized()
                step = self.cfg['speed'] * time.dt
                origin = self.world_position + Vec3(0, self.height * 0.5, 0)
                wall = raycast(origin, direction, distance=step + 0.7,
                               ignore=(self, self.player))
                if not wall.hit:
                    self.position += direction * step
                    self.y = self.floor_y            # Nunca cae ni sube.

        self._advance_animation()

    def _has_los(self):
        """Línea de visión al jugador: False si hay geometría (muro/cobertura)
        entre el enemigo y el jugador. Así la cobertura de verdad protege."""
        origin = self.world_position + Vec3(0, self.height * 0.6, 0)
        target = self.player.world_position + Vec3(0, 1.1, 0)
        d = target - origin
        dist = d.length()
        if dist < 0.1:
            return True
        hit = raycast(origin, d.normalized(), distance=dist - 0.4,
                      ignore=(self, self.player))
        return not hit.hit

    # ==================================================== animación =======
    def _set_anim(self, name):
        if self._anim == name:
            return
        self._anim = name
        self._frame = 0
        self._anim_timer = 0.0
        self._fired_this_shot = False
        self._apply_frame()

    def _advance_animation(self):
        anim = self.cfg['anims'][self._anim]
        self._anim_timer += time.dt
        step = 1.0 / anim['fps']
        while self._anim_timer >= step:
            self._anim_timer -= step
            self._frame += 1

            # Disparar en el frame del fogonazo (sincroniza bala y visual).
            if (self._anim == 'shoot'
                    and not getattr(self, '_fired_this_shot', False)
                    and self._frame >= self.cfg['fire_frame']):
                self._fire_bullet()
                self._fired_this_shot = True

            if self._frame >= anim['frames']:
                if self._anim == 'shoot':
                    self._set_anim('idle')       # Ráfaga terminada -> idle.
                    return
                self._frame = 0                  # idle: bucle.
            self._apply_frame()

    def _apply_frame(self):
        anim = self.cfg['anims'][self._anim]
        tw, th = self.cfg['tex']
        offset, tscale = _frame_uv(tw, th, anim['x'], anim['y'],
                                   anim['fw'], anim['fh'], self._frame)
        self.sprite.texture_offset = offset
        self.sprite.texture_scale = tscale

    # ==================================================== combate =========
    def _fire_bullet(self):
        """Lanza una EnemyBullet desde el pecho hacia el torso del jugador.

        El origen se adelanta 1.6 u hacia el jugador para que quede FUERA del
        propio collider del enemigo (si no, la colisión de la bala con muros
        la mataría al instante sobre el propio tirador)."""
        target = self.player.world_position + Vec3(0, 1.1, 0)
        chest = self.world_position + Vec3(0, self.height * 0.55, 0)
        flat = Vec3(target.x - chest.x, 0, target.z - chest.z)
        forward = flat.normalized() if flat.length() > 0.01 else Vec3(0, 0, 1)
        origin = chest + forward * 1.6
        tint = color.red if self.is_boss else color.orange
        self.bullets.spawn(origin, target, self.cfg['bullet_speed'],
                           self.cfg['bullet_damage'], self.player, tint)

    def take_damage(self, amount):
        self.hp -= amount
        self.sprite.color = color.red        # Feedback plano, coherente.
        self._flash_timer = ENEMY_FLASH_TIME
        self._refresh_health_bar()
        if not self.active:                  # Si te disparan, despierta.
            self.activate()
        if self.on_hp_changed:               # Barra del jefe en el HUD.
            self.on_hp_changed(max(0, self.hp), self.max_hp)
        if self.hp <= 0:
            self.die()

    def _refresh_health_bar(self):
        frac = max(0.0, min(1.0, self.hp / self.max_hp))
        self._hb_fill.scale_x = ENEMY_HB_WIDTH * frac
        # Verde -> amarillo -> rojo según la vida (feedback gratis).
        self._hb_fill.color = (color.lime if frac > 0.5 else
                               color.yellow if frac > 0.25 else color.red)

    def die(self):
        self.enabled = False                 # Desaparece (vuelve al pool).
        if self.on_death:
            self.on_death(self)              # WaveManager cuenta la baja.
