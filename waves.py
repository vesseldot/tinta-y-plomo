"""
waves.py — EnemyManager (pools por tipo) + WaveManager (oleadas por piso).

EnemyManager
------------
Dueño del pool de balas y de UN pool fijo por tipo de enemigo (ENEMY_POOL).
Nunca se crean/destruyen enemigos en runtime: 'spawn' toma uno LIBRE del pool
y lo coloca; 'morir' solo lo deshabilita. Expone `all_enemies` (para el
minimapa del HUD) y `boss` (para la barra superior).

WaveManager
-----------
Un Entity con update() barato que orquesta el nivel:
  1. ACTIVACIÓN POR PISO: compara la altura Y del jugador (floor_from_y) y,
     cuando el jugador LLEGA físicamente a un piso por primera vez, arranca
     la oleada 0 de ese piso. Los enemigos de pisos superiores no existen
     (no piensan, no se mueven, no atacan) hasta ese momento.
  2. PROGRESIÓN DE OLEADAS: cuenta las bajas; al limpiar una oleada, tras
     WAVE_DELAY aparece la siguiente. Limpiadas todas las de un piso, ese
     piso queda despejado.
  3. VICTORIA: matar al Jefe (piso 3) gana la partida (on_win).

El HUD refleja el progreso reutilizando la barra superior (set_wave / la
vida del jefe por evento).
"""

import random

from ursina import Entity, Vec3, invoke

from config import (BOSS_NAME, ENEMY_POOL, FLOOR_SIZE, FLOOR_Y, FLOORS_WAVES,
                    WAVE_DELAY, floor_from_y)
from enemies import Enemy
from enemy_bullet import BulletManager


class EnemyManager:
    """Pools por tipo + pool de balas. Sin lógica de oleadas (eso es del
    WaveManager); aquí solo se crea y recicla."""

    def __init__(self, player):
        self.player = player
        self.bullets = BulletManager()

        # Un pool fijo por tipo. all_enemies = todos, para el minimapa.
        self.pools = {}
        self.all_enemies = []
        for type_key, count in ENEMY_POOL.items():
            items = [Enemy(type_key, player, self.bullets)
                     for _ in range(count)]
            for e in items:
                e.enabled = False
            self.pools[type_key] = items
            self.all_enemies.extend(items)

        # El (único) jefe: nombre propio para la barra superior del HUD.
        self.boss = self.pools['boss'][0]
        self.boss.display_name = BOSS_NAME

    def free(self, type_key):
        """Primer enemigo LIBRE (deshabilitado) de ese tipo, o None."""
        for e in self.pools[type_key]:
            if not e.enabled:
                return e
        return None

    def clear(self):
        """Apaga todos los enemigos y balas (nueva partida / reinicio)."""
        for e in self.all_enemies:
            e.enabled = False
            e.active = False
        self.bullets.clear()


