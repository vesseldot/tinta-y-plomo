"""
main.py — Punto de entrada: configura el motor y ensambla el ARCHIVERO.

ARQUITECTURA
------------
    config.py       -> constantes de rendimiento/gameplay (tuning en un lugar)
    assets_gen.py   -> genera sprites placeholder la primera vez
    pool.py         -> Entity Pooling genérico (cero instanciación en runtime)
    world.py        -> 3 pisos grises apilados (Archivero) + rampas + cielo
    player.py       -> controlador FPS + vida/muerte por eventos
    enemies.py      -> enemigos billboard animados por spritesheet + IA a
                       distancia + barra de vida propia + pooling
    enemy_bullet.py -> proyectil enemigo (EnemyBullet) reciclado
    waves.py        -> EnemyManager (pools) + WaveManager (oleadas por piso)
    combat.py       -> hitscan del jugador, munición/recarga, arma en HUD
    loot.py         -> cajas de vida/munición recicladas
    ui.py           -> HUD reactivo (retrato + barra de vida + oleada/jefe)
    menus.py        -> inicio/pausa/game over/VICTORIA vía application.paused

FLUJO DEL NIVEL
---------------
El jugador empieza en el Piso 1. El WaveManager detecta en qué piso está
(por su altura Y) y activa las oleadas de ese piso; los enemigos de pisos
superiores permanecen inertes hasta que subes por la rampa. Limpiar todas
las oleadas de un piso lo despeja; en el Piso 3 aparece el Jefe: derrotarlo
gana la partida.

Ejecutar:  python main.py          (ENTER inicia · WASD/ratón · R recarga
                                    ESPACIO salta · ESC pausa)
           python main.py --smoke  (prueba automática mínima y salida)
"""

import sys
import traceback

# ---- Desactivar el motor de audio ANTES de crear Ursina ----
# El juego aún no usa sonidos, y en máquinas sin dispositivo de salida válido
# OpenAL/WASAPI falla y reintenta (errores 0x800705aa) ralentizando el
# arranque. 'audio-library-name null' hace que Panda3D use un gestor de audio
# nulo: cero init de audio, arranque más rápido y sin esos errores. Si más
# adelante agregas sonidos, quita estas dos líneas.
from panda3d.core import loadPrcFileData
loadPrcFileData('', 'audio-library-name null')

from screeninfo import get_monitors
from ursina import Ursina, application, camera, color, scene, time, window

from assets_gen import ensure_assets
from combat import Weapon
from config import (FAR_CLIP, FOG_END, FOG_START, FULLSCREEN, VSYNC,
                    WINDOW_SCALE, WINDOW_TITLE)
from loot import LootManager
from menus import MenuManager
from player import Player
from ui import GameHUD
from waves import EnemyManager, WaveManager
from world import build_archive, build_sky


def _log(msg):
    """Progreso de arranque a consola (con flush para que se vea aunque
    la ventana se cuelgue)."""
    print(f'[arranque] {msg}', flush=True)


# --windowed: ventana pequeña en vez de pantalla completa (para depurar sin
# que el juego tome toda la pantalla). Útil si "Python no responde".
WINDOWED = '--windowed' in sys.argv
use_fullscreen = FULLSCREEN and not WINDOWED

# Los placeholders deben existir ANTES de que cualquier Entity los cargue.
_log('generando/verificando assets...')
ensure_assets()
_log('assets listos')

# ---- Tamaño de ventana EXPLÍCITO y en ENTEROS (Panda3D rechaza floats) ----
monitor = get_monitors()[0]
if use_fullscreen:
    win_size = (monitor.width, monitor.height)
    win_position = (0, 0)
elif WINDOWED:
    win_size = (1280, 720)
    win_position = (80, 60)
