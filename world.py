"""
world.py — El Archivero: 3 pisos texturizados apilados en Y, con cobertura,
y un HUECO DE ESCALERA cerrado por una pared completa que se retira al
despejar el piso.

TEXTURAS
--------
Piso -> assets/ui/piso.png (tileada, double_sided para que sirva de TECHO del
piso inferior). Muros -> assets/ui/paredes.png (tileados). Todo unlit_shader.

CONEXIÓN VERTICAL FIABLE
------------------------
Cada rampa vive dentro de un HUECO DE ESCALERA: dos paredes laterales la
encierran y una PARED COMPLETA (de piso a techo) tapa la entrada. Como el
FirstPersonController choca con paredes verticales (su raycast frontal) y las
laterales impiden rodearla, no hay forma de subir hasta que el WaveManager
retira esa pared al despejar el piso. La rampa sube por un hueco en el piso
de arriba y el jugador emerge dentro de ese piso.

Las rampas ALTERNAN de lado por piso (piso 0 al norte, piso 1 al sur) para
que no se apilen en la misma columna y el jugador tenga que cruzar el piso.

COBERTURA
---------
COVER_PER_FLOOR cajas/columnas con collider por piso, evitando el centro
(spawn) y las columnas de las escaleras.
"""

import math
import random

from ursina import Entity, Vec3, color, load_texture
from ursina.shaders import unlit_shader

from config import (COVER_PER_FLOOR, FLOOR_HEIGHT, FLOOR_SIZE, FLOOR_WALL_H,
                    FLOOR_Y, N_FLOORS, RAMP_SLOPE_RUN, RAMP_WIDTH, SKY_DIST,
                    WORLD_SEED)

# Grises planos para cobertura.
FLAT_PALETTE = [
    color.hsv(30, 0.12, 0.62),
    color.hsv(220, 0.10, 0.50),
    color.hsv(20, 0.18, 0.45),
    color.hsv(0, 0.0, 0.55),
]
GATE_COL = color.hsv(0, 0.55, 0.45)     # Rojo apagado: pared "bloqueado".
WALL_ASPECT = 1408 / 768                # Proporción del arte de paredes.

_H = FLOOR_SIZE / 2
_HOLE_HX = RAMP_WIDTH / 2 + 1.0         # Medio ancho del hueco/rampa en X.
_SHAFT_HX = RAMP_WIDTH / 2 + 0.5        # Medio ancho de las paredes del hueco.

# Rampa por piso: piso 0 sube por el NORTE, piso 1 por el SUR (el último no
# sube). El hueco de un piso está en el lado por el que sube el piso de abajo.
RAMP_SIDES = ['north', 'south']


def _corridor(side):
    """Geometría del hueco de escalera para un lado ('north'/'south').

    Devuelve el rectángulo del hueco (hx0,hx1,hz0,hz1) y las Z de la rampa.
    Todo es simétrico respecto al centro: 'south' es 'north' con Z negada.
    """
    s = 1 if side == 'north' else -1
    z_far = s * (_H - 5.0)              # Borde junto al muro perimetral.
    z_near = s * (_H - 14.0)           # Borde interior del hueco.
    hz0, hz1 = sorted((z_near, z_far))
    # El extremo ALTO de la rampa llega EXACTO al borde lejano del hueco
    # (z_far), que es donde empieza la tira de piso del nivel de arriba: así
    # el jugador pisa el piso sin caer por el hueco.
    ramp_top = z_far
    ramp_bot = ramp_top - s * RAMP_SLOPE_RUN   # Extremo BAJO (hacia el centro).
    return dict(hole=(-_HOLE_HX, _HOLE_HX, hz0, hz1),
                ramp_top=ramp_top, ramp_bot=ramp_bot, s=s)


def build_sky():
    """Cielo tormentoso en acuarela como cúpula esférica (1 draw call)."""
    tex = load_texture('assets/ui/fondo.png')
    sky = Entity(model='sphere', texture=tex, position=Vec3(0, 2, 0),
                 scale=SKY_DIST * 2, double_sided=True, shader=unlit_shader)
    sky.setFogOff(1)
    cap = Entity(model='quad', color=color.hsv(0, 0.005, 0.86),
                 position=Vec3(0, 2 + SKY_DIST * 0.9, 0), rotation_x=90,
                 scale=SKY_DIST * 1.1, double_sided=True, shader=unlit_shader)
    cap.setFogOff(1)
    return [sky, cap]


