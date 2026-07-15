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
                    CRATE_RESPAWN_DELAY, FLOOR_SIZE, FLOOR_Y, N_FLOORS,
                    LOOT_CHECK_INTERVAL, WEAPONS)


class Crate(Entity):
    """Caja interactiva.

    kind: 'weapon' (ROJA: arma intercambiable al azar),
          'ammo'   (AMARILLA: munición del arma actual, ammo_pickup < cargador),
          'health' (BLANCA: botiquín — mantiene viva la fila del corazón).
    """

    COLORS = {
        'weapon': color.hsv(0, 0.55, 0.85),    # Rojo plano: armas.
        'ammo': color.hsv(45, 0.6, 0.85),      # Amarillo plano: balas.
        'health': color.hsv(130, 0.6, 0.75),   # Verde: botiquín (recupera vida).
    }
    KINDS = ('weapon', 'ammo', 'health')

    def __init__(self, kind, manager):
        super().__init__(model='cube', texture='white_cube', scale=0.8,
                         color=Crate.COLORS[kind], collider='box')
        self.kind = kind
        self.manager = manager
        self.floor = 0                   # Piso donde vive (lo fija LootManager).

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

        # Un juego COMPLETO (arma + munición + VIDA) GARANTIZADO en cada piso,
        # y los extras restantes repartidos cíclicamente.
        combos = [(kind, floor) for floor in range(N_FLOORS)
                  for kind in Crate.KINDS]
        i = 0
        while len(combos) < CRATE_COUNT:
            combos.append((Crate.KINDS[i % len(Crate.KINDS)], i % N_FLOORS))
            i += 1

        self.crates = []
        for kind, floor in combos[:CRATE_COUNT]:
            crate = Crate(kind, self)
            crate.floor = floor
            self._place(crate)
            self.crates.append(crate)

    def _place(self, crate):
        # La caja vive en SU piso, dentro de los muros y fuera del corredor de
        # la rampa/hueco (x≈0, z 0..22), para no bloquearlo ni caer por él.
        margin = FLOOR_SIZE / 2 - 5
        y = FLOOR_Y[crate.floor]
        for _ in range(12):
            x = random.uniform(-margin, margin)
            z = random.uniform(-margin, margin)
            if abs(x) < 6 and -2 < z < 22:      # Corredor de la rampa/hueco.
                continue
            break
        crate.position = Vec3(x, y + 0.4, z)
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
            # Chequeo de ALTURA: sin esto recogerías una caja del piso de
            # arriba a través del techo (el radio de recogida es en el plano).
            if abs(crate.y - p.y) > 2.5:
                continue
            dx = crate.x - p.x
            dz = crate.z - p.z
            if dx * dx + dz * dz < self._pickup_sq:
                self.consume(crate)

    def consume(self, crate):
        if not crate.enabled:
            return
        # Las cajas de VIDA (verdes) NO desaparecen: son estaciones de
        # curación permanentes. Curan si te hace falta y se quedan en su
        # sitio para volver a usarlas.
        if crate.kind == 'health':
            self.player.heal(CRATE_HEAL)
            return
        # Los métodos devuelven False si no hacían falta: la caja se queda
        # en el mundo en vez de desperdiciarse (mismo if, costo cero).
        if crate.kind == 'weapon':
            # Arma al azar de la tabla; si ya la tienes, suelta algo de
            # munición de esa arma (lógica en combat.give_weapon).
            accepted = self.weapon.give_weapon(
                random.choice(list(WEAPONS.keys())))
        else:  # 'ammo'
            accepted = self.weapon.add_ammo()
        if not accepted:
            return
        crate.enabled = False
        invoke(self._place, crate, delay=CRATE_RESPAWN_DELAY)

    def reset_all(self):
        """Nueva partida: recolocar todas las cajas."""
        for crate in self.crates:
            self._place(crate)
