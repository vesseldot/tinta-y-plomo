"""
enemies.py — Enemigos como billboards 2D de 8 direcciones (estilo
"Mouse: P.I. for Hire" / DOOM clásico) con IA barata y pooling.

BILLBOARDING EFICIENTE
----------------------
La forma ingenua es hacer `sprite.look_at(camera)` en update() de cada
enemigo: eso corre en Python 60 veces por segundo por enemigo.

En su lugar usamos `setBillboardAxis()` de Panda3D (todo Entity de Ursina ES
un NodePath de Panda3D): el motor rota el nodo hacia la cámara EN C++ durante
el recorrido de escena, con coste por enemigo prácticamente nulo para Python.
"Axis" (y no "PointEye") lo restringe al eje vertical: el sprite gira como un
recorte de cartón, que es exactamente el look retro buscado.

8 DIRECCIONES SIN CAMBIAR DE TEXTURA
------------------------------------
Los 8 frames viven en UN atlas horizontal. Cambiar de frame = mover
`texture_offset` (una transformación UV), NO cambiar la textura: la GPU nunca
hace rebind de textura y todos los enemigos comparten el mismo material.
El índice de dirección se recalcula a 10 Hz (SPRITE_ANIM_INTERVAL) con fase
aleatoria por enemigo, para que los cálculos no caigan todos en el mismo frame.

ILUMINACIÓN
-----------
unlit_shader en el sprite: sin luces por pixel, el color del PNG llega crudo
a pantalla. Es a la vez la estética cel (sombreado plano "dibujado a mano")
y la opción más barata posible de shading.
"""

import math
import random

from ursina import (BoxCollider, Entity, Vec2, Vec3, camera, color, invoke,
                    time)
from ursina.shaders import unlit_shader

from pool import EntityPool
from config import (BOSS_HP, BOSS_NAME, ENEMY_ACTIVE_DIST,
                    ENEMY_ATTACK_INTERVAL, ENEMY_ATTACK_RANGE, ENEMY_COUNT,
                    ENEMY_DAMAGE, ENEMY_HP, ENEMY_RESPAWN_DELAY, ENEMY_SPEED,
                    ENEMY_STOP_DIST, MAP_SIZE, SPRITE_ANIM_INTERVAL)

DIRECTIONS = 8
FRAME_U = 1 / DIRECTIONS   # Ancho de un frame en coordenadas UV.