def _floor_tile(cx, cz, sx, sz, y):
    """Trozo de piso texturizado (plano + collider), visible por ambos lados
    (hace de techo del piso de abajo)."""
    f = Entity(model='plane', position=Vec3(cx, y, cz), scale=Vec3(sx, 1, sz),
               texture='assets/ui/piso.png',
               texture_scale=(max(1, sx / 6), max(1, sz / 6)),
               shader=unlit_shader, collider='box', double_sided=True)
    f.texture.filtering = 'mipmap'
    return f


def _build_floor_plane(y, hole):
    """Piso texturizado. Con hole=(hx0,hx1,hz0,hz1) se arma en 4 tiras dejando
    ese hueco para la rampa; sin hole, un plano entero."""
    if hole is None:
        _floor_tile(0, 0, FLOOR_SIZE, FLOOR_SIZE, y)
        return
    hx0, hx1, hz0, hz1 = hole
    _floor_tile(0, (-_H + hz0) / 2, FLOOR_SIZE, hz0 + _H, y)      # Sur.
    _floor_tile(0, (hz1 + _H) / 2, FLOOR_SIZE, _H - hz1, y)       # Norte.
    _floor_tile((-_H + hx0) / 2, (hz0 + hz1) / 2, hx0 + _H, hz1 - hz0, y)  # O.
    _floor_tile((hx1 + _H) / 2, (hz0 + hz1) / 2, _H - hx1, hz1 - hz0, y)   # E.


def _build_walls(y):
    """4 muros perimetrales macizos, texturizados (tablones tileados)."""
    wy = y + FLOOR_WALL_H / 2
    t = 0.5
    tiles = max(1, round(FLOOR_SIZE / (FLOOR_WALL_H * WALL_ASPECT)))
    specs = [
        (Vec3(0, wy, _H), Vec3(FLOOR_SIZE, FLOOR_WALL_H, t)),
        (Vec3(0, wy, -_H), Vec3(FLOOR_SIZE, FLOOR_WALL_H, t)),
        (Vec3(_H, wy, 0), Vec3(t, FLOOR_WALL_H, FLOOR_SIZE)),
        (Vec3(-_H, wy, 0), Vec3(t, FLOOR_WALL_H, FLOOR_SIZE)),
    ]
    for pos, scale in specs:
        w = Entity(model='cube', position=pos, scale=scale, color=color.white,
                   texture='assets/ui/paredes.png', texture_scale=(tiles, 1),
                   shader=unlit_shader, collider='box')
        w.texture.filtering = 'mipmap'


def _in_corridor(lx, lz):
    """True si (lx,lz) cae en la columna de alguna escalera (a evitar)."""
    return abs(lx) < RAMP_WIDTH and 2.0 < abs(lz) < 24.0


def _build_cover(y, rng, floor_index):
    """Cajas y columnas de cobertura, evitando el centro (spawn en piso 0) y
    las columnas de las escaleras."""
    margin = _H - 4
    placed = 0
    tries = 0
    while placed < COVER_PER_FLOOR and tries < COVER_PER_FLOOR * 10:
        tries += 1
        lx = rng.uniform(-margin, margin)
        lz = rng.uniform(-margin, margin)
        if floor_index == 0 and lx * lx + lz * lz < 36:
            continue                         # No tapar el spawn.
        if _in_corridor(lx, lz):
            continue                         # No tapar las escaleras.
        if rng.random() < 0.6:               # Caja.
            s = rng.uniform(1.3, 2.4)
            size = Vec3(s, s, s)
        else:                                 # Columna.
            size = Vec3(1, rng.uniform(2.5, 4.0), 1)
        Entity(model='cube', position=Vec3(lx, y + size.y / 2, lz),
               scale=size, color=rng.choice(FLAT_PALETTE),
               shader=unlit_shader, collider='box')
        placed += 1


