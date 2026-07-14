"""
combat.py — Arsenal intercambiable + hitscan + pools de efectos + arma en HUD.

ARSENAL COMO DATOS, NO COMO CLASES
----------------------------------
Las 3 armas (revólver / ametralladora / escopeta) son ENTRADAS de la tabla
WEAPONS en config.py, no subclases. Cambiar de arma cuesta:
  1. Cambiar un diccionario activo (self.current).
  2. Mover el texture_offset del atlas guns_sheet.png (cero cargas de
     textura, igual que las 8 direcciones de los enemigos).
La munición de cada arma (cargador + reserva) persiste al cambiar.

HITSCAN Y PERDIGONES
--------------------
La escopeta no crea proyectiles: son `pellets` raycasts con una desviación
aleatoria barata (spread). El trazador visual de cada perdigón sale del
mismo pool de siempre. La ametralladora solo baja fire_rate: el disparo
sostenido reutiliza los mismos objetos del pool una y otra vez.

RECARGA
-------
Tecla R (o automática al vaciar el cargador): un temporizador plano, sin
Sequences. La caja amarilla da `ammo_pickup` balas del arma ACTUAL, siempre
menos que su cargador (regla de diseño, ver config.py).
"""

import random

from ursina import (Entity, Vec2, Vec3, camera, color, held_keys, lerp,
                    raycast, time)
from ursina.shaders import unlit_shader

from pool import EntityPool
from config import (ADS_SPEED, ADS_SPREAD_MULT, DEFAULT_WEAPON, FOV_ADS,
                    FOV_DEFAULT, GAMEPAD_TRIGGER_THRESHOLD, HEADSHOT_MULT,
                    HEADSHOT_ZONE, IMPACT_LIFETIME, IMPACT_POOL_SIZE,
                    TRACER_LIFETIME, TRACER_POOL_SIZE, WEAPONS, WEAPON_RANGE)


class Tracer(Entity):
    """Línea del disparo. Vive TRACER_LIFETIME y se auto-recicla.

    Ursina solo llama update() de entidades habilitadas: un trazador
    deshabilitado en el pool cuesta exactamente cero.
    """

    def __init__(self):
        super().__init__(model='cube', color=color.yellow, shader=unlit_shader)
        self._life = 0.0

    def fire(self, start, end):
        length = (end - start).length()
        self.scale = Vec3(0.03, 0.03, max(length, 0.01))
        self.position = (start + end) / 2
        self.look_at(end)
        self._life = TRACER_LIFETIME

    def update(self):
        self._life -= time.dt
        if self._life <= 0:
            EntityPool.release(self)


class ImpactPuff(Entity):
    """Nube de impacto billboard reciclada (sustituye a un sistema de
    partículas completo: en gama baja el overdraw de partículas es veneno)."""

    def __init__(self):
        super().__init__(model='quad', texture='assets/puff.png',
                         double_sided=True, shader=unlit_shader)
        self.setBillboardPointEye()   # Billboard total en C++.
        self._life = 0.0

    def burst(self, position, tint=color.white):
        self.position = position
        self.scale = 0.15
        self.color = tint            # Amarillo en headshot: feedback gratis.
        self._life = IMPACT_LIFETIME

    def update(self):
        self._life -= time.dt
        if self._life <= 0:
            EntityPool.release(self)
            return
        # Entity.scale es Vec3: la expansión se hace con vector uniforme.
        growth = time.dt * 2.0
        self.scale += Vec3(growth, growth, growth)


