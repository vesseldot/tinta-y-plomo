"""
ui.py — GameHUD estilo 'Rubber Hose' años 30 (escala de grises).

LAYOUT (según boceto de diseño)
-------------------------------
    ┌─────────────────────────────────────────────┐
    │        [◉ ████████░░ ]  <cartel>     (poción) │  jefe/oleada · vida
    │                                             │
    │                                             │
    │  ┌────────┐                          ▄▄▄    │
    │  │minimapa│                         (arma)  │
    │  └────────┘                          6/24   │  minimapa · arma+munición
    └─────────────────────────────────────────────┘

REGLAS DE RENDIMIENTO (gama baja)
---------------------------------
1. UI por EVENTOS: asignar Text.text reconstruye la malla del texto, así
   que SOLO se asigna dentro de los métodos update_* (que se llaman cuando
   un valor cambia, jamás por frame).
2. MINIMAPA SIN SEGUNDA CÁMARA (prohibida: duplicaría el render de la
   escena). Matemática pura: coordenadas (X, Z) de mundo -> (X, Y) locales
   del marco:   local = (pos_mundo - pos_jugador) * (0.5 / RADIO)
   El jugador queda al centro; sus puntos son un pool FIJO creado una vez.
   El refresco corre a ~6 Hz (MINIMAP_INTERVAL), no a 60.
3. Arte estático de assets/ui/ precargado: la vida (3 estados de la poción)
   y las armas (una textura por arma) son texturas SUELTAS. Cambiar de
   estado/arma es un swap de referencia, y ocurre solo en EVENTOS (cruzar
   un umbral de vida, recoger un arma), nunca por frame -> el rebind es
   despreciable. Se precargan con load_texture para que el primer cambio
   en combate no cause un tirón.
4. Jerarquía plana: todo cuelga del HUD o de un grupo por bloque
   (boss_group) para encender/apagar secciones con UN enabled.
5. El resto de la UI (jefe, minimapa, munición) sigue con placeholders
   generados por assets_gen.py, sustituibles por arte final.

INSTANCIACIÓN EN main.py (sin sobrecargar el update)
----------------------------------------------------
    hud = GameHUD(player, weapon, enemies.pool.items, loot.crates)
    hud.bind_boss(enemies.boss)
Se crea UNA vez tras construir los sistemas. El HUD se auto-conecta a los
callbacks (on_hp_changed, on_ammo_changed, on_weapon_changed): nadie lo
consulta por frame. Su único update() propio es el temporizador del
minimapa: un float y una comparación por frame; el trabajo real ocurre
6 veces por segundo.
"""

from ursina import (Entity, Text, Vec2, Vec3, camera, color, load_texture,
                    time, window)

from config import (MINIMAP_INTERVAL, MINIMAP_RADIUS, MINIMAP_SIZE, WEAPONS)

# ---- Assets estáticos de UI (arte final rubber-hose en gris) ----
# Viven en assets/ui/. Son texturas SUELTAS (una por arma, una por estado
# de vida), no atlas. Cambiar de arma/estado = swap de textura; como solo
# ocurre en EVENTOS (recoger arma, cruzar un umbral de vida), no por frame,
# el rebind es despreciable. Se precargan en __init__ con load_texture
# (cacheada) para que el primer cambio en combate no cause un hitch.
UI_DIR = 'assets/ui/'
WEAPON_ASPECT = 677 / 369   # Proporción real del arte de armas.
MAX_LIVES = 3               # Umbrales de vida: máxima (3) / media (2) / baja (1).
BOSS_BAR_W = 0.46           # Ancho de la barra superior en unidades de UI.
BOSS_BAR_H = 0.035

