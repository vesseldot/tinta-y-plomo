"""
world.py — Generación del mapa 3D low-poly y sistema de culling por sectores.

ESTRATEGIA DE DRAW CALLS
------------------------
El coste #1 en GPUs integradas no suele ser la cantidad de polígonos sino la
cantidad de DRAW CALLS (cada Entity con su propio modelo = 1 llamada al
driver). Un mapa con 200 cajas sueltas = 200 draw calls.

Solución: dividir el mapa en SECTORES y fusionar toda la geometría estática
de cada sector en UNA sola malla con Entity.combine():
    ~200 draw calls  ->  ~36 draw calls (1 por sector).
Todos los sectores comparten LA MISMA textura ('white_cube') y la variedad
visual se logra con COLOR DE VÉRTICE (que combine() conserva): así el driver
tampoco cambia de textura entre llamadas.

ESTRATEGIA DE CULLING
---------------------
1. Frustum culling: Panda3D (el motor debajo de Ursina) ya descarta en C++
   cualquier nodo fuera del cono de visión de la cámara. Al agrupar por
   sectores le damos nodos "grandes" fáciles de descartar de golpe.
2. Occlusion/distancia (manual): Panda3D no trae occlusion culling real, así
   que lo aproximamos: cada 0.25 s (¡no cada frame!) se desactivan los
   sectores más lejos de RENDER_DISTANCE. Un sector deshabilitado no entra
   ni siquiera al recorrido de escena. La niebla (main.py) esconde el corte.
3. Los COLLIDERS viven en entidades invisibles SEPARADAS que nunca se
   cullean: la física no se rompe aunque el visual esté apagado, y un box
   collider sin modelo no cuesta nada de render.
"""

import random

from ursina import Entity, Vec3, camera, color, load_texture, time
from ursina.shaders import unlit_shader

from config import (CULL_INTERVAL, MAP_SIZE, RENDER_DISTANCE, SECTOR_SIZE,
                    SKY_DIST, WORLD_SEED)

# Paleta plana "a lápiz": tonos desaturados que combinan con sprites cel-shaded.
FLAT_PALETTE = [
    color.hsv(30, 0.25, 0.75),   # arena
    color.hsv(220, 0.15, 0.55),  # gris azulado
    color.hsv(20, 0.35, 0.5),    # ladrillo apagado
    color.hsv(100, 0.2, 0.6),    # verde grisáceo
]


def _add_box(sector, colliders_root, local_pos, size, col):
    """Caja visual (hija del sector, se fusionará) + collider invisible aparte."""
    Entity(parent=sector, model='cube', position=local_pos, scale=size, color=col)
    Entity(parent=colliders_root, collider='box', visible=False,
           position=sector.position + local_pos, scale=size)


def build_sky():
    """Cielo como CÚPULA esférica: una esfera gigante forrada con el cielo
    tormentoso (assets/ui/fondo.png) que envuelve TODO el nivel.

    Frente a la caja anterior, la esfera no tiene esquinas ni costuras de
    paredes: el cielo se curva de forma continua alrededor del jugador,
    como un domo de planetario. Sigue ESTÁTICA en el mundo (no anclada a la
    cámara), así que al caminar hay paralaje y se siente física.

    Presupuesto: 1 sola Entity = 1 draw call y CERO updates por frame
    (Panda3D no recorre un nodo estático que no cambia). Una malla esférica
    de baja resolución es despreciable para cualquier GPU.

    Notas de render:
      - double_sided=True: la esfera se ve desde DENTRO (sus caras miran
        hacia afuera; sin esto, el backface culling la volvería invisible).
      - setFogOff(1): a 50+ u la niebla lineal (45..85) la teñiría; excluida
        a nivel de nodo, el cielo se ve nítido y el mundo 3D se desvanece
        HACIA su horizonte.
      - Radio = SKY_DIST < FAR_CLIP: la cúpula entra entera en el frustum.
      - unlit_shader: sin luces, el color de la acuarela llega crudo.
    """
    tex = load_texture('assets/ui/fondo.png')
    # Centrada en el origen y a la ALTURA DEL OJO del jugador (~2 u): así el
    # horizonte de la esfera (su ecuador) coincide con la línea del suelo y
    # las nubes de tormenta quedan arriba, como un cielo real.
    sky = Entity(model='sphere', texture=tex,
                 position=Vec3(0, 2, 0), scale=SKY_DIST * 2,
                 double_sided=True, shader=unlit_shader)
    sky.setFogOff(1)

    # ---- Tapa del cenit ----
    # Toda esfera UV "pellizca" su textura en los polos (converge a un punto).
    # El polo superior queda justo sobre el jugador, así que al mirar arriba
    # se vería ese vórtice. Un quad horizontal de nube plana lo oculta: se
    # interpone entre el jugador y el polo. Color = gris claro de la nube
    # alta (medido con PIL en la banda del polo), para fundirse con el cielo
    # que lo rodea. (El polo inferior queda bajo el suelo, invisible.)
    cap = Entity(model='quad', color=color.hsv(0, 0.005, 0.86),
                 position=Vec3(0, 2 + SKY_DIST * 0.9, 0), rotation_x=90,
                 scale=SKY_DIST * 1.1, double_sided=True, shader=unlit_shader)
    cap.setFogOff(1)
    return [sky, cap]


