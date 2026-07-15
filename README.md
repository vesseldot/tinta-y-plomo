# Tinta y Plomo — FPS 2.5D en Ursina (estética Rubber Hose años 30)

Shooter en primera persona con estética **Rubber Hose / cartoon de los años 30**:
enemigos y arma como **sprites 2D planos animados** dentro de un **mundo 3D
low-poly**, con prioridad al rendimiento sobre la fidelidad gráfica.

El mundo es un **archivero gigante de 3 pisos** apilados verticalmente. Subes
piso a piso limpiando **oleadas** de enemigos hasta enfrentar al **Jefe Final**
en el último piso.

## Ejecutar

```bash
pip install ursina screeninfo
python main.py              # pantalla completa
python main.py --windowed   # ventana 1280x720 (útil para depurar)
python main.py --smoke      # prueba automática mínima, se cierra sola
```

Controles: **ENTER/ESPACIO/clic** iniciar/reintentar · **WASD** moverse ·
**ratón** apuntar · **clic izquierdo** disparar · **clic derecho** apuntar (ADS) ·
**R** recargar · **espacio** saltar · **ESC** pausa (Q en pausa para salir).
Mando Xbox soportado en paralelo (sticks, gatillos, A/Start/X).

El primer arranque tarda (Panda3D compila shaders una vez); los siguientes son
rápidos. El audio va desactivado (`audio-library-name null`): el juego aún no
usa sonidos y así evita errores en equipos sin dispositivo de salida.

### Cajas de suministros (en los 3 pisos)

| Caja | Efecto |
|---|---|
| **Roja** | Arma al azar (revólver / ametralladora / escopeta); la munición de cada una persiste al cambiar |
| **Amarilla** | Munición del arma actual (siempre menos que un cargador) |
| **Verde** | Botiquín **permanente**: restaura vida y se queda en su sitio para reutilizarlo |

## Estructura del nivel (El Archivero)

- **3 pisos** apilados en el eje Y. Empiezas en el Piso 1.
- **Activación por altura:** los enemigos de un piso están inertes hasta que
  el jugador llega físicamente a ese piso (se comprueba su `y`).
- **Wave Manager:** cada piso tiene oleadas; la siguiente aparece al limpiar la
  anterior. Piso 1 y 2: 2 oleadas (pequeños + medianos). Piso 3: medianos + el
  **Jefe Final** → derrotarlo **gana la partida**.
- **No se sube sin limpiar:** cada rampa vive en un hueco de escalera cerrado
  por una **pared de piso a techo** que solo se retira al despejar el piso. Las
  rampas alternan de lado por piso para que cruces la sala.
- **Cobertura:** cajas y columnas con collider repartidas por piso.

## Enemigos y animación (sprites)

Tres tipos, definidos como datos en `config.py` (`ENEMY_TYPES`):

| Tipo | Sprite | Tamaño | Rol |
|---|---|---|---|
| **Básico** | `assets/enemies/enem1.png` (rejilla 5×4) | Pequeño | Peón, dispara lento |
| **Ejecutor** | `assets/enemies/enemigo2.png` (rejilla 4×4) | Mediano | Más vida y cadencia |
| **Jefe** | `assets/enemies/jefe.png` (filas irregulares) | Enorme | Ráfaga rápida; matarlo = ganar |

- **Recorte por regiones UV:** cada animación (`idle` / `shoot`) declara su
  rectángulo en píxeles `{x, y, fw, fh}` + nº de frames + fps. Mostrar un frame
  es mover `texture_offset`/`texture_scale`; la GPU nunca recarga textura y
  todos los enemigos de un tipo comparten material. Sirve tanto para rejillas
  uniformes como para el sheet irregular del jefe.
- **Billboard en C++:** `setBillboardAxis()` de Panda3D encara el sprite a la
  cámara sin código Python por frame (look "recorte de cartón").

## IA y combate

- **Campo de visión (distancia 3D):** si el jugador entra en rango, el enemigo
  se detiene, lo encara y dispara; si no, avanza hacia él.
- **Sin atravesar geometría:** el avance usa un raycast corto por delante (no
  cruza muros ni cobertura), y solo dispara si tiene **línea de visión** libre
  al jugador — la cobertura de verdad protege.
- **Regla de piso:** un enemigo solo persigue/dispara al jugador si está en su
  mismo piso (no dispara entre pisos por el hueco de la escalera).
- **Proyectil `EnemyBullet`:** pooled, viaja en línea recta hacia el jugador,
  **choca con muros/cobertura** (raycast) y resta vida al impactar.
