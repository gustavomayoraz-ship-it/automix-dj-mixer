"""AutoMix — ventana de arranque: aparece al instante (antes de cargar librosa, scipy, etc.) para que se vea que el programa está abriendo."""
import sys


def abrir_splash():
    """Crea la QApplication y muestra la ventanita de arranque. Devuelve el splash (o None si algo falla)."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QPixmap
    from PySide6.QtWidgets import QApplication, QSplashScreen
    app = QApplication.instance() or QApplication(sys.argv)
    w, h = 520, 250
    pm = QPixmap(w, h); pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    fondo = QLinearGradient(0, 0, 0, h); fondo.setColorAt(0.0, QColor("#2c3270")); fondo.setColorAt(1.0, QColor("#0b0e26"))
    p.setBrush(fondo); p.setPen(QPen(QColor("#8b5cf6"), 2)); p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 16, 16)
    f = QFont("Segoe UI", 44); f.setBold(True); f.setItalic(True); p.setFont(f)
    g = QLinearGradient(QPointF(120, 0), QPointF(400, 0)); g.setColorAt(0.0, QColor("#22d3ff")); g.setColorAt(1.0, QColor("#ff3d9a"))
    p.setPen(QPen(g, 1)); p.drawText(QRectF(0, 40, w, 80), int(Qt.AlignmentFlag.AlignCenter), "AutoMix")
    f2 = QFont("Segoe UI", 10); f2.setBold(True); f2.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 6); p.setFont(f2)
    p.setPen(QColor("#9aa6d6")); p.drawText(QRectF(0, 118, w, 24), int(Qt.AlignmentFlag.AlignCenter), "DJ  MIXER")
    f3 = QFont("Segoe UI", 9); p.setFont(f3); p.setPen(QColor("#6f7ab0"))
    p.drawText(QRectF(0, 146, w, 20), int(Qt.AlignmentFlag.AlignCenter), "Gustavo Mayoraz")
    p.end()
    sp = QSplashScreen(pm, Qt.WindowType.WindowStaysOnTopHint)
    try:
        sp.setMask(pm.mask())                 # esquinas redondeadas sin fondo negro
    except Exception:
        pass
    fm = QFont("Segoe UI", 10); sp.setFont(fm)
    sp.show()
    mensaje(sp, "Iniciando…")
    return sp


def mensaje(sp, texto):
    """Cambia el texto de abajo del splash (y lo repinta ya, aunque el programa esté ocupado cargando)."""
    if sp is None:
        return
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QApplication
        sp.showMessage(texto + "  ", int(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter), QColor("#9fe3c6"))
        QApplication.processEvents()
    except Exception:
        pass
