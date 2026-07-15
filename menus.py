"""
menus.py — Pantalla de inicio, pausa y Game Over.

LA PAUSA MÁS BARATA POSIBLE
---------------------------
`application.paused = True` hace que Ursina deje de llamar update() e
input() de TODAS las entidades (y congela los invoke/Sequence pendientes).
No hay que tocar ni un sistema: enemigos, arma, culler y loot se detienen
solos, y el coste de CPU en pausa cae casi a cero.

La única entidad con `ignore_paused = True` es este MenuManager: sigue
recibiendo teclado para poder despausar. Las pantallas son un quad
semitransparente + 2 Texts REUTILIZADOS (se les cambia el texto, nunca se
crean/destruyen pantallas): la lógica de menús pesa 3 entidades en total.

REINICIAR = REUSAR
------------------
"Otra partida" no reconstruye nada: llama a los reset() de cada sistema,
que re-posicionan los pools existentes (misma filosofía del pooling).
"""

from ursina import Entity, Text, application, camera, color, mouse, window


class MenuManager(Entity):

    def __init__(self, player, weapon, enemy_manager, loot_manager, hud):
        super().__init__(parent=camera.ui, ignore_paused=True)
        self.player = player
        self.weapon = weapon
        self.enemy_manager = enemy_manager
        self.loot_manager = loot_manager
        self.hud = hud
        self.state = 'start'

        # Panel de fondo: UN quad negro semitransparente (el mundo se ve
        # detrás, en pausa queda congelado como fotograma — gratis y noir).
        self.panel = Entity(parent=self, model='quad', color=color.black,
                            scale=(window.aspect_ratio + 0.1, 1.1), z=0.1)
        self.panel.alpha = 0.82
        self.title = Text(parent=self, text='', scale=2.4, origin=(0, 0),
                          y=0.1, color=color.white)
        self.subtitle = Text(parent=self, text='', scale=1.0, origin=(0, 0),
                             y=-0.06, color=color.light_gray)

        # La muerte del jugador llega por evento, no por polling.
        player.on_death = self.show_game_over

        # Arrancamos EN la pantalla de inicio, con el mundo congelado.
        self._show_screen('TINTA Y PLOMO',
                          'ENTER / ESPACIO: comenzar el caso        ESC: salir')

    # ---------------------------------------------------------- pantallas
    def _show_screen(self, title, subtitle):
        self.panel.enabled = True
        self.title.enabled = True
        self.subtitle.enabled = True
        self.title.text = title          # Texts reutilizados, no recreados.
        self.subtitle.text = subtitle
        self.hud.enabled = False         # HUD apagado = ni un update de UI.
        application.paused = True        # Congela TODO menos este menú.
        mouse.locked = False

    def _hide_screens(self):
        self.panel.enabled = False
        self.title.enabled = False
        self.subtitle.enabled = False
        self.hud.enabled = True
        application.paused = False
        mouse.locked = True

    # -------------------------------------------------------------- flujo
    def start_game(self):
        self.state = 'playing'
        self._hide_screens()

    def pause(self):
        self.state = 'paused'
        self._show_screen('PAUSA',
                          'ESC / ENTER: continuar        Q: salir')

    def resume(self):
        self.state = 'playing'
        self._hide_screens()

    def show_game_over(self):
        self.state = 'gameover'
        self._show_screen('FIN',
                          'ENTER / ESPACIO: otra toma        ESC: salir')

    def show_win(self):
        """Victoria: se llama al derrotar al Jefe Final (piso 3)."""
        self.state = 'win'
        self._show_screen('CASO CERRADO',
                          'Derrotaste al jefe del archivero.        '
                          'ENTER / ESPACIO: otra partida    ESC: salir')

    def restart(self):
        # Reiniciar = reusar: cada sistema recoloca sus pools existentes.
        self.player.reset()
        self.weapon.reset()
        self.enemy_manager.reset_all()
        self.loot_manager.reset_all()
        self.start_game()

    # -------------------------------------------------------------- input
    def input(self, key):
        # ignore_paused=True: este es el único input vivo durante menús.
        # ENTER, ESPACIO, clic o botón A/Start confirman: costumbre de
        # arcade y el mando funciona en los menús sin configurar nada.
        confirm = key in ('enter', 'space', 'left mouse down', 'gamepad a',
                          'gamepad start')
        if self.state == 'playing':
            if key in ('escape', 'gamepad start'):
                self.pause()
        elif self.state == 'paused':
            if key == 'escape' or confirm:
                self.resume()
            elif key == 'q':
                application.quit()
        elif self.state == 'start':
            if confirm:
                self.start_game()
            elif key == 'escape':
                application.quit()
        elif self.state in ('gameover', 'win'):
            if confirm:
                self.restart()
            elif key == 'escape':
                application.quit()
