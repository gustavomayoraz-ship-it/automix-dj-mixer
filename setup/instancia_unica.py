"""AutoMix — una sola instancia por programa (reproductor y analizador aparte).
Se usa un candado de archivo del sistema operativo: si el programa se cierra o se cae, Windows lo libera solo (no queda trabado).
No importa Qt ni librerías pesadas: se puede llamar al principio de todo, antes de cargar nada."""
import os
from pathlib import Path

CARPETA = Path(__file__).resolve().parent.parent / "cache"
_RETENIDOS = {}          # nombre -> descriptor abierto (mientras el proceso viva, el candado sigue tomado)


def tomar(nombre):
    """True si este proceso es la única instancia de `nombre`; False si ya hay otra abierta."""
    try:
        CARPETA.mkdir(exist_ok=True)
        fd = os.open(str(CARPETA / f".{nombre}.instancia"), os.O_RDWR | os.O_CREAT)
    except OSError:
        return True                                   # no se puede ni crear el archivo: mejor abrir que impedir abrir
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return False
    _RETENIDOS[nombre] = fd
    return True


def avisar_ya_abierto(titulo, texto):
    """Cuadro de aviso sin Qt (en Windows); en otros sistemas, mensaje por consola."""
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, texto, titulo, 0x40 | 0x1000)       # icono información + siempre arriba
            return
        except (OSError, AttributeError):
            pass
    print(f"[{titulo}] {texto}")
