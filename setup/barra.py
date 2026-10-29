"""AutoMix — barra de progreso con marca de auto-enganche."""
from PySide6.QtGui import QBrush, QColor, QCursor, QFontMetricsF, QLinearGradient, QPainter, QPen, QPolygonF
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtWidgets import QSizePolicy, QWidget
from setup import cruce_auto
from setup.ajustes import AJ, FUENTE_BOOST, fmt_time
from setup.config import DEF_MARCA
from setup.tema import TEMA


# =====================================================================
# 3.6) BARRA DE PROGRESO CON MARCA (AUTO-ENGANCHE)
# =====================================================================
class BarraProgresoConMarca(QWidget):
    marca_cambiada = Signal(float)
    marca_cruzada = Signal(float)

    MARGEN = 10

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(58)
        self.setMaximumHeight(58)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.progreso = 0.0
        self.prog_seg = 0.0
        self.dur = 0.0
        self.marca = DEF_MARCA
        self._arrastrando = False
        self._arrastrando_marca = False
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def set_progreso(self, p, seg=0.0, dur=0.0):
        p = max(0.0, min(1.0, float(p)))
        cambio = (abs(p - self.progreso) > 1e-4
                  or abs(seg - self.prog_seg) > 0.05
                  or abs(dur - self.dur) > 0.05)
        self.progreso = p
        self.prog_seg = seg
        self.dur = dur
        if cambio:
            self.update()

    def set_marca(self, m):
        m = float(m)
        self.marca = m if m >= 0 else DEF_MARCA
        self.update()

    def _x_de_frac(self, f):
        w = self.width()
        m = self.MARGEN
        return m + f * max(1, (w - 2 * m))

    def _frac_de_x(self, x):
        w = self.width()
        m = self.MARGEN
        return max(0.0, min(1.0, (x - m) / max(1, (w - 2 * m))))

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        m = self.MARGEN

        SOBRE = 4                       # cuánto sobresale la marca roja por arriba y por abajo de la barra (igual en los dos lados)
        # Todo se centra respecto del MARCO real del cuadro (no del widget): el marco deja arriba un hueco para el título,
        # y centrado en el widget la barra y la marca quedaban más abajo que el medio del marco.
        par = self.parentWidget(); oy = self.y()
        if par is not None and par.height() > 0:
            marco_t, marco_b = 12.0, par.height() - 1.0        # el borde del marco empieza 12 px bajo el tope del cuadro (margin-top del QSS)
            cy = (marco_t + marco_b) / 2.0 - oy
            tit_b = marco_t + QFontMetricsF(par.font()).height() / 2.0 + 2.0 - oy      # la barra empieza bajo el texto del título
        else:
            cy, tit_b = h / 2.0, 4.0
        mitad = min(cy - tit_b, cy - SOBRE - 0.5, (h - 1.0) - SOBRE - cy)   # media altura de la barra: la mayor que entra, simétrica
        mitad = max(8.0, mitad)
        y_prog_t = cy - mitad
        y_prog_b = cy + mitad
        y_top = y_prog_t - SOBRE        # la marca queda centrada exactamente sobre la barra
        y_bot = y_prog_b + SOBRE
        hh = y_prog_b - y_prog_t
        ancho = w - 2 * m
        rad = min(8.0, hh / 2.0)

        p.setPen(QPen(QColor(255, 255, 255, 40), 1))                      # reglita de cuartos
        for f in (0.25, 0.5, 0.75):
            x = self._x_de_frac(f)
            p.drawLine(int(x), 0, int(x), 3)

        fondo = QLinearGradient(0, y_prog_t, 0, y_prog_b)
        fondo.setColorAt(0.0, QColor("#04060b")); fondo.setColorAt(1.0, QColor("#0d1220"))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(fondo))
        p.drawRoundedRect(QRectF(m, y_prog_t, ancho, hh), rad, rad)

        if self.progreso > 0.0:
            pw = self.progreso * ancho
            if pw > 1:
                g = QLinearGradient(m, 0, m + ancho, 0)
                g.setColorAt(0.0, QColor("#0f7fa6")); g.setColorAt(0.55, QColor(TEMA["cian"])); g.setColorAt(1.0, QColor(TEMA["violeta"]))
                p.setBrush(QBrush(g))
                p.drawRoundedRect(QRectF(m, y_prog_t, pw, hh), rad, rad)
                brillo = QLinearGradient(0, y_prog_t, 0, y_prog_t + hh)       # reflejo de vidrio
                brillo.setColorAt(0.0, QColor(255, 255, 255, 80)); brillo.setColorAt(0.5, QColor(255, 255, 255, 10)); brillo.setColorAt(1.0, QColor(0, 0, 0, 40))
                p.setBrush(QBrush(brillo))
                p.drawRoundedRect(QRectF(m, y_prog_t, pw, hh), rad, rad)

        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(TEMA["linea"]), 1))
        p.drawRoundedRect(QRectF(m, y_prog_t, ancho, hh), rad, rad)

        if self.dur > 0:
            txt = f"{fmt_time(self.prog_seg)}  /  {fmt_time(self.dur)}"
        else:
            txt = "--:--  /  --:--"
        f = self.font(); f.setPointSizeF(max(12.0, 10.5 * AJ.escala * FUENTE_BOOST)); f.setBold(True); p.setFont(f)
        r_txt = QRectF(m + 10, y_prog_t, ancho - 20, hh)
        p.setPen(QColor(0, 0, 0, 170)); p.drawText(r_txt.translated(1, 1), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), txt)
        p.setPen(QColor("#ffffff")); p.drawText(r_txt, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), txt)

        if self.marca >= 0:
            txt_m = f"⚓ {self.marca * 100:.1f}%"
            p.setPen(QColor(0, 0, 0, 170)); p.drawText(r_txt.translated(1, 1), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight), txt_m)
            p.setPen(QColor(TEMA["rojo"])); p.drawText(r_txt, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight), txt_m)

        if self.marca >= 0 and cruce_auto.BREAK_ACTIVO >= 0.5:        # línea de trazos: desde dónde empieza a vigilarse un break (⚙ «Vigilar desde»)
            xv = self._x_de_frac(max(0.0, self.marca - float(cruce_auto.BREAK_VENTANA)))
            amb = QColor(TEMA["ambar"])
            p.setPen(QPen(QColor(0, 0, 0, 170), 3.4)); p.drawLine(QPointF(xv, y_top), QPointF(xv, y_bot))
            lin = QPen(amb, 1.8, Qt.PenStyle.CustomDashLine); lin.setDashPattern([2.5, 2.0])
            p.setPen(lin); p.drawLine(QPointF(xv, y_top), QPointF(xv, y_bot))

        if self.marca >= 0:                      # la marca va AL FRENTE: se dibuja al final, encima de la barra
            xm = self._x_de_frac(self.marca)
            rojo = QColor(TEMA["rojo"])
            p.setPen(QPen(QColor(rojo.red(), rojo.green(), rojo.blue(), 60), 9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))   # resplandor
            p.drawLine(QPointF(xm, y_top + 4), QPointF(xm, y_bot - 4))
            p.setPen(QPen(QColor(0, 0, 0, 200), 4)); p.drawLine(QPointF(xm, y_top), QPointF(xm, y_bot))
            p.setPen(QPen(rojo, 2.2)); p.drawLine(QPointF(xm, y_top), QPointF(xm, y_bot))
            p.setBrush(QBrush(rojo)); p.setPen(QPen(QColor(0, 0, 0, 220), 1))
            p.drawPolygon(QPolygonF([QPointF(xm - 7, y_top), QPointF(xm + 7, y_top), QPointF(xm, y_top + 8)]))
            p.drawPolygon(QPolygonF([QPointF(xm - 7, y_bot), QPointF(xm + 7, y_bot), QPointF(xm, y_bot - 8)]))

        p.end()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._arrastrando = True
            self._set_marca_desde_x(ev.position().x())

    def mouseMoveEvent(self, ev):
        if self._arrastrando:
            self._set_marca_desde_x(ev.position().x())

    def mouseReleaseEvent(self, ev):
        self._arrastrando = False

    def mouseDoubleClickEvent(self, ev):
        self.marca = DEF_MARCA                  # la marca nunca se borra: vuelve a su posición por defecto
        self.marca_cambiada.emit(DEF_MARCA)
        self.update()

    def _set_marca_desde_x(self, x):
        f = self._frac_de_x(x)
        self.marca = f
        self.marca_cambiada.emit(f)
        self.update()

    def sizeHint(self):
        return QSize(500, 58)
