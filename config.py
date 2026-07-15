"""
config.py — Constantes globales de rendimiento y gameplay.

Centralizar los números aquí permite "tunear" el juego para hardware
más débil sin tocar la lógica (bajar FLOOR_SIZE, COVER_PER_FLOOR, tamaños
de los pools, etc.).
"""

# ---------- Ventana / render ----------
WINDOW_TITLE = 'Tinta y Plomo'
FULLSCREEN = True       # True = pantalla completa a resolución nativa.
WINDOW_SCALE = 0.85     # Modo ventana: fracción del monitor (centrada).
VSYNC = True            # Limita los FPS al refresco del monitor: evita quemar CPU/GPU dibujando frames que nadie ve.
FAR_CLIP = 140          # Debe abarcar la diagonal de la caja de cielo (world.build_sky):
                        # desde una esquina del mapa hasta la esquina opuesta de la caja
                        # hay ~125 u. El mundo jugable sigue capado por niebla + culling.
FOG_START = 45          # La niebla lineal oculta el "pop" del sector culling.
FOG_END = 85            # El mundo se funde en el tono papel ANTES de llegar a la caja.
SKY_DIST = 52           # Media caja de cielo: paredes de papel a ±52 u del centro.

# ---------- Mundo ----------
WORLD_SEED = 7          # Distribución de cobertura reproducible.

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

# ---------- Jugador ----------
PLAYER_SPEED = 8
PLAYER_JUMP = 1.2
MOUSE_SENSITIVITY = 70
PLAYER_MAX_HP = 100

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
CRATE_HEAL = 40              # Vida que restaura el botiquín (caja verde).
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


# ============================================================================
#  ARCHIVERO VERTICAL — 3 pisos superpuestos en el eje Y
# ============================================================================
# Geometría placeholder (bloques/planos grises): el arte real del escenario
# se coloca después. Estos números definen el "esqueleto" del nivel.
N_FLOORS = 3
FLOOR_SIZE = 56.0            # Lado (X y Z) de cada piso cuadrado (mapa grande =
                            # más espacio para disparar y esquivar).
FLOOR_HEIGHT = 8.0           # Separación vertical entre pisos = alto del techo
                            # (más alto = salas más amplias).
FLOOR_WALL_H = 7.0           # Alto de los muros perimetrales (acompaña al techo).
COVER_PER_FLOOR = 14        # Cajas/columnas de COBERTURA repartidas por piso.
# Altura Y del SUELO de cada piso. La IA y el WaveManager comparan player.y
# contra estos valores para saber en qué piso está físicamente el jugador.
FLOOR_Y = [i * FLOOR_HEIGHT for i in range(N_FLOORS)]

# ---- Rampa de acceso entre pisos ----
# Una rampa suave (pendiente baja) por piso: el FirstPersonController la sube
# sin bloquearse porque no hay un muro vertical y su raycast de gravedad va
# "pegando" al jugador a la superficie inclinada. Si tu build no la trepa,
# baja RAMP_SLOPE_RUN (más corta = más empinada) o súbelo (más tendida).
RAMP_WIDTH = 6.0            # Ancho de la rampa.
RAMP_SLOPE_RUN = 18.0      # Largo horizontal que cubre para subir FLOOR_HEIGHT
                          # (más grande = rampa más tendida = más fácil de subir).

# El jugador está "en" el piso i si su Y cae en la banda [Yi - 0.5, Yi + h).
# Umbral usado por floor_from_y().
FLOOR_BAND = FLOOR_HEIGHT * 0.5