def _build_ramp(y, rc):
    """Rampa suave dentro del hueco de escalera, del piso y al de arriba."""
    rise = FLOOR_HEIGHT
    run = RAMP_SLOPE_RUN
    length = math.sqrt(run * run + rise * rise)
    angle = math.degrees(math.atan2(rise, run))
    mid_z = (rc['ramp_bot'] + rc['ramp_top']) / 2
    # Ancho un poco mayor que el hueco para que se meta bajo las paredes
    # laterales y NO queden rendijas por las que caer. El extremo ALTO va
    # junto al muro; el signo de la rotación depende del lado.
    Entity(model='cube', color=color.hsv(30, 0.10, 0.55), shader=unlit_shader,
           position=Vec3(0, y + rise / 2, mid_z),
           scale=Vec3(RAMP_WIDTH + 1.2, 0.3, length),
           rotation=Vec3(-rc['s'] * angle, 0, 0), collider='box')


def _build_shaft(y, rc):
    """Hueco de escalera: 2 paredes laterales (permanentes) + PARED de entrada
    (removible, de piso a techo). Devuelve la pared removible."""
    s = rc['s']
    entrance_z = rc['ramp_bot'] - s * 0.5            # Justo antes del pie.
    far_z = rc['hole'][3] if s > 0 else rc['hole'][2]  # Borde junto al muro.
    z0, z1 = sorted((entrance_z, far_z))
    length = z1 - z0
    mid_z = (z0 + z1) / 2
    wy = y + FLOOR_HEIGHT / 2
    tiles = max(1, round(length / (FLOOR_HEIGHT * WALL_ASPECT)))
    # Paredes laterales del hueco (permanentes): encierran la rampa.
    for x in (-_SHAFT_HX, _SHAFT_HX):
        w = Entity(model='cube', position=Vec3(x, wy, mid_z),
                   scale=Vec3(0.4, FLOOR_HEIGHT, length), color=color.white,
                   texture='assets/ui/paredes.png', texture_scale=(tiles, 1),
                   shader=unlit_shader, collider='box')
        w.texture.filtering = 'mipmap'
    # PARED DE FONDO (fondo del hueco, permanente): sin ella se podía rodear
    # y colarse por DEBAJO de la rampa. Bastante más baja que el techo para NO
    # estorbar al emerger arriba (el jugador sale a la altura del piso, por
    # encima de esta pared), pero suficiente para tapar el paso a ras de suelo.
    bh = FLOOR_HEIGHT - 1.5
    back = Entity(model='cube', position=Vec3(0, y + bh / 2, far_z),
                  scale=Vec3(RAMP_WIDTH + 1.0, bh, 0.4),
                  color=color.white, texture='assets/ui/paredes.png',
                  texture_scale=(1, 1), shader=unlit_shader, collider='box')
    back.texture.filtering = 'mipmap'
    # PARED de entrada: de piso a techo, tapa el acceso. Removible.
    gate = Entity(model='cube', color=GATE_COL, shader=unlit_shader,
                  position=Vec3(0, wy, entrance_z),
                  scale=Vec3(RAMP_WIDTH + 1.0, FLOOR_HEIGHT, 0.4),
                  collider='box')
    return gate


def build_archive():
    """Construye los 3 pisos. Devuelve (floors, gates):
      floors: lista de dicts {index, y}.
      gates:  {piso: [pared_removible]} para los pisos con rampa (0 y 1)."""
    rng = random.Random(WORLD_SEED)
    floors = []
    gates = {}
    for i in range(N_FLOORS):
        y = FLOOR_Y[i]
        # Hueco en el piso: por donde sube el piso de ABAJO (RAMP_SIDES[i-1]).
        hole = _corridor(RAMP_SIDES[i - 1])['hole'] if i > 0 else None
        _build_floor_plane(y, hole)
        _build_walls(y)
        _build_cover(y, rng, i)
        # Rampa hacia arriba (todos menos el último), en su lado.
        if i < N_FLOORS - 1:
            rc = _corridor(RAMP_SIDES[i])
            _build_ramp(y, rc)
            gates[i] = [_build_shaft(y, rc)]
        floors.append(dict(index=i, y=y))
    return floors, gates
