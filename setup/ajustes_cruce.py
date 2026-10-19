"""AutoMix — ⚙ Ajustes generales del cruce: todos los tiempos que arman el 'retardo' (la onda) del crossfader.
Lo que se mueve acá se aplica enseguida (en la próxima mezcla) y queda guardado."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QDialog, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSlider,
                               QVBoxLayout, QWidget)
from setup import cruce_auto
from setup.config import guardar_config, leer_config
from setup.tema import COLOR_DECK_A, COLOR_DECK_B, TEMA

CLAVE = "ajustes_cruce"

# (clave en cruce_auto, texto, mínimo, máximo, divisor, formato, ayuda)
GRUPOS = [
    ("⏸ Pausa del medio", [
        ("PAUSA", "Pausa al 50 %", 0, 80, 10, "{:.1f} s",
         "Cuánto espera el crossfader en el 50 % (los dos temas suenan a la par) antes de seguir. 0 = sin pausa.\nVale en Auto y en Manual."),
    ]),
    ("🐢 Frenado (primera mitad)", [
        ("ZONA_K", "Frenado en el cruce", 0, 100, 10, "×{:.1f}",
         "Cuánto frena el crossfader en el punto donde se cruzan las líneas de A y B.\n0 = no frena (avanza parejo) · 5 = va a ~1/6 de la velocidad de afuera · 10 = casi se queda quieto.\nVale en Auto y en Manual."),
        ("ZONA_MIN", "Frenada antes del cruce (mín.)", 1, 25, 100, "{:.0%}",
         "La frenada empieza donde empieza a subir B y llega hasta el cruce. Si ese tramo es corto, se alarga hasta este mínimo\n(% del recorrido del crossfader). Más = frena desde más lejos, más suave."),
        ("ZONA_ACEL", "Aceleración hasta la mitad", 10, 100, 100, "{:.0%}",
         "Después del cruce el crossfader sigue lento y va acelerando de a poco.\n100 % = recién recupera la velocidad al llegar al 50 % · menos = la recupera antes de la mitad."),
    ]),
    ("🤖 Cruce Auto", [
        ("MIN_DUR", "Duración mínima", 4, 40, 1, "{:.0f} s",
         "El fundido del Auto dura al menos esto (sin contar la pausa del medio)."),
        ("DUR_IDEAL", "Duración preferida", 6, 40, 1, "{:.0f} s",
         "A igualdad de choque de voces, el Auto prefiere la duración más cercana a esta."),
        ("MAX_DUR", "Duración máxima", 8, 60, 1, "{:.0f} s",
         "El fundido del Auto nunca dura más que esto (sin contar la pausa)."),
        ("ENT_MIN", "B entra: lo más temprano", 1, 30, 100, "{:.0%}",
         "Momento más temprano en que puede empezar a entrar B (% del tiempo del fundido). Sin choque de voces entra a este punto."),
        ("ENT_MAX", "B entra: lo más tarde", 2, 40, 100, "{:.0%}",
         "Momento más tarde en que puede empezar a entrar B. Cuando las voces se pisan, entra más cerca de este punto."),
        ("RB_MIN", "Subida de B (mín.)", 2, 30, 100, "{:.0%}",
         "La subida de B abarca como mínimo este tramo del recorrido del crossfader (poco = B entra casi de golpe)."),
    ]),
]


def cargar():
    """Al arrancar: lee lo guardado y lo aplica."""
    try:
        cruce_auto.aplicar(leer_config().get(CLAVE, {}))
    except Exception:
        import traceback; traceback.print_exc()


def guardar():
    try:
        guardar_config(**{CLAVE: cruce_auto.valores()})
    except Exception:
        pass


class VistaRitmo(QWidget):
    """Muestra cómo avanza el crossfader en el tiempo con los ajustes de abajo (la onda del retardo)."""

    def __init__(self, ventana):
        super().__init__()
        self.v = ventana
        self.setMinimumHeight(165)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _caso(self):
        v = self.v
        pl = getattr(v, "_ultimo_plan", None)
        if v.cruce_auto and pl and pl.get("pc") is not None:
            return float(pl["dur"]), bool(pl.get("pausa", True)), pl["pc"], pl.get("zpb"), f"último cruce Auto ({pl['dur']:.0f} s)"
        try:
            zona = v._punto_cruce_manual()
        except Exception:
            zona = None
        if zona and not v.cruce_auto:
            return float(v.spin_mix.value()), cruce_auto.hay_pausa(), zona[0], zona[1], f"tu cruce manual ({v.spin_mix.value()} s)"
        D = max(cruce_auto.MIN_DUR, min(cruce_auto.MAX_DUR, cruce_auto.DUR_IDEAL))
        return D, cruce_auto.hay_pausa(), 0.22, 0.17, f"ejemplo ({D:.0f} s)"

    def paintEvent(self, ev):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QPen(QColor(TEMA["linea"]), 1)); p.setBrush(QBrush(QColor("#070a12")))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 8, 8)
        D, pausa, pc, pb, titulo = self._caso()
        pa = cruce_auto.PAUSA if pausa else 0.0
        total = D + pa
        x0, x1, yt, yb = 34.0, w - 12.0, 32.0, h - 22.0
        fuente = QFont(self.font()); fuente.setPointSizeF(8.0); p.setFont(fuente)
        p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        for f in (0.25, 0.5, 0.75):
            y = yb - (yb - yt) * f
            p.drawLine(QPointF(x0, y), QPointF(x1, y))
        p.setPen(QColor("#8aa"))
        for f in (0.0, 0.5, 1.0):
            p.drawText(QRectF(2, yb - (yb - yt) * f - 8, x0 - 6, 16), int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), f"{int(f * 100)}%")

        def X(T):
            return x0 + (x1 - x0) * T / max(0.001, total)

        def Y(pos):
            return yb - (yb - yt) * pos
        if pausa and pa > 0:                                              # banda de la pausa
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(255, 200, 60, 40))
            p.drawRect(QRectF(X(0.5 * D), yt, X(0.5 * D + pa) - X(0.5 * D), yb - yt))
        n = 240
        pts = []
        for i in range(n + 1):
            T = total * i / n
            pts.append(QPointF(X(T), Y(cruce_auto._t_de_T(T, D, pausa, pc, pb))))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 60), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)); p.drawPolyline(QPolygonF(pts))
        p.setPen(QPen(QColor("#ffd84a"), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)); p.drawPolyline(QPolygonF(pts))

        def tiempo_de(pos):                                              # segundos en que el crossfader llega a esa posición
            lo, hi = 0.0, 0.5 * D
            for _ in range(30):
                m = 0.5 * (lo + hi)
                if cruce_auto._t_de_T(m, D, pausa, pc, pb) < pos:
                    lo = m
                else:
                    hi = m
            return hi
        marcas = []
        if pb is not None and 0 < pb < 0.5:
            marcas.append((tiempo_de(pb), COLOR_DECK_B, "B entra"))
        if pc is not None and 0 < pc < 0.5:
            marcas.append((tiempo_de(pc), "#ffffff", "cruce"))
        for i, (T, col, txt) in enumerate(marcas):
            p.setPen(QPen(QColor(col), 1.2, Qt.PenStyle.DashLine)); p.drawLine(QPointF(X(T), yt), QPointF(X(T), yb))
            p.setPen(QColor(col))
            p.drawText(QRectF(X(T) + 4, 3 + 12 * i, 140, 14), int(Qt.AlignmentFlag.AlignLeft), f"{txt} {T:.1f} s")     # una debajo de la otra
        p.setPen(QColor("#8aa"))
        p.drawText(QRectF(x0, yb + 3, 80, 16), int(Qt.AlignmentFlag.AlignLeft), "0 s")
        p.drawText(QRectF(x1 - 160, yb + 3, 160, 16), int(Qt.AlignmentFlag.AlignRight), f"{total:.1f} s")
        p.drawText(QRectF(x0 + 60, yb + 3, x1 - x0 - 230, 16), int(Qt.AlignmentFlag.AlignCenter), titulo)
        p.end()


class AjustesCruce(QDialog):
    def __init__(self, ventana):
        super().__init__(ventana)
        self.v = ventana
        self.setWindowTitle("⚙ Ajustes generales — tiempos y retardo del cruce")
        self.setMinimumWidth(680)
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        info = QLabel("Acá se regulan los tiempos del cruce. La curva amarilla muestra cómo avanza el crossfader (0 % = suena A · 100 % = suena B): "
                      "la banda amarilla es la pausa del 50 %. Los cambios se guardan solos y valen desde la próxima mezcla.")
        info.setWordWrap(True); info.setStyleSheet("color:#9fe3c6;")
        lay.addWidget(info)
        self.vista = VistaRitmo(ventana)
        lay.addWidget(self.vista)
        self._sl = {}
        for titulo, filas in GRUPOS:
            caja = QGroupBox(titulo)
            gl = QGridLayout(caja)
            gl.setContentsMargins(8, 14, 8, 6); gl.setHorizontalSpacing(8); gl.setVerticalSpacing(4)
            for r, (k, texto, lo, hi, div, fmt, tip) in enumerate(filas):
                lbl = QLabel(texto); lbl.setToolTip(tip)
                sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(lo, hi); sl.setToolTip(tip)
                sl.setValue(int(round(getattr(cruce_auto, k) * div)))
                val = QLabel(); val.setMinimumWidth(56); val.setAlignment(Qt.AlignmentFlag.AlignRight)
                sl.valueChanged.connect(lambda x, k=k, div=div, fmt=fmt, val=val: self._cambio(k, x, div, fmt, val))
                val.setText(fmt.format(sl.value() / div))
                gl.addWidget(lbl, r, 0); gl.addWidget(sl, r, 1); gl.addWidget(val, r, 2)
                gl.setColumnStretch(1, 1)
                self._sl[k] = (sl, val, div, fmt)
            lay.addWidget(caja)
        fila = QHBoxLayout()
        b_def = QPushButton("Valores por defecto"); b_def.clicked.connect(self._defecto)
        b_cer = QPushButton("Cerrar"); b_cer.clicked.connect(self.close)
        for b in (b_def, b_cer):
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        fila.addWidget(b_def); fila.addStretch(1); fila.addWidget(b_cer)
        lay.addLayout(fila)

    def _cambio(self, k, x, div, fmt, val):
        val.setText(fmt.format(x / div))
        cruce_auto.aplicar({k: x / div})
        guardar()
        self.vista.update()

    def _defecto(self):
        for k, (sl, val, div, fmt) in self._sl.items():
            sl.blockSignals(True); sl.setValue(int(round(cruce_auto.DEFECTOS[k] * div))); sl.blockSignals(False)
            val.setText(fmt.format(sl.value() / div))
        cruce_auto.aplicar(cruce_auto.DEFECTOS)
        guardar()
        self.vista.update()
