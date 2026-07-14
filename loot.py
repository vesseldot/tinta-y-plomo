"""
loot.py — Cajas de suministros interactivas (vida y munición).

REGLAS DE GAMA BAJA APLICADAS
-----------------------------
1. Pool fijo de CRATE_COUNT cajas creadas UNA vez al cargar. Recoger una
   caja = deshabilitarla; reaparecer = re-posicionarla. Igual que balas y
   enemigos: cero instanciación/destrucción en runtime, GC tranquilo.
2. Recogida "por contacto" SIN física: nada de trigger volumes ni tests de
   colisión por frame. Es una comparación de distancia al cuadrado (sin
   raíz cuadrada) contra el jugador, a 5 Hz (LOOT_CHECK_INTERVAL).
3. Cada caja es UN solo Entity: cubo low-poly con color plano (mismo
   lenguaje visual "cartón/decorado" del mapa) + collider box para que el
   raycast del arma pueda abrirla de un disparo.
4. Nada de brillos, rotaciones idle ni "bobbing" por frame: bonitos, pero
   son N updates de Python por segundo que la CPU débil agradece no pagar.
"""

import random

from ursina import Entity, Vec3, color, invoke, time

from config import (CRATE_COUNT, CRATE_HEAL, CRATE_PICKUP_RADIUS,
                    CRATE_RESPAWN_DELAY, LOOT_CHECK_INTERVAL, MAP_SIZE,
                    WEAPONS)


class Crate(Entity):
    """Caja interactiva.

    kind: 'weapon' (ROJA: arma intercambiable al azar),
          'ammo'   (AMARILLA: munición del arma actual, ammo_pickup < cargador),
          'health' (BLANCA: botiquín — mantiene viva la fila del corazón).
    """

    COLORS = {
        'weapon': color.hsv(0, 0.55, 0.85),    # Rojo plano: armas.
        'ammo': color.hsv(45, 0.6, 0.85),      # Amarillo plano: balas.
        'health': color.hsv(0, 0.0, 0.9),      # Blanco/gris: botiquín.
    }
    KINDS = ('weapon', 'ammo', 'health')

    def __init__(self, kind, manager):
        super().__init__(model='cube', texture='white_cube', scale=0.8,
                         color=Crate.COLORS[kind], collider='box')
        self.kind = kind
        self.manager = manager

    def take_damage(self, amount):
        # Dispararle a la caja también la abre: mismo duck typing que usa
        # combat.py con los enemigos — cero acoplamiento entre módulos.
        self.manager.consume(self)


class LootManager(Entity):
    """Coloca las cajas, detecta la recogida por contacto y las recicla."""

    def __init__(self, player, weapon):
        super().__init__()
        self.player = player
        self.weapon = weapon
        self._timer = 0.0
        self._pickup_sq = CRATE_PICKUP_RADIUS ** 2   # Distancia², sin sqrt.

        self.crates = []
        for i in range(CRATE_COUNT):     # Reparto cíclico: arma/balas/vida.
            crate = Crate(Crate.KINDS[i % len(Crate.KINDS)], self)
            self._place(crate)
            self.crates.append(crate)

    def _place(self, crate):
        margin = MAP_SIZE / 2 - 5
        crate.position = Vec3(random.uniform(-margin, margin), 0.4,
                              random.uniform(-margin, margin))
        crate.enabled = True

    def update(self):
        # Recogida por contacto a baja frecuencia: 5 chequeos/s bastan para
        # un radio de 1.7 unidades a velocidad de jugador 8 u/s.
        self._timer += time.dt
        if self._timer < LOOT_CHECK_INTERVAL:
            return
        self._timer = 0.0

        p = self.player.position
        for crate in self.crates:
            if not crate.enabled:
                continue
            dx = crate.x - p.x
            dz = crate.z - p.z
            if dx * dx + dz * dz < self._pickup_sq:
                self.consume(crate)

    def consume(self, crate):
        if not crate.enabled:
            return
        # Los métodos devuelven False si no hacían falta: la caja se queda
        # en el mundo en vez de desperdiciarse (mismo if, costo cero).
        if crate.kind == 'weapon':
            # Arma al azar de la tabla; si ya la tienes, suelta algo de
            # munición de esa arma (lógica en combat.give_weapon).
            accepted = self.weapon.give_weapon(
                random.choice(list(WEAPONS.keys())))
        elif crate.kind == 'ammo':
            accepted = self.weapon.add_ammo()
        else:
            accepted = self.player.heal(CRATE_HEAL)
        if not accepted:
            return
        crate.enabled = False
        invoke(self._place, crate, delay=CRATE_RESPAWN_DELAY)

    def reset_all(self):
        """Nueva partida: recolocar todas las cajas."""
        for crate in self.crates:
            self._place(crate)