def floor_from_y(y):
    """Índice de piso (0..N_FLOORS-1) según la altura Y del jugador.

    Matemática pura: sin colliders ni triggers. La usa el WaveManager para
    detectar cuándo el jugador 'llega físicamente' a un piso y activarlo.
    """
    idx = int((y + FLOOR_BAND) // FLOOR_HEIGHT)
    return max(0, min(N_FLOORS - 1, idx))


# ============================================================================
#  ENEMIGOS — 3 tipos, animados recortando su spritesheet por REGIONES
# ============================================================================
# Cada spritesheet tiene un layout distinto (rejilla uniforme en los peones,
# filas irregulares en el jefe), así que NO asumimos una rejilla global:
# cada animación declara su rectángulo en píxeles {x, y, fw, fh}, cuántos
# frames tiene y a qué velocidad (fps). El recorte se hace por UV en runtime
# (texture_offset/scale), sin cargar texturas nuevas — igual de barato que el
# atlas de armas. 'idle' = pose de apuntado en bucle; 'shoot' = ráfaga con
# fogonazo (se reproduce una vez por disparo).
#
# Medidas obtenidas inspeccionando los PNG reales de assets/enemies/:
#   enem1.png    1365x768  -> rejilla 5x4 (frame 273x192)
#   enemigo2.png  848x1251 -> rejilla 4x4 (frame 212x313)
#   jefe.png     1619x971  -> 3 filas etiquetadas de distinto ancho/altura
ENEMY_TYPES = {
    # -------- Enemigo 1 (Básico): pequeño, poca vida, dispara lento --------
    'basic': dict(
        sheet='assets/enemies/enem1.png', tex=(1365, 768),
        world_height=1.6, hp=40, speed=2.2,
        vision_range=16.0, fire_interval=1.4,
        bullet_damage=4, bullet_speed=14.0,
        col_w=0.55,                      # Ancho del collider (fracción de alto).
        anims=dict(
            idle=dict(x=0, y=0,   fw=273, fh=192, frames=5, fps=6),
            shoot=dict(x=0, y=576, fw=273, fh=192, frames=5, fps=14),
        ),
        fire_frame=1,                    # Frame de 'shoot' en que sale la bala.
    ),
    # -------- Enemigo 2 (Ejecutor): mediano, más vida y cadencia --------
    'executor': dict(
        sheet='assets/enemies/enemigo2.png', tex=(848, 1251),
        world_height=2.6, hp=90, speed=1.6,
        vision_range=20.0, fire_interval=1.1,
        bullet_damage=6, bullet_speed=16.0,
        col_w=0.5,
        anims=dict(
            idle=dict(x=0, y=0,   fw=212, fh=313, frames=4, fps=6),
            shoot=dict(x=0, y=938, fw=212, fh=313, frames=4, fps=12),
        ),
        fire_frame=1,
    ),
    # -------- Jefe Final: enorme, mucha vida, ráfaga rápida --------
    # 'idle' usa la fila "DETECTA AL JUGADOR (ENFADO)" y 'shoot' la fila
    # "DISPARA AL JUGADOR" (12 frames). La fila de recarga queda declarada
    # abajo por si quieres usarla, pero la IA base solo usa idle/shoot.
    'boss': dict(
        sheet='assets/enemies/jefe.png', tex=(1619, 971),
        world_height=5.0, hp=500, speed=1.2,
        vision_range=28.0, fire_interval=0.6,
        bullet_damage=9, bullet_speed=20.0,
        col_w=0.45,
        anims=dict(
            idle=dict(x=0, y=374, fw=202, fh=265, frames=8, fps=7),
            shoot=dict(x=0, y=702, fw=134, fh=240, frames=12, fps=16),
            # reload=dict(x=0, y=4, fw=202, fh=300, frames=8, fps=8),
        ),
        fire_frame=4,                    # El fogonazo empieza hacia el frame 4.
        is_boss=True,
    ),
}

# Nombre del jefe para la barra superior del HUD (ya existía BOSS_NAME arriba).
# Tamaño de cada pool por tipo: nunca se crean/destruyen enemigos en runtime,
# el WaveManager solo reposiciona y (des)activa los de estos pools.
ENEMY_POOL = {'basic': 9, 'executor': 6, 'boss': 1}

# Velocidad de la animación de "flash" de daño y persecución.
ENEMY_FLASH_TIME = 0.10
ENEMY_HB_WIDTH = 1.1        # Ancho de la barrita de vida sobre la cabeza.
ENEMY_HB_HEIGHT = 0.12

# ============================================================================
#  BALA ENEMIGA (proyectil)
# ============================================================================
EBULLET_POOL_SIZE = 40      # Balas enemigas pre-instanciadas (pooling).
EBULLET_LIFETIME = 3.5      # Segundos antes de reciclarse si no impacta.
EBULLET_HIT_RADIUS = 0.7    # Distancia al jugador para contar impacto.
EBULLET_SIZE = 0.35         # Tamaño del quad billboard de la bala.

# ============================================================================
#  OLEADAS POR PISO (Wave Manager)
# ============================================================================
# Cada piso: lista de OLEADAS; cada oleada: lista de (tipo, cantidad).
# La siguiente oleada del piso solo aparece cuando se limpia la anterior.
# El piso solo se activa cuando el jugador llega físicamente a su altura Y.
FLOORS_WAVES = [
    # ---- Piso 1: 2 oleadas — pequeños con un par de medianos ----
    [
        [('basic', 6), ('executor', 2)],
        [('basic', 5), ('executor', 3)],
    ],
    # ---- Piso 2: 2 oleadas — mezcla equilibrada pequeños/medianos ----
    [
        [('basic', 5), ('executor', 3)],
        [('basic', 5), ('executor', 4)],
    ],
    # ---- Piso 3: medianos + JEFE. Matar al jefe = ganar ----
    [
        [('executor', 4)],
        [('executor', 3), ('boss', 1)],
    ],
]
WAVE_DELAY = 2.5            # Pausa entre el fin de una oleada y la siguiente.
