"""AutoMix — icono de la aplicación (dibujado por código: no depende de ningún archivo) y su registro en Windows."""
import sys

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QImage, QLinearGradient, QPainter, QPen, QPixmap

APP_ID = "Mayoraz.AutoMix.DJ"            # identificador de la app en Windows: así la barra de tareas usa ESTE icono y no el de Python
_ALTURAS = (0.30, 0.55, 0.85, 0.50, 1.00, 0.65, 0.40, 0.80, 0.45, 0.70, 0.35, 0.60, 0.25)      # forma de la onda (de 0 a 1)


def _dibujar(lado: int) -> QImage:
    """Dos ondas de sonido (celeste arriba, magenta abajo, como los dos decks) y la línea del playhead, sobre fondo azul oscuro."""
    img = QImage(lado, lado, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = float(lado)
    fondo = QLinearGradient(0, 0, 0, s)
    fondo.setColorAt(0.0, QColor("#2c3270")); fondo.setColorAt(1.0, QColor("#0a0d26"))
    marco = max(1.0, s * 0.03)
    p.setBrush(QBrush(fondo)); p.setPen(QPen(QColor("#8b5cf6"), marco))
    p.drawRoundedRect(QRectF(marco / 2, marco / 2, s - marco, s - marco), s * 0.22, s * 0.22)

    n = 5 if lado <= 24 else (9 if lado <= 64 else 13)
    paso = len(_ALTURAS) / n
    alturas = [_ALTURAS[min(len(_ALTURAS) - 1, int(i * paso))] for i in range(n)]
    x0, x1 = s * 0.16, s * 0.84
    ancho_slot = (x1 - x0) / n
    ancho_barra = ancho_slot * 0.62
    mitad = s * 0.17                                   # alto máximo de cada onda hacia cada lado de su eje
    for eje, color in ((s * 0.33, "#22d3ff"), (s * 0.69, "#ff3d9a")):
        p.setBrush(QBrush(QColor(color))); p.setPen(Qt.PenStyle.NoPen)
        for i, h in enumerate(alturas):
            alto = max(s * 0.05, mitad * h * 2)
            x = x0 + i * ancho_slot + (ancho_slot - ancho_barra) / 2
            p.drawRoundedRect(QRectF(x, eje - alto / 2, ancho_barra, alto), ancho_barra / 2, ancho_barra / 2)
    p.setPen(QPen(QColor("#fffadc"), max(1.0, s * 0.035)))        # playhead al centro
    p.drawLine(int(s / 2), int(s * 0.10), int(s / 2), int(s * 0.90))
    p.end()
    return img


def crear_icono() -> QIcon:
    ic = QIcon()
    for lado in (16, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(QPixmap.fromImage(_dibujar(lado)))
    return ic


def aplicar_icono(app) -> None:
    """Pone el icono de AutoMix a todas las ventanas y registra la app en Windows (barra de tareas). Se puede llamar más de una vez."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except (AttributeError, OSError):
            pass
    try:
        app.setWindowIcon(crear_icono())
    except RuntimeError:
        pass


def guardar_ico(ruta: str) -> None:
    """Escribe un .ico con varios tamaños (para el acceso directo del escritorio / instalador). Necesita Pillow."""
    from PIL import Image
    import io
    from PySide6.QtCore import QBuffer, QIODevice
    base = _dibujar(256)
    b = QBuffer(); b.open(QIODevice.OpenModeFlag.WriteOnly); base.save(b, "PNG"); b.close()
    Image.open(io.BytesIO(bytes(b.data()))).save(ruta, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