# ---- Regiones de arte (píxeles sobre el lienzo 677x369) ----
# Los PNG traen márgenes transparentes; recortamos por UV al recuadro real
# del dibujo (medido con PIL) para que el arte llene su quad sin deformarse.
# Recortar por UV = mover texture_offset/scale: cero coste, cero re-cargas.
TEX_W, TEX_H = 677, 369
LIFE_REGIONS = {                       # Estado -> (archivo, recuadro).
    3: ('vida_maxima', (133, 4, 524, 354)),   # Confiado, con puro.
    2: ('vida_media', (129, 4, 518, 354)),    # Golpeado y furioso.
    1: ('vida_baja', (149, 3, 517, 364)),     # Hecho polvo, sombrero roto.
}
MINIMAP_REGION = (166, 15, 511, 355)   # Círculo del plano (casi cuadrado).
ICON_PLAYER = (45, 90, 224, 276)       # Perro detective.
ICON_ENEMY = (265, 105, 430, 270)      # Carita.
ICON_BOSS = (474, 105, 639, 270)       # Carita con X: el jefe marcado.
MAP_USABLE = 0.78                      # Fracción interior del aro utilizable.


def _sized(width, aspect):
    """Escala (w, h) que respeta la proporción del arte para no deformarlo."""
    return (width, width / aspect)


def _apply_region(entity, region):
    """Muestra solo un recuadro de la textura vía UV (offset/scale).

    OJO: las UV tienen origen abajo-izquierda; los píxeles, arriba-izquierda.
    """
    x0, y0, x1, y1 = region
    entity.texture_scale = Vec2((x1 - x0) / TEX_W, (y1 - y0) / TEX_H)
    entity.texture_offset = Vec2(x0 / TEX_W, 1 - y1 / TEX_H)


def _region_size(width, region):
    """Escala (w, h) de quad con la proporción del recuadro de arte."""
    x0, y0, x1, y1 = region
    return (width, width * (y1 - y0) / (x1 - x0))


