# Detective Shooter — FPS 2.5D en Ursina optimizado para gama baja

Shooter en primera persona estilo **"Mouse: P.I. for Hire"**: enemigos y arma
como **sprites 2D planos (cel-shading)** dentro de un **mundo 3D low-poly**,
con prioridad absoluta al rendimiento sobre la fidelidad gráfica.

## Ejecutar

```bash
pip install ursina
python main.py            # ESC para salir
python main.py --smoke    # prueba automática: corre 5 s y se cierra sola
```

Controles: **ENTER/ESPACIO/clic** iniciar/reintentar · **WASD** moverse ·
**ratón** apuntar · **clic izquierdo** disparar · **R** recargar ·
**espacio** saltar · **ESC** pausa (Q en pausa para salir).

Cajas: **rojas** = arma al azar (revólver / ametralladora / escopeta, la
munición de cada una persiste al cambiar) · **amarillas** = munición del
arma actual (siempre menos que un cargador) · **blancas** = botiquín.
El primer enemigo del pool es el jefe **SMURG** (barra segmentada superior).

La primera ejecución genera sprites placeholder en `assets/` (flat shading +
contorno, atlas de 8 direcciones). Sustitúyelos por tu arte final respetando
el mismo layout.

## Arquitectura

| Módulo | Responsabilidad |
|---|---|
| `main.py` | Configuración del motor y ensamblaje de los sistemas |
| `config.py` | Todas las constantes de rendimiento/gameplay en un solo lugar |
| `world.py` | Mapa 3D low-poly, geometría combinada por sectores, culling |
| `player.py` | Controlador FPS + vida/daño/muerte por eventos |
| `combat.py` | Arsenal por tabla de datos (3 armas), hitscan con perdigones, pools |
| `enemies.py` | Billboards de 8 direcciones, IA + ataque, jefe SMURG, pool |
| `loot.py` | Cajas arma/munición/vida: pool fijo, recogida por distancia² a 5 Hz |
| `ui.py` | GameHUD años 30: jefe (centro), vidas-rostros (der.), minimapa (izq.), arma (der.) |
| `menus.py` | Inicio / pausa / Game Over vía `application.paused` |
| `pool.py` | Entity Pooling genérico |
| `assets_gen.py` | Genera los sprites placeholder con PIL |

> Nota: el archivo de constantes se llama `config.py` y **no** `settings.py`
> a propósito: Ursina auto-ejecuta cualquier `settings.py` que encuentre en
> la carpeta de assets, lo que causaría una doble carga.

## Cómo se mezcla 2D y 3D sin perder rendimiento

1. **Billboarding en C++, no en Python.** Cada enemigo usa
   `setBillboardAxis()` de Panda3D: el motor rota el sprite hacia la cámara
   durante el recorrido de escena, sin ejecutar ni una línea de Python por
   frame. El eje vertical fijo da el look "recorte de cartón" clásico.
2. **8 direcciones = 1 atlas + offset UV.** Los 8 frames viven en una sola
   textura; cambiar de dirección es mover `texture_offset` (gratis para la
   GPU), nunca cambiar de textura. El índice se recalcula a 10 Hz con fase
   aleatoria por enemigo, no a 60 Hz.
3. **Sombreado plano = estética + optimización.** `unlit_shader` en todos los
   sprites y cero luces en escena: el color del PNG llega crudo a pantalla.
   El estilo "dibujado a mano" elimina por diseño el coste de iluminación.
4. **El arma es UI, no mundo.** El revólver es un quad hijo de `camera.ui`:
   en espacio de pantalla no necesita billboard, ni culling, ni transformes
   de mundo. El retroceso es un lerp del offset.

## Optimizaciones aplicadas

- **Draw calls:** la escenografía estática se fusiona por sector con
  `Entity.combine()` (~200 cubos → ~36 mallas). Todo comparte la textura
  `white_cube` y la variedad la da el color de vértice: sin cambios de
  textura entre llamadas.
- **Culling:** Panda3D ya hace *frustum culling* en C++ por nodo; los
  sectores le dan bloques grandes que descartar de golpe. Encima, un
  `SectorCuller` desactiva sectores más lejos de `RENDER_DISTANCE` cada
  0.25 s (Panda3D no trae occlusion culling real; esto lo aproxima). El *far
  clip* corto + niebla lineal esconden el corte.
- **Colisiones:** solo *box colliders* (nunca mesh colliders), separados de
  los visuales para que el culling no rompa la física. El disparo es
  **hitscan** (un raycast en C++), no proyectiles físicos.
- **Entity Pooling:** balas trazadoras, puffs de impacto y enemigos se
  pre-instancian al cargar y se reciclan (`pool.py`). Nada se crea ni
  destruye en combate → sin picos de instanciación ni pausas del recolector
  de basura.
- **Trabajo por frame mínimo:** IA con *early-out* por distancia, animación
  de sprites a 10 Hz, culling a 4 Hz, temporizadores simples en vez de
  `Sequence`/`invoke` por disparo.
- **Render:** forward rendering simple de Panda3D sin tocar: sin
  post-procesado (Bloom/SSAO), sin sombras dinámicas, cielo = color de fondo
  (0 draw calls), `vsync` activado, `development_mode=False`.
- **UI por eventos:** asignar `Text.text` reconstruye la malla del texto, así
  que el HUD (vida, munición, rostro) solo se redibuja vía callbacks
  (`on_hp_changed`, `on_ammo_changed`) cuando el valor cambió — nunca por
  frame. El rostro del detective usa un atlas de 3 estados con
  `texture_offset`, igual que los enemigos.
- **Minimapa sin render-to-texture:** nada de segunda cámara ortográfica
  (duplicaría el coste de escena). Es un quad en `camera.ui` con puntos que
  mapean coordenadas X/Z de mundo a coordenadas locales del quad, refrescado
  a ~6 Hz con un pool fijo de puntos.
- **Pausa gratis:** `application.paused = True` congela updates, inputs y
  Sequences de todo el juego; el único ente vivo es el menú
  (`ignore_paused=True`). Reiniciar partida re-usa los pools (`reset()`),
  no reconstruye nada.

## ¿Y Pygame?

No hace falta: Panda3D ya provee **input** (teclado/ratón vía `held_keys`,
`mouse`) y **audio** (`ursina.Audio`) nativos. Añadir Pygame metería un
segundo bucle de eventos SDL compitiendo con el del motor. El único uso
legítimo sería `pygame.mixer` **solo** (`pygame.mixer.init()`, sin
`pygame.init()` ni ventana) si necesitaras mezcla de audio avanzada: corre
aparte y no toca el bucle principal. Para este proyecto, `Audio` de Ursina
es suficiente.
