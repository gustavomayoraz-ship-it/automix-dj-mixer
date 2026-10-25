"""
AutoMix — PySide6  (mezclador DJ de dos decks: cruce por bandas, recetas automáticas)
- Play individual por deck
- Waveform de cada deck se mueve SOLO si suena
- 🔗 Sync automático de BPM y downbeats sin tirones
- 🔊 Sistema Automático de Ganancia (Auto-Gain RMS normalizado a -14 dBFS)
- 🎚️ Crossfader: volumen A↔B + BPM compartido interpolado
- 🎬 Mezclar: auto-fade con duración configurable (atajo F2) + pausa 3 s al 50 %
- ⚓ Barra de progreso con marca de auto-enganche
- ⏯ Tecla Espacio para pausar/reanudar el deck sonando
- ⟲ Botón de reset de tiempo en cada deck
- 🛑 Auto-stop del deck silenciado al llegar los extremos
- ✋ Manito: arrastrar la waveform
- Playhead fijo al centro
- Tempo suavizado y biblioteca ordenada por BPM

Este archivo solo abre el programa: el código está repartido en la carpeta "setup" (una parte por tema).
"""
import sys
import time
from pathlib import Path

_T0 = time.perf_counter()

_RAIZ = str(Path(__file__).resolve().parent)
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

if __name__ == "__main__":                        # una sola ventana de AutoMix a la vez (los procesos hijos del análisis no pasan por acá)
    from setup.instancia_unica import avisar_ya_abierto, tomar
    if not tomar("AutoMix"):
        avisar_ya_abierto("AutoMix", "AutoMix ya está abierto.\n\nSi no lo ves, buscalo en la barra de tareas "
                                     "(puede estar todavía cargando la biblioteca).")
        sys.exit(0)

import setup.base          # dependencias + consola oculta (también lo corre el proceso hijo del análisis)
_T1 = time.perf_counter()


if __name__ == "__main__":
    _splash = None
    try:
        from setup.arranque import abrir_splash, mensaje
        _splash = abrir_splash()                        # ventana de arranque YA (antes de cargar librosa, scipy, etc.)
        mensaje(_splash, "Cargando módulos…")
    except Exception:
        _splash = None
    from setup.ventana import main
    main((_T0, _T1, time.perf_counter()), _splash)
