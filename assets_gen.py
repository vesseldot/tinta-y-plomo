"""
assets_gen.py — Genera con PIL los pocos placeholders que el juego aún usa y
que no son arte final: el "puff" de impacto, el atlas de armas del HUD, y tres
piezas de UI (cara del jefe, cartel y marco de la barra). El resto del arte
(enemigos, piso, paredes, cielo, vida, minimapa) vive como PNG reales en
assets/ y assets/ui/.

Se generan solo si faltan (coste cero en arranques siguientes). Cuando tengas
arte final para estas piezas, reemplaza el PNG en assets/ y listo.
"""

from pathlib import Path

from PIL import Image, ImageDraw

ASSET_DIR = Path(__file__).parent / 'assets'

FRAME = 64          # Lado del icono cuadrado del jefe.

# Paleta plana "noir a lápiz".
INK = (25, 22, 28, 255)          # Contorno "a tinta".
GRAY_LIGHT = (215, 215, 215, 255)
GRAY_MED = (150, 150, 150, 255)


def _to_gray(img: Image.Image) -> Image.Image:
    """Convierte a escala de grises CONSERVANDO el canal alfa (look 'película
    antigua' sin redibujar; sigue siendo un RGBA del mismo tamaño)."""
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
    """Ametralladora estilo 'tommy gun': cuerpo + tambor + 2 empuñaduras."""
    steel = (95, 100, 115, 255)
    wood = (110, 70, 45, 255)
    d.rectangle([ox + 20, 24, ox + 108, 40], fill=steel, outline=INK, width=3)
    d.ellipse([ox + 48, 42, ox + 76, 70], fill=wood, outline=INK, width=3)
    d.polygon([(ox + 84, 40), (ox + 104, 40), (ox + 114, 80), (ox + 94, 82)],
              fill=wood, outline=INK)
    d.rectangle([ox + 28, 40, ox + 40, 64], fill=wood, outline=INK, width=3)


def _draw_shotgun(d: ImageDraw.ImageDraw, ox: int):
    """Escopeta de cañón largo con bomba (pump)."""
    steel = (105, 110, 125, 255)
    wood = (110, 70, 45, 255)
    d.rectangle([ox + 12, 24, ox + 100, 34], fill=steel, outline=INK, width=3)
    d.rectangle([ox + 30, 40, ox + 62, 54], fill=wood, outline=INK, width=3)
    d.polygon([(ox + 88, 34), (ox + 112, 36), (ox + 118, 84), (ox + 96, 86)],
              fill=wood, outline=INK)
    d.arc([ox + 74, 38, ox + 92, 58], 200, 340, fill=INK, width=3)


def _make_guns_sheet(path: Path):
    """Atlas de las 3 armas (128px por frame), EN GRIS. Cambiar de arma =
    mover texture_offset; una sola textura para la mano y el HUD."""
    img = Image.new('RGBA', (128 * 3, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _draw_revolver(d, 0)
    _draw_tommy(d, 128)
    _draw_shotgun(d, 256)
    _to_gray(img).save(path)


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


def _make_ui_sign(path: Path):
    """Cartel colgante del jefe: dos cuerdas + placa con doble borde."""
    img = Image.new('RGBA', (128, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([30, 0, 38, 30], fill=INK, width=3)     # Cuerdas.
    d.line([98, 0, 90, 30], fill=INK, width=3)
    d.rectangle([8, 30, 120, 88], fill=GRAY_LIGHT, outline=INK, width=4)
    d.rectangle([14, 36, 114, 82], outline=GRAY_MED, width=2)
    img.save(path)


def _make_ui_bar_frame(path: Path):
    """Marco de la barra de jefe: borde + divisores de 10 segmentos.

    El relleno es OTRO quad detrás que solo cambia scale_x: la barra
    'segmentada' completa son 2 quads y cero redibujado de texturas."""
    img = Image.new('RGBA', (256, 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 255, 39], outline=INK, width=4)
    for i in range(1, 10):                       # 10 segmentos.
        x = int(i * 25.6)
        d.line([x, 3, x, 36], fill=INK, width=3)
    img.save(path)


def _make_puff(path: Path):
    """Nube de impacto: círculo blanco semitransparente con contorno."""
    img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([3, 3, 29, 29], fill=(245, 240, 230, 200), outline=INK, width=2)
    d.ellipse([10, 10, 22, 22], fill=(255, 255, 255, 230))
    img.save(path)


def ensure_assets():
    """Crea assets/ y los PNG placeholder solo si faltan."""
    ASSET_DIR.mkdir(exist_ok=True)
    targets = {
        ASSET_DIR / 'puff.png': _make_puff,
        ASSET_DIR / 'guns_sheet.png': _make_guns_sheet,
        ASSET_DIR / 'ui_boss_face.png': _make_boss_face,
        ASSET_DIR / 'ui_sign.png': _make_ui_sign,
        ASSET_DIR / 'ui_bar_frame.png': _make_ui_bar_frame,
    }
    for path, maker in targets.items():
        if not path.exists():
            maker(path)


if __name__ == '__main__':
    ensure_assets()
    print(f'Assets generados en {ASSET_DIR}')
