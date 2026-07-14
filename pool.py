"""
pool.py — Entity Pooling genérico.

PROBLEMA: crear/destruir Entities en runtime (balas, chispazos, puffs) hace
dos cosas caras:
  1. Instanciar un Entity implica crear NodePaths de Panda3D, cargar/asociar
     modelos y texturas -> picos de CPU (stutter) justo cuando disparas.
  2. destroy() libera objetos Python -> presión sobre el recolector de
     basura (GC). En hardware de gama baja el GC pausando el hilo principal
     se nota como micro-congelamientos.

SOLUCIÓN: pre-instanciar N objetos al cargar el nivel y RECICLARLOS.
Un Entity con enabled=False no se renderiza, no colisiona y su update()
no se ejecuta: su coste en runtime es prácticamente cero.
"""


class EntityPool:
    """Pool round-robin de tamaño fijo.

    Round-robin en vez de lista de libres: si el pool se agota, el objeto
    más viejo se recicla en el acto. El coste queda ACOTADO (nunca hay más
    de `size` objetos vivos) y acquire() es O(1) sin asignar memoria.
    """

    def __init__(self, factory, size: int):
        # Toda la asignación de memoria ocurre AQUÍ, durante la carga,
        # nunca durante el gameplay.
        self.items = [factory() for _ in range(size)]
        for item in self.items:
            item.enabled = False
        self._next = 0

    def acquire(self):
        """Devuelve el siguiente objeto del pool, ya habilitado."""
        item = self.items[self._next]
        self._next = (self._next + 1) % len(self.items)
        item.enabled = True
        return item

    @staticmethod
    def release(item):
        """Devolver = simplemente deshabilitar. Nada se destruye jamás."""
        item.enabled = False
