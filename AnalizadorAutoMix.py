"""
AutoMix — Analizador aparte.
Analiza la biblioteca en un programa SEPARADO del reproductor (ventana propia, a máxima velocidad) y guarda
los resultados en la carpeta "cache". Lo abre el reproductor cuando hay miles de temas sin analizar; el reproductor
puede seguir abierto o cerrarse: al volver a abrirlo lee lo que se guardó.
Uso manual:  python AnalizadorAutoMix.py --lista lista.txt [--suave] [--forzar]     (lista.txt: una ruta por línea)
"""
import sys
from pathlib import Path

_RAIZ = str(Path(__file__).resolve().parent)
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

import setup.base          # dependencias + consola oculta (también lo corre el proceso hijo del análisis)


if __name__ == "__main__":
    from setup.analizador_aparte import main
    sys.exit(main(sys.argv[1:]))
