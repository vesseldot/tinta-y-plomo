"""
assets_gen.py — Genera los sprites placeholder (estilo flat / cel-shading)
con PIL (Pillow, dependencia que Ursina ya trae) la primera vez que se corre.

¿Por qué generar los assets por código?
  1. El proyecto corre "out of the box" sin descargar nada.
  2. Demuestra el formato correcto que deben tener tus sprites finales:
     - Colores PLANOS + contorno oscuro (look "dibujado a mano", sin iluminación).
     - Atlas horizontal de 8 frames para las 8 direcciones (UNA sola textura
       por enemigo = UNA sola llamada de textura, en vez de 8 texturas sueltas).
  3. Texturas pequeñas (64px por frame): en hardware de gama baja el ancho de
     banda de memoria de la GPU es el cuello de botella típico; texturas chicas
     + filtrado 'nearest' mantienen el estilo pixel/cartoon y son gratis.

Cuando tengas arte real (estilo "Mouse: P.I. for Hire"), solo reemplaza los
PNG en assets/ respetando el mismo layout de atlas.
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw

ASSET_DIR = Path(__file__).parent / 'assets'

FRAME = 64          # Lado de cada frame del atlas.
DIRECTIONS = 8      # 8 direcciones -> atlas de 512x64.

# Paleta plana estilo "noir a lápiz": pocos colores, sin degradados.
INK = (25, 22, 28, 255)          # Contorno "a tinta".
COAT = (120, 96, 70, 255)        # Gabardina.
COAT_SHADE = (96, 76, 56, 255)   # Sombra PLANA (un solo tono, sin gradiente = cel-shading).
SKIN = (210, 190, 170, 255)
HAT = (60, 55, 65, 255)


def _draw_enemy_frame(draw: ImageDraw.ImageDraw, ox: int, angle_deg: float):
    """Dibuja un detective/matón visto desde un ángulo dado.

    Simulamos el "volumen" desplazando la cara y el brazo según el ángulo:
    es la misma técnica que usarás con arte real (un dibujo por dirección).
    angle_deg = 0 -> el enemigo mira hacia la cámara (vista frontal).
    """
    rad = math.radians(angle_deg)
    fx = math.sin(rad)            # -1..1: cuánto "gira" el personaje.
    facing_away = math.cos(rad) < -0.2   # De espaldas: no se dibuja la cara.

    cx = ox + FRAME // 2

    # Cuerpo (gabardina): elipse plana con contorno.
    draw.ellipse([cx - 14, 26, cx + 14, 58], fill=COAT, outline=INK, width=2)
    # Sombra lateral PLANA para fingir volumen (cel-shading de 2 tonos).
    shade_w = int(8 * abs(fx))
    if shade_w > 1:
        side = cx + (10 if fx > 0 else -10 - shade_w)
        draw.ellipse([side, 30, side + shade_w + 4, 56], fill=COAT_SHADE)

    # Cabeza.
    head_dx = int(fx * 5)
    draw.ellipse([cx - 9 + head_dx, 8, cx + 9 + head_dx, 26],
                 fill=SKIN, outline=INK, width=2)
    # Sombrero de detective (ala + copa).
    draw.ellipse([cx - 13 + head_dx, 12, cx + 13 + head_dx, 19], fill=HAT, outline=INK)
    draw.rectangle([cx - 8 + head_dx, 5, cx + 8 + head_dx, 15], fill=HAT, outline=INK)

    # Cara solo si no está de espaldas (ojos = 2 puntos, estilo cartoon).
    if not facing_away:
        eye_dx = int(fx * 6)
        draw.ellipse([cx - 5 + eye_dx, 19, cx - 2 + eye_dx, 22], fill=INK)
        draw.ellipse([cx + 2 + eye_dx, 19, cx + 5 + eye_dx, 22], fill=INK)


def _make_enemy_sheet(path: Path):
    """Atlas 8-direcciones: frame i = ángulo relativo i*45° respecto a la cámara."""
    img = Image.new('RGBA', (FRAME * DIRECTIONS, FRAME), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for i in range(DIRECTIONS):
        _draw_enemy_frame(draw, i * FRAME, i * 45)
    img.save(path)


# Paleta EN ESCALA DE GRISES para toda la UI (estilo película de los 30).
GRAY_LIGHT = (215, 215, 215, 255)
GRAY_MED = (150, 150, 150, 255)
GRAY_DARK = (80, 80, 80, 255)


def _to_gray(img: Image.Image) -> Image.Image:
    """Convierte a escala de grises CONSERVANDO el canal alfa.

    Así cualquier dibujo se vuelve 'película antigua' sin redibujarlo, y la
    GPU no nota diferencia: sigue siendo un RGBA del mismo tamaño.
    """
    return img.convert('LA').convert('RGBA')


def _draw_revolver(d: ImageDraw.ImageDraw, ox: int):
    steel = (105, 110, 125, 255)
    steel_hi = (140, 146, 160, 255)
    wood = (110, 70, 45, 255)
    d.rectangle([ox + 44, 18, ox + 84, 34], fill=steel, outline=INK, width=3)
    d.rectangle([ox + 48, 21, ox + 80, 25], fill=steel_hi)   # Brillo PLANO.
    d.ellipse([ox + 56, 30, ox + 84, 56], fill=steel, outline=INK, width=3)
    d.polygon([(ox + 70, 50), (ox + 98, 50), (ox + 112, 90), (ox + 86, 92)],
              fill=wood, outline=INK)
    d.arc([ox + 66, 52, ox + 84, 70], 200, 340, fill=INK, width=3)


def _draw_tommy(d: ImageDraw.ImageDraw, ox: int):
    """Ametralladora estilo 'tommy gun' de gánster: cuerpo + tambor + 2 empuñaduras."""
    steel = (95, 100, 115, 255)
    wood = (110, 70, 45, 255)
    d.rectangle([ox + 20, 24, ox + 108, 40], fill=steel, outline=INK, width=3)   # Cuerpo/cañón.
    d.ellipse([ox + 48, 42, ox + 76, 70], fill=wood, outline=INK, width=3)       # Tambor.
    d.polygon([(ox + 84, 40), (ox + 104, 40), (ox + 114, 80), (ox + 94, 82)],
              fill=wood, outline=INK)                                            # Empuñadura trasera.
    d.rectangle([ox + 28, 40, ox + 40, 64], fill=wood, outline=INK, width=3)     # Empuñadura frontal.


def _draw_shotgun(d: ImageDraw.ImageDraw, ox: int):
    """Escopeta de cañón largo con bomba (pump)."""
    steel = (105, 110, 125, 255)
    wood = (110, 70, 45, 255)
    d.rectangle([ox + 12, 24, ox + 100, 34], fill=steel, outline=INK, width=3)   # Cañón largo.
    d.rectangle([ox + 30, 40, ox + 62, 54], fill=wood, outline=INK, width=3)     # Bomba.
    d.polygon([(ox + 88, 34), (ox + 112, 36), (ox + 118, 84), (ox + 96, 86)],
              fill=wood, outline=INK)                                            # Culata.
    d.arc([ox + 74, 38, ox + 92, 58], 200, 340, fill=INK, width=3)               # Gatillo.


def _make_gun(path: Path):
    """(Compat) Revólver suelto; el juego ahora usa guns_sheet.png."""
    img = Image.new('RGBA', (128, 96), (0, 0, 0, 0))
    _draw_revolver(ImageDraw.Draw(img), 0)
    img.save(path)


def _make_guns_sheet(path: Path):
    """Atlas de las 3 armas (128px por frame), EN GRIS.

    Igual que las 8 direcciones del enemigo: cambiar de arma = mover
    texture_offset. Una sola textura compartida entre la mano y el HUD.
    """
    img = Image.new('RGBA', (128 * 3, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _draw_revolver(d, 0)
    _draw_tommy(d, 128)
    _draw_shotgun(d, 256)
    _to_gray(img).save(path)


def _make_ui_icons(path: Path):
    """Atlas 3x64: corazón (vida), gota (tinta), nube (cordura). Gris + tinta."""
    img = Image.new('RGBA', (FRAME * 3, FRAME), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Corazón: dos círculos + triángulo, estilo cartoon.
    cx = FRAME // 2
    d.ellipse([cx - 20, 14, cx + 2, 36], fill=GRAY_LIGHT, outline=INK, width=3)
    d.ellipse([cx - 2, 14, cx + 20, 36], fill=GRAY_LIGHT, outline=INK, width=3)
    d.polygon([(cx - 17, 32), (cx + 17, 32), (cx, 54)], fill=GRAY_LIGHT,
              outline=INK)
    # Gota.
    cx = FRAME + FRAME // 2
    d.polygon([(cx, 8), (cx - 13, 34), (cx + 13, 34)], fill=GRAY_LIGHT,
              outline=INK)
    d.ellipse([cx - 14, 26, cx + 14, 54], fill=GRAY_LIGHT, outline=INK, width=3)
    # Nube (3 círculos solapados).
    cx = FRAME * 2 + FRAME // 2
    d.ellipse([cx - 22, 26, cx + 2, 50], fill=GRAY_LIGHT, outline=INK, width=3)
    d.ellipse([cx - 6, 16, cx + 20, 44], fill=GRAY_LIGHT, outline=INK, width=3)
    d.ellipse([cx + 2, 28, cx + 24, 50], fill=GRAY_LIGHT, outline=INK, width=3)
    img.save(path)


def _make_ui_oval(path: Path):
    """Contenedor ovalado para los valores numéricos."""
    img = Image.new('RGBA', (96, 48), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([2, 2, 94, 46], fill=GRAY_LIGHT, outline=INK, width=3)
    img.save(path)


def _make_boss_face(path: Path):
    """Icono circular del jefe: cara enojada rubber hose en gris."""
    img = Image.new('RGBA', (FRAME, FRAME), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([2, 2, 62, 62], fill=GRAY_MED, outline=INK, width=4)
    d.line([16, 20, 28, 28], fill=INK, width=4)    # Cejas en V (furia).
    d.line([48, 20, 36, 28], fill=INK, width=4)
    d.ellipse([22, 26, 30, 34], fill=INK)
    d.ellipse([34, 26, 42, 34], fill=INK)
    d.arc([20, 38, 44, 56], 200, 340, fill=INK, width=4)   # Boca gruñendo.
    img.save(path)


def _make_ui_ring(path: Path):
    """Aro del retrato: círculo hueco (el rostro se ve por el centro)."""
    img = Image.new('RGBA', (96, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([3, 3, 93, 93], outline=INK, width=7)
    d.ellipse([9, 9, 87, 87], outline=GRAY_LIGHT, width=3)
    img.save(path)


def _make_ui_sign(path: Path):
    """Cartel colgante del jefe: dos cuerdas + placa con doble borde."""
    img = Image.new('RGBA', (128, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([30, 0, 38, 30], fill=INK, width=3)     # Cuerdas.
    d.line([98, 0, 90, 30], fill=INK, width=3)
    d.rectangle([8, 30, 120, 88], fill=GRAY_LIGHT, outline=INK, width=4)
    d.rectangle([14, 36, 114, 82], outline=GRAY_MED, width=2)
    img.save(path)


def _make_ui_plate(path: Path):
    """Placa del retrato: banda con extremos en punta (estilo listón)."""
    img = Image.new('RGBA', (128, 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(0, 20), (14, 4), (114, 4), (128, 20), (114, 36), (14, 36)],
              fill=GRAY_LIGHT, outline=INK)
    img.save(path)


def _make_ui_bar_frame(path: Path):
    """Marco de la barra de jefe: borde + divisores de 10 segmentos.

    El relleno es OTRO quad detrás que solo cambia scale_x: la barra
    'segmentada' completa son 2 quads y cero redibujado de texturas.
    """
    img = Image.new('RGBA', (256, 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 255, 39], outline=INK, width=4)
    for i in range(1, 10):                       # 10 segmentos.
        x = int(i * 25.6)
        d.line([x, 3, x, 36], fill=INK, width=3)
    img.save(path)


def _make_faces(path: Path, gray=False):
    """Atlas de 3 rostros del detective para el HUD (sano/herido/crítico).

    Mismo truco que los enemigos: UN atlas + texture_offset. Cambiar de
    rostro al recibir daño es mover UVs, jamás cargar otra textura.
    Con gray=True se guarda en escala de grises (UI estilo película).
    """
    img = Image.new('RGBA', (FRAME * 3, FRAME), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(3):
        cx = i * FRAME + FRAME // 2
        # Cara + sombrero (mismo lenguaje visual que el enemy_sheet).
        d.ellipse([cx - 20, 16, cx + 20, 56], fill=SKIN, outline=INK, width=3)
        d.ellipse([cx - 24, 8, cx + 24, 20], fill=HAT, outline=INK)
        d.rectangle([cx - 14, 1, cx + 14, 14], fill=HAT, outline=INK)
        if i == 0:      # Sano: ojos abiertos + sonrisa.
            d.ellipse([cx - 10, 28, cx - 4, 34], fill=INK)
            d.ellipse([cx + 4, 28, cx + 10, 34], fill=INK)
            d.arc([cx - 10, 34, cx + 10, 50], 20, 160, fill=INK, width=3)
        elif i == 1:    # Herido: ojos entrecerrados + boca recta.
            d.line([cx - 11, 30, cx - 3, 32], fill=INK, width=3)
            d.line([cx + 3, 32, cx + 11, 30], fill=INK, width=3)
            d.line([cx - 8, 45, cx + 8, 45], fill=INK, width=3)
        else:           # Crítico: ojos en X + boca de preocupación (rubber hose puro).
            for sx in (-10, 4):
                d.line([cx + sx, 28, cx + sx + 6, 34], fill=INK, width=3)
                d.line([cx + sx + 6, 28, cx + sx, 34], fill=INK, width=3)
            d.arc([cx - 9, 42, cx + 9, 54], 200, 340, fill=INK, width=3)
    if gray:
        img = _to_gray(img)
    img.save(path)


def _make_puff(path: Path):
    """Nube de impacto: círculo blanco semitransparente con contorno."""
    img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([3, 3, 29, 29], fill=(245, 240, 230, 200), outline=INK, width=2)
    d.ellipse([10, 10, 22, 22], fill=(255, 255, 255, 230))
    img.save(path)


def ensure_assets():
    """Crea assets/ y los PNG solo si faltan (coste cero en arranques siguientes)."""
    ASSET_DIR.mkdir(exist_ok=True)
    targets = {
        ASSET_DIR / 'enemy_sheet.png': _make_enemy_sheet,
        ASSET_DIR / 'gun.png': _make_gun,
        ASSET_DIR / 'puff.png': _make_puff,
        ASSET_DIR / 'hud_faces.png': _make_faces,
        ASSET_DIR / 'ui_faces.png': lambda p: _make_faces(p, gray=True),
        ASSET_DIR / 'guns_sheet.png': _make_guns_sheet,
        ASSET_DIR / 'ui_icons.png': _make_ui_icons,
        ASSET_DIR / 'ui_oval.png': _make_ui_oval,
        ASSET_DIR / 'ui_boss_face.png': _make_boss_face,
        ASSET_DIR / 'ui_ring.png': _make_ui_ring,
        ASSET_DIR / 'ui_sign.png': _make_ui_sign,
        ASSET_DIR / 'ui_plate.png': _make_ui_plate,
        ASSET_DIR / 'ui_bar_frame.png': _make_ui_bar_frame,
    }
    for path, maker in targets.items():
        if not path.exists():
            maker(path)


if __name__ == '__main__':
    ensure_assets()
    print(f'Assets generados en {ASSET_DIR}')