class WaveManager(Entity):
    """Orquesta pisos y oleadas. Es la fachada que usan main.py y menus.py
    (reset_all)."""

    def __init__(self, player, enemies, hud, gates=None):
        super().__init__()
        self.player = player
        self.enemies = enemies
        self.hud = hud
        self.gates = gates or {}         # {piso: reja} — bloquean la subida.
        self.on_win = None               # main.py lo conecta a menus.show_win.

        self._reset_state()

    # ------------------------------------------------------------- estado
    def _reset_state(self):
        self.started_floor = -1          # Piso más alto ya iniciado.
        self.floor_idx = 0               # Piso cuya oleada corre ahora.
        self.wave_idx = 0                # Oleada actual dentro del piso.
        self.alive = []                  # Enemigos vivos de la oleada actual.
        self.wave_total = 0              # Tamaño de la oleada (para el %).
        self.between_waves = False       # En pausa entre oleadas.
        self.won = False

    def reset_all(self):
        """Reiniciar = reusar: apaga todo, vuelve a bloquear las rejas y deja
        que update() re-arranque el piso 0 cuando el jugador esté colocado."""
        self.enemies.clear()
        for parts in self.gates.values():    # Muros de vuelta a "bloqueado".
            for g in parts:
                g.enabled = True
        self._reset_state()
        if self.hud:
            self.hud.hide_wave()
            self.hud.set_waves_left(0)

    # -------------------------------------------------- activación por piso
    def update(self):
        if self.won:
            return

        # ¿El jugador llegó a un piso nuevo (más alto)? Actívalo.
        pf = floor_from_y(self.player.y)
        if pf > self.started_floor:
            self._start_floor(pf)

        # Progresión: ¿se limpió la oleada actual?
        if not self.between_waves and self.alive:
            # Filtra los que murieron (enabled=False). La lista de la oleada
            # es pequeña; solo refrescamos el HUD si el conteo cambió (evita
            # reasignar texto/escala cada frame).
            before = len(self.alive)
            self.alive = [e for e in self.alive if e.enabled]
            if len(self.alive) != before:
                self._update_hud_progress()
            if not self.alive:
                self._on_wave_cleared()

    def _start_floor(self, index):
        """Arranca la oleada 0 del piso `index` (activa a sus enemigos)."""
        self.started_floor = index
        self.floor_idx = index
        self.wave_idx = 0
        self._spawn_wave(index, 0)

    # --------------------------------------------------------- oleadas
    def _spawn_wave(self, floor_idx, wave_idx):
        spec = FLOORS_WAVES[floor_idx][wave_idx]
        floor_y = FLOOR_Y[floor_idx]
        self.alive = []
        for type_key, count in spec:
            for _ in range(count):
                e = self.enemies.free(type_key)
                if not e:                # Pool agotado (no debería): sáltalo.
                    continue
                e.on_death = self._on_enemy_death
                e.spawn(self._spawn_pos(floor_y), floor_y)
                e.activate()             # El piso ya está bajo los pies.
                self.alive.append(e)
        self.wave_total = len(self.alive)
        self.between_waves = False
        # Oleadas que faltan por despejar en este piso (incluida la actual).
        if self.hud:
            self.hud.set_waves_left(len(FLOORS_WAVES[floor_idx]) - wave_idx)
        self._update_hud_progress()

    def _spawn_pos(self, floor_y):
        """Posición aleatoria en el piso, lejos del jugador (para no
        aparecer encima)."""
        half = FLOOR_SIZE / 2 - 3
        for _ in range(8):
            p = Vec3(random.uniform(-half, half), floor_y,
                     random.uniform(-half, half))
            flat = Vec3(p.x - self.player.x, 0, p.z - self.player.z)
            if flat.length() > 8:        # Al menos 8 u del jugador.
                return p
        return p                          # Si no encuentra hueco, la última.

    def _on_enemy_death(self, enemy):
        # Victoria inmediata si cae el Jefe (aunque queden peones).
        if enemy.is_boss:
            self._win()

    def _on_wave_cleared(self):
        self.between_waves = True
        n_waves = len(FLOORS_WAVES[self.floor_idx])
        if self.wave_idx + 1 < n_waves:
            # Siguiente oleada del mismo piso tras una pausa.
            self.wave_idx += 1
            if self.hud:
                self.hud.set_wave(f'PISO {self.floor_idx + 1} · DESPEJADO', 0)
            invoke(self._spawn_wave, self.floor_idx, self.wave_idx,
                   delay=WAVE_DELAY)
        else:
            # Piso despejado: abrir la reja para poder subir. (Si es el
            # último, ya se ganó al matar al jefe; esto es respaldo.)
            for g in self.gates.get(self.floor_idx, []):
                g.enabled = False            # Techo + muro abiertos: rampa libre.
            if self.hud:
                self.hud.set_waves_left(0)
                if self.floor_idx >= len(FLOORS_WAVES) - 1:
                    self.hud.hide_wave()
                else:
                    self.hud.set_wave(
                        f'PISO {self.floor_idx + 1} DESPEJADO · SUBE', 0)

    # ----------------------------------------------------------- victoria
    def _win(self):
        if self.won:
            return
        self.won = True
        if self.hud:
            self.hud.hide_wave()
        if self.on_win:
            self.on_win()

    # -------------------------------------------------------------- HUD
    def _update_hud_progress(self):
        if not self.hud:
            return
        # Si en la oleada hay jefe, su vida (por evento) manda la barra.
        boss = next((e for e in self.alive if e.is_boss), None)
        if boss:
            self.hud.set_wave(BOSS_NAME, boss.hp / boss.max_hp)
            return
        frac = (len(self.alive) / self.wave_total) if self.wave_total else 0
        self.hud.set_wave(
            f'PISO {self.floor_idx + 1} · OLEADA {self.wave_idx + 1}', frac)