def build_world():
    """Construye piso, muros perimetrales y sectores de escenografía.

    Devuelve la lista de sectores para que SectorCuller los administre.
    """
    random.seed(WORLD_SEED)  # Mapa determinista: mismo layout en cada corrida.

    # ---- Piso: UN solo plano con textura repetida (texture_scale) ----
    # Placa metálica dibujada a tinta (assets/ui/piso.png). 1 entity +
    # 1 textura tileada = 1 draw call para todo el suelo. Cada baldosa mide
    # ~6 unidades; MAP_SIZE/6 repeticiones cubren el mapa sin estirar el
    # dibujo. unlit_shader: sin luces, el gris del arte llega crudo (misma
    # estética plana que el resto).
    floor = Entity(model='plane', scale=(MAP_SIZE, 1, MAP_SIZE),
                   texture='assets/ui/piso.png',
                   texture_scale=(MAP_SIZE / 6, MAP_SIZE / 6),
                   shader=unlit_shader, collider='box')
    # Mipmaps: sin ellos, las líneas de tinta del piso lejano hierven
    # (aliasing) y en gama baja se nota muchísimo. La GPU elige el nivel
    # por distancia; costo cero por frame.
    floor.texture.filtering = 'mipmap'

    # ---- Muros perimetrales: 4 cubos estirados, siempre visibles ----
    # Cerca de tablones dibujados a tinta (assets/ui/paredes.png). El muro
    # mide MAP_SIZE x 4 y el arte es 1408x768: si se estirara a lo largo,
    # los tablones quedarían de metros de ancho. texture_scale lo TILEA
    # horizontalmente las veces justas para conservar la proporción del
    # dibujo (tilear UVs es gratis: misma textura, mismo draw call).
    half = MAP_SIZE / 2
    wall_h = 4
    tiles = round(MAP_SIZE / (wall_h * 1408 / 768))   # ≈10 repeticiones.
    for pos, scale in (
        ((0, 2, half), (MAP_SIZE, wall_h, 1)),
        ((0, 2, -half), (MAP_SIZE, wall_h, 1)),
        ((half, 2, 0), (1, wall_h, MAP_SIZE)),
        ((-half, 2, 0), (1, wall_h, MAP_SIZE)),
    ):
        wall = Entity(model='cube', position=pos, scale=scale,
                      color=color.white, texture='assets/ui/paredes.png',
                      texture_scale=(tiles, 1), collider='box')
    # Mipmaps para la cerca: las líneas finas de tinta parpadean (aliasing)
    # al verse de lejos; el mipmapping lo resuelve EN LA GPU eligiendo una
    # versión reducida de la textura según la distancia. Costo: +33% de
    # memoria de ESA textura, cero costo por frame. (La textura es
    # compartida: basta configurarla una vez.)
    wall.texture.filtering = 'mipmap'

    # ---- Sectores de escenografía (cajas, columnas) ----
    colliders_root = Entity()   # Padre de todos los colliders invisibles.
    sectors = []
    steps = range(int(-half), int(half), SECTOR_SIZE)
    for sx in steps:
        for sz in steps:
            center = Vec3(sx + SECTOR_SIZE / 2, 0, sz + SECTOR_SIZE / 2)
            sector = Entity(position=center)

            for _ in range(random.randint(2, 4)):
                if random.random() < 0.6:   # Caja / crate.
                    s = random.uniform(1.0, 2.2)
                    size = Vec3(s, s, s)
                else:                        # Columna.
                    size = Vec3(1, random.uniform(3, 5), 1)
                lx = random.uniform(-SECTOR_SIZE / 2 + 2, SECTOR_SIZE / 2 - 2)
                lz = random.uniform(-SECTOR_SIZE / 2 + 2, SECTOR_SIZE / 2 - 2)
                _add_box(sector, colliders_root, Vec3(lx, size.y / 2, lz),
                         size, random.choice(FLAT_PALETTE))

            # LA optimización clave: N cubos hijos -> 1 sola malla/draw call.
            # auto_destroy=True elimina los Entities hijos: dejan de existir
            # en Python (menos objetos que recorrer por frame).
            sector.combine(auto_destroy=True)
            sector.texture = 'white_cube'
            sectors.append(sector)

    return sectors


class SectorCuller(Entity):
    """Desactiva sectores lejanos. Corre a baja frecuencia (CULL_INTERVAL).

    Recorrer ~36 sectores 4 veces por segundo es despreciable para la CPU;
    hacerlo cada frame sería pagar 60 veces por segundo por la misma info.
    """

    def __init__(self, sectors):
        super().__init__()
        self.sectors = sectors
        self._timer = 0.0
        # Distancia al CUADRADO: evita la raíz cuadrada en el bucle caliente.
        self._max_dist_sq = RENDER_DISTANCE * RENDER_DISTANCE

    def update(self):
        self._timer += time.dt
        if self._timer < CULL_INTERVAL:
            return
        self._timer = 0.0

        cam = camera.world_position
        for sector in self.sectors:
            offset = sector.position - cam
            dist_sq = offset.x * offset.x + offset.z * offset.z
            enabled = dist_sq < self._max_dist_sq
            if sector.enabled != enabled:    # Solo tocar el scene graph si cambió.
                sector.enabled = enabled
