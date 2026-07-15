"""
enemy_bullet.py — Proyectil enemigo (EnemyBullet) con pooling.

POR QUÉ POOLING (misma filosofía que combat.py / loot.py)
--------------------------------------------------------
Los enemigos disparan constantemente: crear/destruir un Entity por bala
provocaría stutter y presión de GC en gama baja. En su lugar hay UN pool
fijo (EBULLET_POOL_SIZE) compartido por TODOS los enemigos: disparar =
reactivar la bala más vieja y relanzarla. El número de balas vivas nunca
supera el tamaño del pool.

SIN FÍSICA REAL
---------------
La bala viaja en línea recta hacia donde estaba el jugador al dispararse
(no es teledirigida: esquivarla es parte del juego). El impacto se resuelve
con UNA distancia al cuadrado contra el jugador por frame; no hay colliders
ni raycasts por bala. La caducidad por tiempo (EBULLET_LIFETIME) evita que
una bala perdida viva para siempre.

El sprite es un quad billboard sencillo (reutiliza assets/puff.png teñido):
sin arte nuevo, se ve como un fogonazo/plomo volando y es baratísimo.
"""

from ursina import Entity, Vec3, color, raycast, time
from ursina.shaders import unlit_shader

from pool import EntityPool
from config import (EBULLET_HIT_RADIUS, EBULLET_LIFETIME, EBULLET_POOL_SIZE,
                    EBULLET_SIZE)


class EnemyBullet(Entity):
    """Una bala reciclable. Inhabilitada en el pool cuesta cero."""

    def __init__(self):
        super().__init__(model='quad', texture='assets/puff.png',
                         scale=EBULLET_SIZE, double_sided=True,
                         color=color.orange, shader=unlit_shader,
                         enabled=False)
        # Billboard total en C++: la bala siempre encara la cámara.
        self.setBillboardPointEye()
        self._vel = Vec3(0, 0, 0)
        self._life = 0.0
        self._damage = 0
        self._player = None
        # Radio² pre-calculado: evitamos la raíz en el bucle caliente.
        self._hit_r2 = EBULLET_HIT_RADIUS * EBULLET_HIT_RADIUS

    def fire(self, origin, target, speed, damage, player, tint=color.orange):
        """Lanza la bala desde `origin` hacia la posición `target`."""
        self.position = origin
        direction = target - origin
        if direction.length() < 1e-4:        # Degenerado: dispara al frente.
            direction = Vec3(0, 0, 1)
        self._vel = direction.normalized() * speed
        self._life = EBULLET_LIFETIME
        self._damage = damage
        self._player = player
        self.color = tint
        self.scale = EBULLET_SIZE

    def update(self):
        # Caducidad: la bala perdida vuelve al pool.
        self._life -= time.dt
        if self._life <= 0:
            EntityPool.release(self)
            return

        # Colisión con MUROS/COBERTURA: si en el tramo de este frame hay
        # geometría por delante, la bala se detiene ahí (no atraviesa). Se
        # ignora al jugador: su impacto se resuelve aparte, por distancia.
        travel = self._vel * time.dt
        wall = raycast(self.world_position, self._vel.normalized(),
                       distance=travel.length(), ignore=(self._player,))
        if wall.hit:
            EntityPool.release(self)
            return

        self.position += travel

        # Impacto: distancia² contra el "torso" del jugador (su posición +
        # algo de altura). Una resta de vectores y un producto punto.
        target = self._player.world_position + Vec3(0, 1.1, 0)
        offset = target - self.world_position
        if offset.length_squared() <= self._hit_r2:
            self._player.take_damage(self._damage)
            EntityPool.release(self)


class BulletManager:
    """Dueño del pool de balas enemigas. Los enemigos llaman a `spawn`."""

    def __init__(self):
        self.pool = EntityPool(EnemyBullet, EBULLET_POOL_SIZE)

    def spawn(self, origin, target, speed, damage, player, tint=color.orange):
        self.pool.acquire().fire(origin, target, speed, damage, player, tint)

    def clear(self):
        """Nueva partida: apaga todas las balas en vuelo."""
        for b in self.pool.items:
            b.enabled = False