class Enemy(Entity):
    """Nodo raíz: posición, collider e IA. El sprite billboard es un hijo.

    Separar raíz/sprite tiene un porqué: el collider queda alineado a los
    ejes del mundo (barato y estable para el raycast del arma) mientras solo
    el quad visual rota hacia la cámara.
    """

    def __init__(self, player):
        super().__init__()
        self.player = player
        self.hp = ENEMY_HP
        self.max_hp = ENEMY_HP           # El jefe lo sobreescribe.
        self.height = 1.8                # Altura total: combat.py la usa para
                                         # el headshot (tercio superior). El
                                         # collider sigue siendo UNO solo.
        self.display_name = 'MATÓN'      # Nombre para la barra del HUD.
        self.on_death = None             # Callback que instala EnemyManager.
        self.on_hp_changed = None        # Callback del HUD (barra de jefe).
        self.facing_angle = 0.0          # Hacia dónde "camina" (grados).
        self._anim_timer = random.uniform(0, SPRITE_ANIM_INTERVAL)  # Fase aleatoria.
        self._flash_timer = 0.0
        self._attack_timer = 0.0

        # Collider de caja simple: los mesh colliders son MUCHO más caros
        # de testear y no aportan nada con esta estética.
        self.collider = BoxCollider(self, center=Vec3(0, 0.9, 0),
                                    size=Vec3(1.0, 1.8, 0.6))

        # Pivote con billboard en C++ (ver docstring del módulo).
        self._pivot = Entity(parent=self, y=0.9)
        self._pivot.setBillboardAxis()
        # rotation_y=180: el billboard de Panda apunta el eje +forward del
        # nodo hacia la cámara, dejando la cara del quad al revés; este giro
        # lo corrige. (Si tu sprite se ve espejado, elimina esta rotación.)
        self.sprite = Entity(parent=self._pivot, model='quad', rotation_y=180,
                             texture='assets/enemy_sheet.png',
                             scale=(1.5, 1.8), double_sided=True,
                             shader=unlit_shader)
        self.sprite.texture_scale = Vec2(FRAME_U, 1)   # Mostrar 1 frame del atlas.
        # Filtrado 'nearest': mantiene los bordes duros del dibujo (look
        # cartoon) y es el modo de muestreo más barato para la GPU.
        self.sprite.texture.filtering = None

    # ------------------------------------------------------------------ IA
    def update(self):
        dist = (self.player.position - self.position).length()

        # EARLY-OUT: enemigos lejanos no piensan, no animan, no se mueven.
        # Con 8 enemigos es poco, pero con 50 es la diferencia entre 60 y
        # 20 FPS en una CPU débil.
        if dist > ENEMY_ACTIVE_DIST:
            return

        # Persecución simple: sin pathfinding (A* en Python por frame es
        # veneno para gama baja). El mapa abierto lo tolera bien.
        if dist > ENEMY_STOP_DIST:
            direction = self.player.position - self.position
            direction.y = 0
            direction = direction.normalized()
            self.position += direction * ENEMY_SPEED * time.dt
            self.facing_angle = math.degrees(math.atan2(direction.x, direction.z))

        # Ataque cuerpo a cuerpo: proximidad + temporizador. Sin colliders
        # de ataque ni animaciones: una comparación y una resta por frame.
        if self._attack_timer > 0:
            self._attack_timer -= time.dt
        if dist <= ENEMY_ATTACK_RANGE and self._attack_timer <= 0:
            self._attack_timer = ENEMY_ATTACK_INTERVAL
            self.player.take_damage(ENEMY_DAMAGE)

        # Animación de dirección a 10 Hz, no a 60.
        self._anim_timer += time.dt
        if self._anim_timer >= SPRITE_ANIM_INTERVAL:
            self._anim_timer = 0.0
            self._update_direction_frame()

        # Flash de daño (temporizador propio: sin Sequences ni allocs).
        if self._flash_timer > 0:
            self._flash_timer -= time.dt
            if self._flash_timer <= 0:
                self.sprite.color = color.white

    def _update_direction_frame(self):
        """Elige el frame del atlas según el ángulo enemigo-cámara.

        Solo trigonometría 2D barata; nada de matrices. frame 0 = de frente.
        """
        to_cam = camera.world_position - self.world_position
        view_angle = math.degrees(math.atan2(to_cam.x, to_cam.z))
        rel = (self.facing_angle - view_angle + 180.0) % 360.0
        index = int((rel + 22.5) // 45) % DIRECTIONS
        # Cambiar de frame = mover UVs. Cero cambios de textura en GPU.
        self.sprite.texture_offset = Vec2(index * FRAME_U, 0)

    # -------------------------------------------------------------- combate
    def take_damage(self, amount):
        self.hp -= amount
        self.sprite.color = color.red    # Feedback plano, coherente con el estilo.
        self._flash_timer = 0.12
        if self.on_hp_changed:           # La barra del jefe se entera por evento.
            self.on_hp_changed(max(0, self.hp), self.max_hp)
        if self.hp <= 0:
            self.die()

    def die(self):
        # Opción elegida: volver al pool (desaparece y reaparece en otro
        # punto). Alternativa "cadáver inerte" si la prefieres: en vez de
        # release, poner self.sprite.rotation_z = 90, self.collider = None
        # y saltar el update con un flag — el sprite tumbado queda en el
        # piso sin costo de IA. Ambas respetan el presupuesto de gama baja.
        EntityPool.release(self)         # NO destroy(): vuelve al pool.
        if self.on_death:
            self.on_death(self)          # El manager programa el respawn.


class EnemyManager:
    """Administra el pool de enemigos y sus respawns.

    ENEMY_COUNT enemigos se crean UNA vez al cargar; morir = desactivarse,
    reaparecer = re-posicionarse y reactivarse. El número de objetos vivos
    es constante durante toda la partida -> GC tranquilo, cero stutter.
    """

    def __init__(self, player):
        self.pool = EntityPool(lambda: Enemy(player), ENEMY_COUNT)

        # El primer enemigo del pool es el JEFE: más vida, sprite más grande
        # y nombre propio para la barra del HUD. Sigue siendo un objeto del
        # mismo pool: el jefe no añade NINGÚN sistema nuevo al presupuesto.
        boss = self.pool.items[0]
        boss.display_name = BOSS_NAME
        boss.max_hp = BOSS_HP
        boss.height = 2.6                # Su "cabeza" empieza más arriba.
        boss._pivot.y = 1.3
        boss.sprite.scale = (2.4, 2.9)
        boss.collider = BoxCollider(boss, center=Vec3(0, 1.3, 0),
                                    size=Vec3(1.6, 2.6, 0.8))
        self.boss = boss

        for enemy in self.pool.items:
            enemy.on_death = self.notify_death
            self._respawn(enemy)

    def _respawn(self, enemy):
        margin = MAP_SIZE / 2 - 4
        enemy.position = Vec3(random.uniform(-margin, margin), 0,
                              random.uniform(-margin, margin))
        enemy.hp = enemy.max_hp          # Respeta la vida del jefe.
        enemy.sprite.color = color.white
        enemy._attack_timer = 0.0
        enemy.enabled = True
        if enemy.on_hp_changed:          # La barra del jefe reaparece llena.
            enemy.on_hp_changed(enemy.hp, enemy.max_hp)

    def reset_all(self):
        """Nueva partida: recolocar TODO el pool. Reiniciar = reusar."""
        for enemy in self.pool.items:
            self._respawn(enemy)

    def notify_death(self, enemy):
        # invoke() programa el respawn sin necesitar un update() propio.
        invoke(self._respawn, enemy, delay=ENEMY_RESPAWN_DELAY)
