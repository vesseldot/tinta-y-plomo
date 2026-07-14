"""
main.py — Punto de entrada: configuración del motor y ensamblaje de módulos.

ARQUITECTURA
------------
    config.py     -> constantes de rendimiento/gameplay (tuning en un solo lugar)
    assets_gen.py -> genera sprites placeholder flat/cel la primera vez
    pool.py       -> Entity Pooling genérico (cero instanciación en runtime)
    world.py      -> mapa low-poly, geometría combinada por sector, culling
    player.py     -> controlador FPS + vida/muerte por eventos
    enemies.py    -> billboards 8-direcciones + IA barata + ataque + pool
    combat.py     -> hitscan, munición/recarga, arma 2D en HUD, pools de efectos
    loot.py       -> cajas de vida/munición recicladas (pool + distancia²)
    ui.py         -> HUD reactivo por eventos + minimapa sin segunda cámara
    menus.py      -> inicio/pausa/game over vía application.paused

PIPELINE DE RENDER
------------------
Ursina/Panda3D usa FORWARD RENDERING simple por defecto: exactamente lo que
queremos para gama baja. La clave es NO activar nada encima:
  - Cero luces en escena + unlit_shader en los sprites => sin coste de
    iluminación por pixel, y el sombreado plano ES la estética buscada.
  - Sin post-procesado (Bloom/SSAO/FXAA existen en Panda3D pero cada uno es
    una o más pasadas full-screen extra: prohibidas aquí).
  - Sin sombras dinámicas (shadow maps = re-render de la escena por luz).
  - Cielo = color de fondo de la ventana: 0 geometría, 0 draw calls.

NOTA SOBRE PYGAME
-----------------
No se necesita: Panda3D ya provee input de teclado/ratón y audio nativos
(clase Audio de Ursina). Meter Pygame añadiría un segundo bucle de eventos
SDL compitiendo con el de Panda3D. El único caso legítimo sería audio
avanzado con `pygame.mixer` inicializado SOLO (pygame.mixer.init(), sin
pygame.init() ni ventana): corre en su propio hilo y no toca el bucle
principal. Para este proyecto, Audio de Ursina basta.

Ejecutar:  python main.py         (ENTER inicia · WASD/ratón · R recarga
                                   ESPACIO salta · ESC pausa)
           python main.py --smoke (prueba automática: recorre menú, disparo,
                                   recarga, loot, muerte y reinicio en 5 s)
"""

import sys

from screeninfo import get_monitors   # Dependencia que Ursina ya trae.
from ursina import (Entity, Ursina, Vec3, application, camera, color, scene,
                    time, window)

from assets_gen import ensure_assets
from combat import Weapon
from config import (FAR_CLIP, FOG_END, FOG_START, FULLSCREEN, VSYNC,
                    WINDOW_SCALE, WINDOW_TITLE)
from enemies import EnemyManager
from loot import LootManager
from menus import MenuManager
from player import Player
from ui import GameHUD
from world import SectorCuller, build_sky, build_world

# Los sprites placeholder deben existir ANTES de que cualquier Entity los cargue.
ensure_assets()

# ---- Tamaño de ventana EXPLÍCITO y en ENTEROS ----
# Ursina calcula su tamaño por defecto con floats (p.ej. 1920.0) y Panda3D
# RECHAZA ese valor ("Invalid integer value for ConfigVariable win-size"),
# dejando una ventana mal dimensionada que se ve cortada. Pedimos el
# monitor real y pasamos enteros: ventana centrada al 85% del monitor, o
# pantalla completa nativa si FULLSCREEN=True en config.py.
monitor = get_monitors()[0]
if FULLSCREEN:
    win_size = (monitor.width, monitor.height)
    win_position = (0, 0)
