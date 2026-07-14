"""
player.py — Jugador: FPS con teclado/ratón Y mando Xbox SIMULTÁNEOS,
más estado (vida, daño, muerte).

INPUT SIMULTÁNEO SIN MENÚ DE SELECCIÓN
--------------------------------------
Ursina vuelca TODO en el mismo diccionario `held_keys`: las teclas valen
0/1 y los ejes del gamepad son floats (-1..1) bajo nombres como
'gamepad left stick x'. Eso permite SUMAR ambos periféricos cada frame:

  - Movimiento/cámara de teclado+ratón: los resuelve el update() del
    prefab FirstPersonController (raycasts en C++), que se llama con
    super().update().
  - ENCIMA se suma la contribución del mando: si el stick está en su zona
    muerta aporta exactamente 0 y no toca nada; si el jugador mueve ratón
    y stick a la vez, ambas rotaciones se suman de forma natural.

Un dispositivo en reposo cuesta: 4 lecturas de diccionario y 4
comparaciones por frame. No hay detección de dispositivo, ni estados, ni
menú de selección: ambos caminos viven en el mismo update().

ZONA MUERTA (deadzone)
----------------------
Los sticks analógicos nunca reportan 0.0 exacto en reposo (drift). Si el
valor crudo |v| < DEADZONE se descarta; si la supera, se RE-ESCALA:
    útil = (|v| - dz) / (1 - dz)
para que el rango utilizable siga siendo 0..1 completo (sin el re-escalado,
apenas pasar la zona muerta daría un salto brusco de velocidad).
"""

from ursina import Vec2, Vec3, clamp, color, held_keys, raycast, time
from ursina.prefabs.first_person_controller import FirstPersonController

from config import (GAMEPAD_DEADZONE, GAMEPAD_LOOK_SPEED_X,
                    GAMEPAD_LOOK_SPEED_Y, MOUSE_SENSITIVITY, PLAYER_JUMP,
                    PLAYER_MAX_HP, PLAYER_SPEED)


def _deadzone(value, dz=GAMEPAD_DEADZONE):
    """Filtra el drift del stick y re-escala el rango útil a 0..1."""
    if abs(value) < dz:
        return 0.0
    sign = 1.0 if value > 0 else -1.0
    return sign * (abs(value) - dz) / (1.0 - dz)


class Player(FirstPersonController):

    def __init__(self):
        super().__init__(position=(0, 1, 0), speed=PLAYER_SPEED,
                         jump_height=PLAYER_JUMP)
        self.mouse_sensitivity = Vec2(MOUSE_SENSITIVITY, MOUSE_SENSITIVITY)
        self.cursor.color = color.black

        self.max_hp = PLAYER_MAX_HP
        self.hp = PLAYER_MAX_HP
        self.dead = False

        # Callbacks por EVENTO (los instalan ui.py y menus.py).
        self.on_hp_changed = None
        self.on_death = None

    # ------------------------------------------------- input simultáneo
    def update(self):
        # 1) Teclado + ratón: intactos, los resuelve el prefab (WASD,
        #    gravedad y salto con raycasts en C++).
        super().update()

        # 2) CÁMARA con stick derecho: se SUMA a lo que ya hizo el ratón.
        look_x = _deadzone(held_keys['gamepad right stick x'])
        look_y = _deadzone(held_keys['gamepad right stick y'])
        if look_x:
            self.rotation_y += look_x * GAMEPAD_LOOK_SPEED_X * time.dt
        if look_y:
            # Mismo clamp de cabeceo que usa el prefab (-90..90).
            self.camera_pivot.rotation_x = clamp(
                self.camera_pivot.rotation_x
                - look_y * GAMEPAD_LOOK_SPEED_Y * time.dt, -90, 90)

        # 3) MOVIMIENTO con stick izquierdo: dirección en el plano del
        #    jugador, normalizada solo si excede 1 (diagonal), con el mismo
        #    chequeo de pared del prefab: UN raycast en C++.
        move_x = _deadzone(held_keys['gamepad left stick x'])
        move_y = _deadzone(held_keys['gamepad left stick y'])
        if move_x or move_y:
            direction = self.forward * move_y + self.right * move_x
            if direction.length() > 1:
                direction = direction.normalized()
            wall = raycast(self.position + Vec3(0, 1, 0),
                           direction.normalized(), distance=0.6,
                           ignore=(self,))
            if not wall.hit:
                self.position += direction * self.speed * time.dt

    def input(self, key):
        super().input(key)               # 'space' = salto (prefab).
        if key == 'gamepad a':           # Botón A del mando = salto.
            self.jump()

    # ------------------------------------------------------------- estado
    def take_damage(self, amount):
        if self.dead:
            return
        self.hp = max(0, self.hp - amount)
        if self.on_hp_changed:
            self.on_hp_changed(self.hp, self.max_hp)
        if self.hp == 0:
            self.dead = True
            if self.on_death:
                # menus.py congela TODO con application.paused y muestra FIN.
                self.on_death()

    def heal(self, amount):
        """True si la curación se usó (la caja no se gasta en vano)."""
        if self.dead or self.hp >= self.max_hp:
            return False
        self.hp = min(self.max_hp, self.hp + amount)
        if self.on_hp_changed:
            self.on_hp_changed(self.hp, self.max_hp)
        return True

    def reset(self):
        """Nueva partida: restaura estado y posición SIN recrear el entity."""
        self.dead = False
        self.hp = self.max_hp
        self.position = (0, 1, 0)
        self.rotation_y = 0
        self.camera_pivot.rotation_x = 0
        if self.on_hp_changed:
            self.on_hp_changed(self.hp, self.max_hp)