class Weapon(Entity):
    """Arma en mano (sprite HUD) + lógica de disparo/recarga/arsenal."""

    REST_POS = Vec3(0.32, -0.32, 0)     # Posición de cadera (hip-fire).
    ADS_POS = Vec3(0, -0.24, 0)         # Apuntando: arma al centro.
    RECOIL_POS = Vec3(0.34, -0.27, 0)   # Salta un poco hacia arriba al tirar.
    RELOAD_POS = Vec3(0.32, -0.55, 0)   # El arma "baja" durante la recarga.
    N_FRAMES = len(WEAPONS)             # Frames del atlas guns_sheet.

    def __init__(self, player):
        super().__init__(parent=camera.ui)
        self.player = player
        self._cooldown = 0.0
        self._reload_timer = 0.0
        self._flash_timer = 0.0
        # ADS: un solo float 0..1. Toda la mecánica (posición del sprite,
        # FOV y dispersión) se deriva de él por interpolación: sin
        # animaciones frame a frame, sin Sequences, sin estados extra.
        self.ads = 0.0

        # Estado del arsenal: {clave: {'magazine': n, 'reserve': n}}.
        # Solo diccionarios y enteros: nada que el GC tenga que perseguir.
        self.owned = {}
        self.current = None

        # Callbacks por EVENTO para el HUD (ver ui.py).
        self.on_ammo_changed = None
        self.on_weapon_changed = None

        self.sprite = Entity(parent=self, model='quad',
                             texture='assets/guns_sheet.png',
                             scale=(0.42, 0.32), position=Weapon.REST_POS,
                             shader=unlit_shader)
        self.sprite.texture_scale = Vec2(1 / Weapon.N_FRAMES, 1)
        self.sprite.texture.filtering = None   # Bordes duros estilo tinta.

        self.muzzle_flash = Entity(parent=self, model='quad',
                                   texture='assets/puff.png', scale=0.07,
                                   position=Weapon.REST_POS + Vec3(-0.1, 0.1, 0),
                                   color=color.yellow, enabled=False,
                                   shader=unlit_shader)

        # Pools llenados al cargar el nivel, nunca durante el combate.
        self.tracers = EntityPool(Tracer, TRACER_POOL_SIZE)
        self.impacts = EntityPool(ImpactPuff, IMPACT_POOL_SIZE)

        self.give_weapon(DEFAULT_WEAPON)

    # ------------------------------------------------------------- estado
    @property
    def cfg(self):
        """Datos del arma actual (tabla WEAPONS)."""
        return WEAPONS[self.current]

    @property
    def state(self):
        """Munición del arma actual: {'magazine': n, 'reserve': n}."""
        return self.owned[self.current]

    def _notify_ammo(self):
        if self.on_ammo_changed:
            self.on_ammo_changed(self.state['magazine'], self.state['reserve'])

    # ------------------------------------------------------------ arsenal
    def give_weapon(self, kind):
        """Caja ROJA: entrega un arma y cambia a ella.

        Si ya la teníamos, la caja suelta `ammo_pickup` balas de esa arma
        (menos que su cargador) para no ser una caja vacía.
        """
        cfg = WEAPONS[kind]
        if kind not in self.owned:
            self.owned[kind] = {'magazine': cfg['magazine'],
                                'reserve': cfg['reserve_start']}
        else:
            s = self.owned[kind]
            s['reserve'] = min(cfg['reserve_max'],
                               s['reserve'] + cfg['ammo_pickup'])
        self.switch_weapon(kind)
        return True

    def switch_weapon(self, kind):
        self.current = kind
        self._reload_timer = 0.0
        self._cooldown = 0.0
        # Cambiar de arma = mover UVs del atlas. Cero rebind de textura.
        self.sprite.texture_offset = Vec2(WEAPONS[kind]['frame']
                                          / Weapon.N_FRAMES, 0)
        if self.on_weapon_changed:
            self.on_weapon_changed(kind, WEAPONS[kind])
        self._notify_ammo()

    # -------------------------------------------------------------- input
    def input(self, key):
        if key in ('r', 'gamepad x'):    # Recarga en teclado Y en mando.
            self.start_reload()

    def update(self):
        # Recarga por temporizador plano (sin invoke/Sequence).
        if self._reload_timer > 0:
            self._reload_timer -= time.dt
            if self._reload_timer <= 0:
                self._finish_reload()

        if self._cooldown > 0:
            self._cooldown -= time.dt
        if self._flash_timer > 0:
            self._flash_timer -= time.dt
            if self._flash_timer <= 0:
                self.muzzle_flash.enabled = False

        # ---- ADS: click derecho O gatillo izquierdo del mando ----
        # held_keys guarda los ejes del gamepad como floats: el gatillo
        # se lee igual que una tecla, solo que con umbral.
        ads_held = (held_keys['right mouse']
                    or held_keys['gamepad left trigger']
                    > GAMEPAD_TRIGGER_THRESHOLD)
        target_ads = 1.0 if (ads_held and self._reload_timer <= 0) else 0.0
        self.ads = lerp(self.ads, target_ads, ADS_SPEED * time.dt)

        # FOV derivado del mismo float. La guardia evita reconfigurar la
        # lente de Panda3D cuando la transición ya terminó.
        target_fov = lerp(FOV_DEFAULT, FOV_ADS, self.ads)
        if abs(camera.fov - target_fov) > 0.05:
            camera.fov = target_fov

        # ---- disparo: click izquierdo O gatillo derecho del mando ----
        firing = (held_keys['left mouse']
                  or held_keys['gamepad right trigger']
                  > GAMEPAD_TRIGGER_THRESHOLD)
        if firing and self._cooldown <= 0 and self._reload_timer <= 0:
            self.shoot()

        # Posición del sprite: cadera <-> centro (ADS) <-> recarga, todo
        # con lerps del mismo quad. Cero animaciones adicionales.
        if self._reload_timer > 0:
            target = Weapon.RELOAD_POS
        else:
            target = lerp(Weapon.REST_POS, Weapon.ADS_POS, self.ads)
        self.sprite.position = lerp(self.sprite.position, target, 8 * time.dt)

    # ------------------------------------------------------------ disparo
    def shoot(self):
        state = self.state
        if state['magazine'] <= 0:
            self.start_reload()      # Clic con el cargador vacío: recarga sola.
            return

        cfg = self.cfg
        state['magazine'] -= 1
        self._notify_ammo()
        self._cooldown = cfg['fire_rate']
        self._flash_timer = 0.06
        self.sprite.position = Weapon.RECOIL_POS
        self.muzzle_flash.enabled = True

        # Origen visual del trazador: sale "del arma" del HUD.
        start = (camera.world_position + camera.forward * 1.2
                 + camera.right * 0.25 - camera.up * 0.18)

        # Apuntando, la dispersión se reduce (interpolada por el mismo
        # float de ADS: transición continua, no un switch).
        spread = cfg['spread'] * lerp(1.0, ADS_SPREAD_MULT, self.ads)

        # pellets raycasts: la escopeta dispara 6 de golpe, el resto 1.
        # Sigue siendo hitscan puro en C++: sin proyectiles físicos.
        for _ in range(cfg['pellets']):
            direction = camera.forward
            if spread > 0:
                direction = (camera.forward
                             + camera.right * random.uniform(-spread, spread)
                             + camera.up * random.uniform(-spread, spread)
                             ).normalized()
            hit = raycast(camera.world_position, direction,
                          distance=WEAPON_RANGE, ignore=(self.player,))
            end = (hit.world_point if hit.hit
                   else camera.world_position + direction * WEAPON_RANGE)
            self.tracers.acquire().fire(start, end)
            if hit.hit:
                # ---- HEADSHOT por matemática de altura (sin colliders
                # extra). Los enemigos billboard exponen `height`; si el
                # punto de impacto cae en el tercio superior del sprite
                # (y_impacto > y_pies + altura * 2/3), el daño se
                # multiplica. Una resta y una comparación por perdigón:
                # infinitamente más barato que un segundo BoxCollider
                # por enemigo que Panda3D tendría que testear en CADA ray.
                damage = cfg['damage']
                headshot = False
                target_height = getattr(hit.entity, 'height', 0)
                if (target_height
                        and hit.world_point.y > hit.entity.y
                        + target_height * HEADSHOT_ZONE):
                    damage = int(damage * HEADSHOT_MULT)
                    headshot = True
                self.impacts.acquire().burst(
                    hit.world_point,
                    color.yellow if headshot else color.white)
                # Duck typing: enemigos Y cajas de loot son dañables.
                if hasattr(hit.entity, 'take_damage'):
                    hit.entity.take_damage(damage)

        if state['magazine'] == 0:
            self.start_reload()      # Encadenar recarga al vaciar.

    # ------------------------------------------------------------ munición
    def start_reload(self):
        state = self.state
        if (self._reload_timer > 0 or state['magazine'] >= self.cfg['magazine']
                or state['reserve'] <= 0):
            return
        self._reload_timer = self.cfg['reload_time']

    def _finish_reload(self):
        state, cfg = self.state, self.cfg
        take = min(cfg['magazine'] - state['magazine'], state['reserve'])
        state['magazine'] += take
        state['reserve'] -= take
        self._notify_ammo()

    def add_ammo(self):
        """Caja AMARILLA: munición del arma ACTUAL (ammo_pickup < cargador).

        Devuelve False si la reserva está llena: la caja no se gasta.
        """
        state, cfg = self.state, self.cfg
        if state['reserve'] >= cfg['reserve_max']:
            return False
        state['reserve'] = min(cfg['reserve_max'],
                               state['reserve'] + cfg['ammo_pickup'])
        self._notify_ammo()
        return True

    def reset(self):
        """Nueva partida: de vuelta al revólver solo, contadores de fábrica."""
        self.owned = {}
        self._reload_timer = 0.0
        self._cooldown = 0.0
        self._flash_timer = 0.0
        self.ads = 0.0
        camera.fov = FOV_DEFAULT
        self.muzzle_flash.enabled = False
        self.give_weapon(DEFAULT_WEAPON)
