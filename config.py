"""
config.py — Constantes globales de rendimiento y gameplay.

Centralizar los números aquí permite "tunear" el juego para hardware
más débil sin tocar la lógica (bajar RENDER_DISTANCE, SECTOR_SIZE, etc.).
"""

# ---------- Ventana / render ----------
WINDOW_TITLE = 'Detective Shooter — Ursina low-end'
FULLSCREEN = True       # True = pantalla completa a resolución nativa.
WINDOW_SCALE = 0.85     # Modo ventana: fracción del monitor (centrada).
VSYNC = True            # Limita los FPS al refresco del monitor: evita quemar CPU/GPU dibujando frames que nadie ve.
FAR_CLIP = 140          # Debe abarcar la diagonal de la caja de cielo (world.build_sky):
                        # desde una esquina del mapa hasta la esquina opuesta de la caja
                        # hay ~125 u. El mundo jugable sigue capado por niebla + culling.
FOG_START = 45          # La niebla lineal oculta el "pop" del sector culling.
FOG_END = 85            # El mundo se funde en el tono papel ANTES de llegar a la caja.
SKY_DIST = 52           # Media caja de cielo: paredes de papel a ±52 u del centro.

# ---------- Mundo / culling ----------
MAP_SIZE = 72           # Lado del mapa (unidades).
SECTOR_SIZE = 12        # Tamaño de cada sector combinado (1 sector = 1 draw call).
RENDER_DISTANCE = 55    # Sectores más lejos que esto se desactivan por completo.
CULL_INTERVAL = 0.25    # El culling manual corre 4 veces por segundo, NO cada frame.
WORLD_SEED = 7          # Mapa reproducible.

# ---------- Combate ----------
WEAPON_RANGE = 60       # Alcance del raycast (hitscan).

# ---------- ADS (apuntar con mira) ----------
FOV_DEFAULT = 90
FOV_ADS = 65             # Zoom ligero al apuntar.
ADS_SPEED = 10           # Velocidad del lerp de entrada/salida del apuntado.
ADS_SPREAD_MULT = 0.3    # Apuntando, la dispersión cae al 30%.

# ---------- Headshots ----------
HEADSHOT_MULT = 2.0      # Daño x2 en la cabeza.
HEADSHOT_ZONE = 2 / 3    # La "cabeza" es el tercio superior del sprite.

# ---------- Gamepad (simultáneo con teclado/ratón) ----------
GAMEPAD_DEADZONE = 0.15      # Zona muerta de los sticks (evita drift).
GAMEPAD_LOOK_SPEED_X = 170   # Grados/segundo de giro con stick a tope.
GAMEPAD_LOOK_SPEED_Y = 110
GAMEPAD_TRIGGER_THRESHOLD = 0.4  # Cuánto hay que apretar un gatillo.
TRACER_POOL_SIZE = 16   # Trazadores pre-instanciados (la escopeta usa 6/tiro).
IMPACT_POOL_SIZE = 16   # "Puffs" de impacto pre-instanciados (pooling).
TRACER_LIFETIME = 0.06
IMPACT_LIFETIME = 0.25

# ---------- Enemigos ----------
ENEMY_COUNT = 8         # Pool fijo de enemigos: nunca se crean/destruyen en runtime.
ENEMY_HP = 100
ENEMY_SPEED = 3.0
ENEMY_ACTIVE_DIST = 38  # Más lejos que esto, la IA ni se ejecuta (early-out).
ENEMY_STOP_DIST = 2.2   # Distancia a la que el enemigo deja de acercarse.
SPRITE_ANIM_INTERVAL = 0.1   # El índice de dirección del sprite se recalcula a 10 Hz, no a 60.
ENEMY_RESPAWN_DELAY = 3.0

# ---------- Jugador ----------
PLAYER_SPEED = 8
PLAYER_JUMP = 1.2
MOUSE_SENSITIVITY = 70
PLAYER_MAX_HP = 100

# ---------- Ataque enemigo ----------
ENEMY_DAMAGE = 6         # Golpe suave: ~17 golpes para matarte (antes 10).
ENEMY_ATTACK_RANGE = 2.6     # Un poco mayor que ENEMY_STOP_DIST.
ENEMY_ATTACK_INTERVAL = 0.9  # Segundos entre golpes.

# ---------- Arsenal ----------
# Una tabla de datos, no clases por arma: cambiar de arma es cambiar de
# diccionario (y un offset UV en el atlas de sprites), cero código nuevo.
# ammo_pickup = lo que da una caja amarilla: SIEMPRE menor que `magazine`
# (la capacidad máxima del cargador de cada arma), por regla de diseño.
DEFAULT_WEAPON = 'revolver'
WEAPONS = {
    'revolver': dict(
        name='REVÓLVER', frame=0, magazine=6, reserve_start=24,
        reserve_max=48, fire_rate=0.18, damage=34, reload_time=1.1,
        pellets=1, spread=0.0, ammo_pickup=4),
    'ametralladora': dict(
        name='AMETRALLADORA', frame=1, magazine=30, reserve_start=60,
        reserve_max=120, fire_rate=0.07, damage=11, reload_time=1.6,
        pellets=1, spread=0.02, ammo_pickup=18),
    'escopeta': dict(
        name='ESCOPETA', frame=2, magazine=4, reserve_start=12,
        reserve_max=24, fire_rate=0.9, damage=12, reload_time=1.5,
        pellets=6, spread=0.06, ammo_pickup=3),
}

# ---------- Jefe ----------
BOSS_NAME = 'SMURG'
BOSS_HP = 300

# ---------- Loot (cajas) ----------
CRATE_COUNT = 12             # Pool fijo: nunca se crean/destruyen en runtime.
CRATE_HEAL = 30
CRATE_PICKUP_RADIUS = 1.7
CRATE_RESPAWN_DELAY = 15.0
LOOT_CHECK_INTERVAL = 0.2    # Recogida por contacto chequeada a 5 Hz, no a 60.

# ---------- UI / minimapa ----------
MINIMAP_SIZE = 0.32          # Lado del minimapa en unidades de camera.ui.
                             # (El aro del marco consume borde: se compensa
                             # con un poco más de tamaño total.)
MINIMAP_RADIUS = 26          # Radio de mundo (unidades) que abarca el minimapa.
MINIMAP_INTERVAL = 0.15      # Refresco del minimapa a ~6 Hz, no por frame.
HUD_FACE_FRAMES = 3          # Rostros del detective: sano / herido / crítico.
STAT_INK_START = 76          # Valor inicial de "tinta" (fila de la gota).
STAT_SANITY_START = 82       # Valor inicial de "cordura" (fila de la nube).