else:
    win_size = (int(monitor.width * WINDOW_SCALE),
                int(monitor.height * WINDOW_SCALE))
    win_position = ((monitor.width - win_size[0]) // 2,
                    (monitor.height - win_size[1]) // 2)

_log(f'creando ventana {win_size} fullscreen={use_fullscreen} ...')
app = Ursina(title=WINDOW_TITLE, vsync=VSYNC, development_mode=False,
             borderless=use_fullscreen, fullscreen=use_fullscreen,
             size=win_size, position=win_position)
_log('ventana creada (motor listo)')

# ---------------- Render para gama baja ----------------
window.fps_counter.enabled = True
window.exit_button.enabled = False

# ---------------- Ensamblaje del juego ----------------
# Todo el ensamblaje va en un try/except: si algo falla al construir el
# nivel, escribimos la traza COMPLETA en error.log (junto a main.py) y la
# imprimimos, para no quedarnos con una ventana "que no responde" sin pista.
try:
    _log('render config...')
    SKY = color.hsv(285, 0.09, 0.36)
    window.color = SKY
    camera.clip_plane_far = FAR_CLIP
    scene.fog_color = SKY
    scene.fog_density = (FOG_START, FOG_END)

    _log('construyendo archivero (3 pisos)...')
    floors, gates = build_archive()     # Pisos texturizados + rampas + rejas.
    _log('cielo...')
    build_sky()                         # Telón tormentoso (1 draw call).
    _log('jugador...')
    player = Player()                   # FPS + vida/muerte por eventos.
    _log('arma...')
    weapon = Weapon(player)             # Hitscan + munición + arma 2D en HUD.
    _log('enemigos (cargando spritesheets)...')
    enemies = EnemyManager(player)      # Pools por tipo + pool de balas + jefe.
    _log('loot...')
    loot = LootManager(player, weapon)  # Cajas de vida/munición reutilizables.

    _log('HUD...')
    hud = GameHUD(player, weapon, enemies.all_enemies, loot.crates)
    hud.bind_boss(enemies.boss)         # Barra superior: vida del jefe.

    _log('wave manager...')
    waves = WaveManager(player, enemies, hud, gates)

    _log('menus...')
    menus = MenuManager(player, weapon, waves, loot, hud)
    waves.on_win = menus.show_win       # Matar al jefe -> pantalla VICTORIA.
    _log('ensamblaje COMPLETO — mostrando pantalla de inicio')
except Exception:
    tb = traceback.format_exc()
    print(tb, flush=True)
    try:
        with open('error.log', 'w', encoding='utf-8') as f:
            f.write(tb)
    except Exception:
        pass
    raise


# ---------------- Prueba de humo mínima ----------------
if '--smoke' in sys.argv:
    from ursina import Entity

    class SmokeRunner(Entity):
        def __init__(self, steps):
            super().__init__(ignore_paused=True)
            self.steps = sorted(steps)
            self.elapsed = 0.0
            self.index = 0

        def update(self):
            self.elapsed += time.dt
            while (self.index < len(self.steps)
                   and self.elapsed >= self.steps[self.index][0]):
                self.steps[self.index][1]()
                self.index += 1

    SmokeRunner([
        (1.0, lambda: app.input('space')),                 # Inicia el caso.
        (1.2, lambda: print('SMOKE piso jugador:',
                            __import__('config').floor_from_y(player.y))),
        (1.5, lambda: player.take_damage(40)),             # Barra de vida baja.
        (2.0, lambda: print('SMOKE hp jugador:', player.hp)),
        (2.5, lambda: player.take_damage(999)),            # -> Game Over.
        (3.0, menus.restart),                              # Reinicio = reuso.
        (3.4, lambda: print('SMOKE reinicio OK, arma:', weapon.current)),
        (4.0, application.quit),
    ])

_log('iniciando bucle principal (app.run)')
try:
    app.run()
except Exception:
    tb = traceback.format_exc()
    print(tb, flush=True)
    try:
        with open('error.log', 'w', encoding='utf-8') as f:
            f.write(tb)
    except Exception:
        pass
    raise