class GameHUD(Entity):

    def __init__(self, player, weapon, enemies, crates):
        super().__init__(parent=camera.ui)
        self.player = player

        # camera.ui mide 1 de alto y aspect_ratio de ancho.
        left = -window.aspect_ratio / 2
        right = window.aspect_ratio / 2

        # ========== PROGRESO DE OLEADA / JEFE (arriba al centro) ==========
        # Grupo propio: mostrar/ocultar toda la barra cuesta UN enabled.
        self.boss_group = Entity(parent=self, y=0.42, enabled=False)
        Entity(parent=self.boss_group, model='quad',
               texture='assets/ui_boss_face.png', scale=0.1,
               position=Vec3(-0.30, 0, 0))
        # Relleno con origin en el borde izquierdo: el progreso/vida se
        # "vacía" hacia la derecha cambiando SOLO scale_x (un quad sin
        # textura, cero redibujos).
        self.boss_fill = Entity(parent=self.boss_group, model='quad',
                                origin=(-0.5, 0), color=color.light_gray,
                                position=Vec3(0.03 - BOSS_BAR_W / 2, 0, 0),
                                scale=(BOSS_BAR_W, BOSS_BAR_H))
        # Marco con los 10 segmentos DIBUJADOS EN LA TEXTURA (1 solo quad).
        Entity(parent=self.boss_group, model='quad',
               texture='assets/ui_bar_frame.png',
               position=Vec3(0.03, 0, -0.01),
               scale=(BOSS_BAR_W + 0.01, BOSS_BAR_H + 0.012))
        # Cartel colgante con el nombre del jefe / la oleada.
        Entity(parent=self.boss_group, model='quad',
               texture='assets/ui_sign.png', scale=(0.2, 0.15),
               position=Vec3(0.03, -0.105, 0))
        self.boss_name = Text(parent=self.boss_group, text='', scale=0.9,
                              origin=(0, 0), color=color.black,
                              position=Vec3(0.03, -0.125, -0.02))

        # ============= VIDA DEL JUGADOR (arriba a la derecha) =============
        # Retrato del detective (arte rubber-hose): UN indicador cuyo
        # sprite cambia con el daño — confiado, golpeado, hecho polvo.
        # Las 3 texturas se precargan; cambiar de estado es un swap de
        # referencia + recorte UV, solo cuando la vida cruza un umbral.
        self._life_tex = {state: load_texture(UI_DIR + name)
                          for state, (name, _) in LIFE_REGIONS.items()}
        self._life_state = None          # Estado mostrado (evita swaps redundantes).
        self.life_icon = Entity(parent=self, model='quad',
                                position=Vec3(right - 0.16, 0.36, 0))
        self._set_life_art(3)

        # ============= MINIMAPA (abajo a la izquierda) ====================
        # Marco circular estilo "plano de arquitecto" (arte final) + iconos
        # del atlas iconos_minimapa.png: perro = jugador, carita = enemigo,
        # carita con X = jefe. TODOS los iconos comparten UNA textura y se
        # diferencian solo por recorte UV: cero rebinds en GPU.
        m = MINIMAP_SIZE
        map_pos = Vec3(left + m / 2 + 0.03, -0.5 + m / 2 + 0.03, 0)
        self.minimap = Entity(parent=self, model='quad',
                              texture=load_texture(UI_DIR + 'minimapa'),
                              scale=m, position=map_pos)
        _apply_region(self.minimap, MINIMAP_REGION)   # Círculo sin márgenes.

        icons_tex = load_texture(UI_DIR + 'iconos_minimapa')
        # Jugador: SIEMPRE al centro (el mapa es relativo a él). Icono de
        # cara estática: el rumbo se lee del mundo, no del mapa.
        self.player_dot = Entity(parent=self.minimap, model='quad',
                                 texture=icons_tex, scale=0.13, z=-0.02)
        _apply_region(self.player_dot, ICON_PLAYER)
        # Pool FIJO de iconos: uno por enemigo y por caja, creados UNA vez.
        # Las cajas siguen como puntos de color (no hay arte de caja aún);
        # tonos oscuros para leerse sobre el plano claro.
        dot_colors = {'weapon': color.red, 'ammo': color.orange,
                      'health': color.green}
        self._tracked = []
        for enemy in enemies:
            dot = Entity(parent=self.minimap, model='quad', texture=icons_tex,
                         scale=0.1, z=-0.01)
            _apply_region(dot, ICON_ENEMY)
            self._tracked.append((enemy, dot))
        for crate in crates:
            dot = Entity(parent=self.minimap, model='quad',
                         color=dot_colors[crate.kind], scale=0.035, z=-0.01)
            self._tracked.append((crate, dot))
        self._map_timer = 0.0
        # El aro del marco ocupa el borde: los iconos solo entran hasta la
        # fracción MAP_USABLE del radio para no pisarlo.
        self._world_to_map = 0.5 * MAP_USABLE / MINIMAP_RADIUS
        self._radius_sq = MINIMAP_RADIUS ** 2

        # ============= ARMA + MUNICIÓN (abajo a la derecha) ===============
        # Icono GRANDE del arma actual con el arte estático suelto (una
        # textura por arma). Precargadas por su clave de WEAPONS, que
        # coincide con el nombre de archivo: revolver -> revolver_static.
        self._weapon_tex = {k: load_texture(f'{UI_DIR}{k}_static')
                            for k in WEAPONS}
        self.weapon_icon = Entity(parent=self, model='quad',
                                  texture=self._weapon_tex[weapon.current],
                                  scale=_sized(0.28, WEAPON_ASPECT),
                                  position=Vec3(right - 0.17, -0.37, 0))
        self.weapon_name = Text(parent=self, text='', scale=0.7,
                                origin=(0, 0), color=color.white,
                                position=Vec3(right - 0.17, -0.27, 0))
        # Contador de munición: debajo del icono.
        self.ammo_text = Text(parent=self, text='', scale=1.3,
                              origin=(0, 0), color=color.white,
                              position=Vec3(right - 0.17, -0.46, 0))

        # ---------------- cableado de eventos (UI reactiva) --------------
        player.on_hp_changed = self._on_hp_changed
        weapon.on_ammo_changed = self.update_ammo
        weapon.on_weapon_changed = self._on_weapon_changed
        self._on_hp_changed(player.hp, player.max_hp)
        self._on_weapon_changed(weapon.current, weapon.cfg)
        self.update_ammo(weapon.state['magazine'], weapon.state['reserve'])

    # ===================================================== API PÚBLICA ====
    def _set_life_art(self, state):
        """Aplica textura + recorte UV + proporción del estado de vida."""
        _, region = LIFE_REGIONS[state]
        self.life_icon.texture = self._life_tex[state]
        _apply_region(self.life_icon, region)
        self.life_icon.scale = _region_size(0.26, region)   # Retrato GRANDE.

    def update_health(self, lives_count):
        """Estado del retrato: 3=confiado, 2=golpeado, 1=hecho polvo,
        0=oculto (jugador muerto). Swap de textura solo si el estado
        cambió, jamás por frame."""
        lives_count = max(0, min(MAX_LIVES, lives_count))
        if lives_count == self._life_state:         # Sin cambios: nada que hacer.
            return
        self._life_state = lives_count
        if lives_count <= 0:
            self.life_icon.enabled = False
            return
        self.life_icon.enabled = True
        self._set_life_art(lives_count)

    def update_wave_progress(self, percent):
        """Progreso de oleada / vida de jefe. Acepta 0..1 (o 0..100)."""
        if percent > 1:
            percent /= 100
        if percent <= 0:
            self.boss_group.enabled = False         # Nada que mostrar.
            return
        self.boss_group.enabled = True
        self.boss_fill.scale_x = BOSS_BAR_W * min(1, percent)

    def update_minimap(self, player_pos, entities_list):
        """Traducción matemática mundo->minimapa (SIN segunda cámara).

        entities_list: pares (entity, dot). Normalmente la llama nuestro
        update() interno a 6 Hz con el pool ya creado, pero es pública por
        si quieres forzar un refresco o pasar otra lista.
        """
        k = self._world_to_map
        px, pz = player_pos.x, player_pos.z
        for target, dot in entities_list:
            if not target.enabled:                  # Muerto/recogido.
                if dot.enabled:
                    dot.enabled = False
                continue
            dx = target.x - px
            dz = target.z - pz
            inside = (dx * dx + dz * dz) < self._radius_sq
            if dot.enabled != inside:
                dot.enabled = inside
            if inside:
                # X mundo -> X mapa, Z mundo -> Y mapa (norte arriba).
                dot.position = Vec3(dx * k, dz * k, -0.01)

    def change_weapon_icon(self, frame_or_texture):
        """Cambia el icono del arma.

        - clave de WEAPONS ('revolver', 'ametralladora', 'escopeta'): usa
          la textura estática precargada de assets/ui/. Es lo que usa el
          juego vía on_weapon_changed.
        - cualquier otra cosa (ruta o Texture): se asigna directo, por si
          añades un arma cuyo arte no esté precargado.
        """
        if frame_or_texture in self._weapon_tex:
            self.weapon_icon.texture = self._weapon_tex[frame_or_texture]
        else:
            self.weapon_icon.texture = frame_or_texture

    def update_ammo(self, magazine, reserve):
        self.ammo_text.text = f'{magazine} / {reserve}'

    # -------- jefe: enganche por eventos (compatible con enemies.py) -----
    def bind_boss(self, boss):
        """La vida del jefe llega por callback, jamás por polling."""
        boss.on_hp_changed = self.update_boss_hp
        self.boss_name.text = boss.display_name
        self.update_boss_hp(boss.hp, boss.max_hp)
        # En el minimapa el jefe se distingue: carita con X y más grande.
        for target, dot in self._tracked:
            if target is boss:
                _apply_region(dot, ICON_BOSS)
                dot.scale = 0.13
                break

    def update_boss_hp(self, hp, max_hp):
        self.update_wave_progress(hp / max_hp if max_hp else 0)

    # ================================================ CALLBACKS INTERNOS ==
    def _on_hp_changed(self, hp, max_hp):
        # Salud continua (0..100) -> vidas discretas (0..3) para el HUD.
        frac = hp / max_hp
        lives = 3 if frac > 2 / 3 else (2 if frac > 1 / 3 else
                                        (1 if hp > 0 else 0))
        self.update_health(lives)

    def _on_weapon_changed(self, kind, cfg):
        self.change_weapon_icon(kind)        # Swap a la textura estática.
        self.weapon_name.text = cfg['name']

    # ======================================== BUCLE PROPIO (solo minimapa)
    def update(self):
        # Costo por frame: UNA suma y UNA comparación. El refresco real del
        # minimapa (la traducción de coordenadas) corre a ~6 Hz.
        self._map_timer += time.dt
        if self._map_timer < MINIMAP_INTERVAL:
            return
        self._map_timer = 0.0
        self.update_minimap(self.player.position, self._tracked)
