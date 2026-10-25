"""
AutoMix — Analizador aparte.
Analiza la biblioteca en un programa SEPARADO del reproductor (ventana propia, a máxima velocidad) y guarda
los resultados en la carpeta "cache". Lo abre el reproductor cuando hay miles de temas sin analizar; el reproductor
puede seguir abierto o cerrarse: al volver a abrirlo lee lo que se guardó.
Uso manual:  python setup/AnalizadorAutoMix.py --lista lista.txt [--suave] [--forzar]     (lista.txt: una ruta por línea)
"""
import sys
from pathlib import Path

_AQUI = Path(__file__).resolve().parent          # carpeta "setup"
_RAIZ = str(_AQUI.parent)                        # carpeta del programa (donde está AutoMix.py)
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != _AQUI]      # (la carpeta setup no debe quedar como lugar de módulos sueltos: sus archivos pisarían nombres de otros módulos)
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

import setup.base          # dependencias + consola oculta (también lo corre el proceso hijo del análisis)


if __name__ == "__main__":
    from setup.analizador_aparte import main
    sys.exit(main(sys.argv[1:]))