else:
    win_size = (int(monitor.width * WINDOW_SCALE),
                int(monitor.height * WINDOW_SCALE))
    win_position = ((monitor.width - win_size[0]) // 2,
                    (monitor.height - win_size[1]) // 2)

# development_mode=False apaga el hot-reload y los contadores de debug de
# Ursina: menos trabajo por frame en el build "final".
app = Ursina(title=WINDOW_TITLE, vsync=VSYNC, development_mode=False,
             borderless=FULLSCREEN, fullscreen=FULLSCREEN,
             size=win_size, position=win_position)

# ---------------- Configuración de render para gama baja ----------------
window.fps_counter.enabled = True          # Para medir mientras desarrollas.
window.exit_button.enabled = False

# La caja de cielo es un cielo tormentoso en acuarela (world.build_sky).
# Este color es el tono del HORIZONTE (banda inferior del arte, medida con
# PIL): la niebla funde el mundo 3D lejano exactamente hacia esa franja, así
# el corte con el telón es invisible.
# (Si cambias fondo.png, recalcula el promedio RGB de su banda ~60-85% alto.)
SKY = color.hsv(285, 0.09, 0.36)
window.color = SKY          # Respaldo si algo asomara fuera del telón.

# Far clip corto: recorta el frustum -> menos objetos pasan el frustum
# culling de Panda3D y el z-buffer gana precisión.
camera.clip_plane_far = FAR_CLIP

# Niebla LINEAL: esconde el far clip y el apagado de sectores lejanos.
scene.fog_color = SKY
scene.fog_density = (FOG_START, FOG_END)

# ---------------- Ensamblaje del juego ----------------
sectors = build_world()             # Mapa low-poly, 1 draw call por sector.
SectorCuller(sectors)               # Culling por distancia a 4 Hz.
build_sky()                         # Telón de papel: 1 quad fijo a la cámara.
player = Player()                   # FPS + vida/muerte por eventos.
weapon = Weapon(player)             # Hitscan + munición + arma 2D en HUD.
enemies = EnemyManager(player)      # Pool de enemigos billboard.
loot = LootManager(player, weapon)  # Cajas de vida/munición reutilizables.
hud = GameHUD(player, weapon, enemies.pool.items, loot.crates)
hud.bind_boss(enemies.boss)         # Barra superior: vida de SMURG por evento.
menus = MenuManager(player, weapon, enemies, loot, hud)  # Arranca en 'inicio'.


# ---------------- Prueba de humo automática ----------------
# Recorre TODO el pipeline (menú -> disparo -> recarga -> loot -> muerte ->
# game over -> reinicio) sin tocar teclado/ratón, y cierra a los 5 s.
if '--smoke' in sys.argv:

    class SmokeRunner(Entity):
        """Línea de tiempo de eventos. ignore_paused=True: corre incluso
        con el juego congelado en menús (los invoke normales se pausarían)."""

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

    def _crate(kind):
        return next(c for c in loot.crates if c.kind == kind and c.enabled)

    SmokeRunner([
        # app.input(...) es la vía oficial de Ursina para simular teclas:
        # recorre exactamente el mismo despacho que el teclado físico
        # (incluido el filtro de application.paused / ignore_paused).
        (1.0, lambda: app.input('space')),
        (1.2, lambda: print('SMOKE estado tras espacio:', menus.state)),
        # Jefe teletransportado al frente: el rayo horizontal de la cámara
        # (y≈1.8) cae en su tercio superior (>1.73) => headshot esperado.
        (1.3, lambda: setattr(enemies.boss, 'position',
                              player.position + Vec3(0, 0, 6))),
        (1.4, lambda: app.input('right mouse down')),      # ADS on.
        (1.5, lambda: app.input('left mouse down')),       # Revólver.
        (1.62, lambda: print(f'SMOKE fov apuntando: {camera.fov:.0f} · '
                             f'hp jefe tras 1 tiro: {enemies.boss.hp} '
                             f'(headshot=232, cuerpo=266)')),
        (2.0, lambda: app.input('left mouse up')),
        (2.05, lambda: app.input('right mouse up')),       # ADS off.
        (2.1, lambda: app.input('r')),                     # Recarga manual.
        (2.4, lambda: loot.consume(_crate('weapon'))),     # Caja ROJA: arma.
        (2.5, lambda: print('SMOKE arma actual:', weapon.current)),
        (2.6, lambda: app.input('left mouse down')),       # Arma nueva.
        (3.1, lambda: app.input('left mouse up')),
        (3.3, lambda: enemies.boss.take_damage(120)),      # Barra de jefe.
        (3.5, lambda: loot.consume(_crate('ammo'))),       # Caja AMARILLA.
        (3.7, lambda: player.take_damage(60)),
        (3.9, lambda: loot.consume(_crate('health'))),     # Caja BLANCA.
        (4.1, lambda: player.take_damage(999)),            # -> Game Over.
        (4.5, menus.restart),
        (4.7, lambda: print('SMOKE arma tras reinicio:', weapon.current)),
        (5.2, application.quit),
    ])

app.run()