- **Barra de vida por enemigo:** un billboard sobre la cabeza (verde → amarillo
  → rojo) que se actualiza al recibir daño.

## Interfaz (HUD años 30, escala de grises)

- **Retrato del detective** (arriba a la derecha) con **barra de vida** al lado
  que se vacía al recibir daño; el rostro cambia por umbrales (sano/herido/crítico).
- **Barra superior**: nombre + progreso de la oleada o **vida del Jefe**.
- **Marcador `OLEADAS RESTANTES: N`** del piso actual.
- **Minimapa** (abajo a la izquierda) sin segunda cámara: matemática X/Z→UI.
- **Arma + munición** (abajo a la derecha) con el icono del arma actual.

## Arquitectura

| Módulo | Responsabilidad |
|---|---|
| `main.py` | Configura el motor (audio off, ventana, niebla) y ensambla los sistemas; log de arranque + `error.log` |
| `config.py` | Todas las constantes de rendimiento/gameplay en un solo lugar |
| `world.py` | Los 3 pisos texturizados, cobertura, rampas por hueco y rejas |
| `player.py` | Controlador FPS (teclado/ratón + mando) + vida/daño/muerte por eventos |
| `combat.py` | Arsenal por tabla de datos (3 armas), hitscan con perdigones, ADS, pools de efectos |
| `enemies.py` | Enemigos billboard animados por spritesheet, IA a distancia, barra de vida, pooling |
| `enemy_bullet.py` | Proyectil enemigo pooled con colisión de muros |
| `waves.py` | `EnemyManager` (pools por tipo) + `WaveManager` (oleadas, activación por piso, rejas, victoria) |
| `loot.py` | Cajas arma/munición/vida repartidas por piso; recogida por distancia² con chequeo de altura |
| `ui.py` | `GameHUD`: retrato+vida, barra de oleada/jefe, oleadas restantes, minimapa, arma |
| `menus.py` | Inicio / pausa / Game Over / **Victoria** vía `application.paused` |
| `pool.py` | Entity Pooling genérico (round-robin de tamaño fijo) |
| `assets_gen.py` | Genera con PIL los pocos placeholders aún usados (puff, armas, piezas de UI) |

> Nota: el archivo de constantes se llama `config.py` y **no** `settings.py` a
> propósito: Ursina auto-ejecuta cualquier `settings.py` que encuentre en la
> carpeta de assets, lo que causaría una doble carga.

## Optimizaciones aplicadas

- **Billboarding en C++, no en Python:** enemigos, barras de vida, balas y
  puffs usan los billboards de Panda3D; cero rotaciones en Python por frame.
- **Animación por UV:** cambiar de frame o de arma es mover `texture_offset`,
  nunca recargar textura. Un material por tipo de enemigo.
- **Sombreado plano:** `unlit_shader` en todos los sprites y cero luces en
  escena → el color del PNG llega crudo; el estilo cel elimina por diseño el
  coste de iluminación. Sin post-procesado, sin sombras dinámicas.
- **Entity Pooling:** enemigos, balas enemigas, trazadores, puffs y cajas se
  pre-instancian y se reciclan (`pool.py`); nada se crea/destruye en combate →
  sin picos de instanciación ni pausas del recolector de basura.
- **Colisiones baratas:** solo *box colliders*. El disparo del jugador es
  **hitscan** (raycast en C++); las balas enemigas y la IA usan raycasts cortos.
- **Trabajo por frame mínimo:** temporizadores simples en vez de `Sequence`; el
  HUD se redibuja **por eventos** (`on_hp_changed`, `on_ammo_changed`…), nunca
  por frame (asignar `Text.text` reconstruye la malla, así que se evita); el
  minimapa refresca a ~6 Hz.
- **Minimapa sin render-to-texture:** un quad en `camera.ui` con puntos que
  mapean X/Z de mundo a coordenadas locales, con un pool fijo de puntos.
- **Pausa gratis:** `application.paused = True` congela updates, inputs y
  `invoke` de todo el juego; el único ente vivo es el menú (`ignore_paused=True`).
  Reiniciar re-usa los pools (`reset_all`), no reconstruye nada.

## ¿Y Pygame?

No hace falta: Panda3D (bajo Ursina) provee **input** nativo (teclado/ratón/mando
vía `held_keys`). El audio va deshabilitado a nivel de motor porque el juego aún
no usa sonidos. Si más adelante quisieras audio, `ursina.Audio` basta; añadir
Pygame metería un segundo bucle SDL compitiendo con el del motor.
