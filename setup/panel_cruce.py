"""AutoMix — gráfico y panel de la forma de cruce."""
import math
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QSizePolicy, QSlider, QVBoxLayout, QWidget
from PySide6.QtCore import QPoint, QPointF, QRectF, QTimer, Qt
from setup import aprendizaje, cruce_auto
from setup.ajustes import AJ, FUENTE_BOOST
from setup.config import DEF_FIN_A, DEF_GAMMA_A, DEF_PUNTO_A, DEF_PUNTO_B, DEF_PUNTO_S, DEF_RAMPA_B, perfil_cruce_ab, perfil_cruce_bandas
from setup.tema import COLOR_DECK_A, COLOR_DECK_B, TEMA
from setup.widgets import qss_marco


class GraficoCruce(QWidget):
    def __init__(self):
        super().__init__()
        self.punto_a = DEF_PUNTO_A; self.punto_b = DEF_PUNTO_B; self.avance = None
        self.punto_s = DEF_PUNTO_S; self.bandas = False; self.simple = False
        self.rb = None; self.gamma = 1.0; self.etiqueta = None; self.vacio = None; self.pausa = None
        self.setMinimumHeight(62)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def actualizar(self, pa, pb, avance=None, ps=None, bandas=False, fa=None, simple=False, rb=None, gamma=1.0,
                   etiqueta=None, vacio=None, inc=None, pausa=None):
        self.rb, self.gamma, self.etiqueta, self.vacio = rb, gamma, etiqueta, vacio
        self.pausa = pausa                                                 # (posición 0..1, segundos) de la pausa del cruce manual; None = no se dibuja
        self.inc = inc                                                     # (cuándo entra B, cuánto tarda en subir) en fracción del fundido: el fundido de temas incompatibles
        self.simple = bool(simple)
        self.punto_a, self.punto_b, self.avance = pa, pb, avance
        self.fin_a = fa
        if ps is not None:
            self.punto_s = ps
        self.bandas = bool(bandas)
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h, m = self.width(), self.height(), 6
        fondo = QLinearGradient(0, 0, 0, h); fondo.setColorAt(0.0, QColor("#0a0e18")); fondo.setColorAt(1.0, QColor("#05070d"))
        p.setPen(QPen(QColor(TEMA["linea"]), 1)); p.setBrush(QBrush(fondo))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 8, 8)
        x0, x1, yt, yb = m + 4.0, w - m - 4.0, m + 4.0, h - m - 4.0
        p.setPen(QPen(QColor(255, 255, 255, 18), 1))                       # cuadrícula
        for f in (0.25, 0.5, 0.75):
            p.drawLine(QPointF(x0 + (x1 - x0) * f, yt), QPointF(x0 + (x1 - x0) * f, yb))
            p.drawLine(QPointF(x0, yt + (yb - yt) * f), QPointF(x1, yt + (yb - yt) * f))
        if self.vacio:                                                     # Auto sin ningún cruce diseñado todavía
            fs = QFont(self.font()); fs.setPointSizeF(max(7.0, 7.5 * AJ.escala * FUENTE_BOOST)); fs.setBold(True); p.setFont(fs)
            p.setPen(QColor(TEMA["ambar"])); p.drawText(QRectF(x0, yt, x1 - x0, yb - yt), int(Qt.AlignmentFlag.AlignCenter), self.vacio)
            p.end(); return
        pa, pb, la, lb = [], [], [], []
        for i in range(61):
            t = i / 60
            if getattr(self, "inc", None):
                te, fr = self.inc
                vs = 1.0 - t
                ve = 1.0 if t >= te + fr - 1e-9 else (max(0.0, (t - te) / fr) if fr > 1e-6 and t >= te else (1.0 if t >= te else 0.0)); ls, le = vs, ve
            elif self.simple:
                vs, ve = math.cos(t * math.pi / 2.0), math.sin(t * math.pi / 2.0); ls, le = vs, ve
            elif self.bandas:
                vs, ve, ls, le = perfil_cruce_bandas(t, self.punto_a, self.punto_b, self.punto_s, rampa=(self.rb or 0.12),
                                                     fin_a=getattr(self, "fin_a", None), gamma_a=self.gamma)
            else:
                vs, ve = perfil_cruce_ab(t, self.punto_a, self.punto_b); ls, le = vs, ve
            x = x0 + (x1 - x0) * t
            pa.append(QPointF(x, yb - vs * (yb - yt))); pb.append(QPointF(x, yb - ve * (yb - yt)))
            la.append(QPointF(x, yb - ls * (yb - yt) + 3)); lb.append(QPointF(x, yb - le * (yb - yt) + 3))
        ca, cb = QColor(COLOR_DECK_A), QColor(COLOR_DECK_B)

        def curva(pts, c, relleno=True):
            if relleno:                                                     # área translucida debajo de la curva
                poli = QPolygonF(pts + [QPointF(x1, yb), QPointF(x0, yb)])
                g = QLinearGradient(0, yt, 0, yb); g.setColorAt(0.0, QColor(c.red(), c.green(), c.blue(), 70)); g.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g)); p.drawPolygon(poli)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(c.red(), c.green(), c.blue(), 55), 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)); p.drawPolyline(QPolygonF(pts))   # resplandor
            p.setPen(QPen(c, 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)); p.drawPolyline(QPolygonF(pts))
        if self.bandas and not self.simple:              # graves: línea punteada, el traspaso se ve como un escalón
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(ca.lighter(150), 2, Qt.PenStyle.DotLine)); p.drawPolyline(QPolygonF(la))
            p.setPen(QPen(cb.lighter(150), 2, Qt.PenStyle.DotLine)); p.drawPolyline(QPolygonF(lb))
            xs = x0 + (x1 - x0) * max(0.0, min(1.0, self.punto_s))          # dónde se traspasa el bajo
            p.setPen(QPen(QColor(TEMA["verde"]), 1, Qt.PenStyle.DashLine)); p.drawLine(QPointF(xs, yt), QPointF(xs, yb))
        if self.pausa is not None:                       # línea vertical de la pausa: cuando la línea blanca llega acá, el cruce se queda quieto ese tiempo
            xp = x0 + (x1 - x0) * max(0.0, min(1.0, self.pausa[0]))
            am = QColor(TEMA["ambar"])
            p.setPen(QPen(QColor(0, 0, 0, 170), 3.2)); p.drawLine(QPointF(xp, yt), QPointF(xp, yb))
            p.setPen(QPen(am, 1.6, Qt.PenStyle.DashLine)); p.drawLine(QPointF(xp, yt), QPointF(xp, yb))
        curva(pa, ca); curva(pb, cb)
        if self.simple or self.etiqueta:
            fs = QFont(self.font()); fs.setPointSizeF(max(7.0, 7.5 * AJ.escala * FUENTE_BOOST)); fs.setBold(True); p.setFont(fs)
            p.setPen(QColor(TEMA["ambar"])); p.drawText(QRectF(x0, yt - 2, x1 - x0, 16), int(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter),
                                                         "CRUCE SIMPLE · BPM distintos" if self.simple else self.etiqueta)
        if self.avance is not None:
            xa = x0 + (x1 - x0) * max(0.0, min(1.0, self.avance))
            p.setPen(QPen(QColor(255, 255, 255, 60), 6)); p.drawLine(QPointF(xa, yt), QPointF(xa, yb))
            p.setPen(QPen(QColor("#ffffff"), 1.5)); p.drawLine(QPointF(xa, yt), QPointF(xa, yb))
        p.end()




def _qss_boton(c1, c2, borde, texto, c1h=None, c2h=None):
    """Botón con degradé de color propio (para que no se pierdan con el fondo azul del panel)."""
    c1h = c1h or c1; c2h = c2h or c2
    return (f"QPushButton {{ background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {c1}, stop:1 {c2}); color:{texto}; font-weight:bold;"
            f" border:1px solid {borde}; border-radius:9px; padding:5px 6px; }}"
            f"QPushButton:hover {{ background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {c1h}, stop:1 {c2h}); border:2px solid #ffffff; }}"
            f"QPushButton:pressed {{ padding-top:7px; }}")


class PanelCruce(QFrame):
    def __init__(self, ventana):
        super().__init__()
        self.v = ventana
        self.setObjectName("panelcruce")
        self.setStyleSheet(qss_marco("QFrame#panelcruce", "#3b82f6", titulo=False))
        self.setMinimumWidth(230); self.setMaximumWidth(300)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(3)
        self.chk = QCheckBox("🎚 Forma de cruce A/B")
        self.chk.setToolTip("Sin tilde: cruce clásico por volumen.")
        self.chk.setChecked(ventana.cruce_ab)
        lay.addWidget(self.chk)
        self.graf = GraficoCruce(); lay.addWidget(self.graf)

        def fila(texto, color, valor, tip):
            r = QHBoxLayout()
            l = QLabel(texto); l.setStyleSheet(f"color:{color}; font-weight:bold;"); l.setToolTip(tip)
            sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(0, 95); sl.setValue(int(round(valor * 100))); sl.setToolTip(tip)
            lv = QLabel(f"{sl.value()}%"); lv.setMinimumWidth(40); lv.setAlignment(Qt.AlignmentFlag.AlignRight)
            r.addWidget(l); r.addWidget(sl, 1); r.addWidget(lv); lay.addLayout(r)
            return sl, lv
        self.sl_a, self.lv_a = fila("A (sale):", COLOR_DECK_A, ventana.punto_a, "Momento en que el tema que sale comienza a bajar.")
        self.sl_b, self.lv_b = fila("B (entra):", COLOR_DECK_B, ventana.punto_b, "Momento en que el tema que entra comienza a subir (por bandas: entra a nivel pleno, con una subida corta).")
        def fila_g(texto, color, lo, hi, valor, tip):                  # deslizador con otro rango (valor entero)
            r = QHBoxLayout()
            l = QLabel(texto); l.setStyleSheet(f"color:{color}; font-weight:bold;"); l.setToolTip(tip)
            sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(lo, hi); sl.setValue(int(valor)); sl.setToolTip(tip)
            lv = QLabel(); lv.setMinimumWidth(40); lv.setAlignment(Qt.AlignmentFlag.AlignRight)
            r.addWidget(l); r.addWidget(sl, 1); r.addWidget(lv); lay.addLayout(r)
            return sl, lv
        self.sl_rb, self.lv_rb = fila_g("B sube en:", COLOR_DECK_B, 2, 40, round(ventana.rampa_b * 100),
                                        "Cuánto tarda B en subir a pleno una vez que entra (en % de la mezcla). Poco = entra de golpe · mucho = sube despacio.")
        self.sl_fa, self.lv_fa = fila_g("A termina en:", COLOR_DECK_A, 50, 100, round(ventana.fin_a * 100),
                                        "En qué punto de la mezcla termina de irse A. 100 % = automático (baja hasta el final). Menos = A se va antes y los dos dejan de sonar juntos antes.")
        self.sl_g, self.lv_g = fila_g("Forma de A:", COLOR_DECK_A, 10, 25, round(ventana.gamma_a * 10),
                                      "Forma de la caída de A. 1,0 = la curva de siempre · más alto = A achica sus medios y agudos antes (útil cuando las voces se pisan).")
        self.sl_s, self.lv_s = fila("Bajo (cambia):", TEMA["verde"], ventana.punto_s, "Momento de la mezcla en que el bajo pasa del tema que sale al que entra (en la línea de compás más próxima). 0 % = el nuevo trae su bajo desde el principio · 95 % = el viejo mantiene el bajo casi hasta el final.")
        self.sl_pp, self.lv_pp = fila_g("Pausa en:", TEMA["ambar"], 10, 90, round(cruce_auto.PAUSA_POS * 100),
                                        "Punto del cruce donde se frena: cuando la línea blanca del gráfico llega a la línea ámbar, el cruce se queda quieto (los dos temas suenan como en ese punto) el tiempo de «Pausa dura».")
        r_pd = QHBoxLayout()
        l_pd = QLabel("Pausa dura:"); l_pd.setStyleSheet(f"color:{TEMA['ambar']}; font-weight:bold;")
        self.cb_pd = QComboBox()
        for n in range(10):
            self.cb_pd.addItem(f"{n} s" if n else "Sin pausa", n)
        self.cb_pd.setCurrentIndex(max(0, min(9, int(round(cruce_auto.PAUSA)))))
        self.cb_pd.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        tip_pd = "Cuántos segundos se queda el cruce en la línea ámbar (0 = no se frena)."
        l_pd.setToolTip(tip_pd); self.cb_pd.setToolTip(tip_pd)
        r_pd.addWidget(l_pd); r_pd.addWidget(self.cb_pd, 1); lay.addLayout(r_pd)
        self.chk_bandas = QCheckBox("🎛 Por bandas")
        self.chk_bandas.setToolTip("Medios y agudos se cruzan con las curvas de arriba; el BAJO (bombo y bajo, <150 Hz) es de uno solo a la vez\ny se traspasa en la línea del compás, sin cortes ni empaste. Sin tilde: el cruce clásico por volumen.")
        self.chk_bandas.setChecked(ventana.cruce_bandas)
        lay.addWidget(self.chk_bandas)
        self.chk_comp = QCheckBox("⚖ Compensar nivel")
        self.chk_comp.setToolTip("Cuando suenan los dos temas a la vez, la suma suena más fuerte que cada uno.\nEsto baja un poco el total (hasta -5 dB, suave y automático) para que el volumen se mantenga parejo en la mezcla.")
        self.chk_comp.setChecked(ventana.comp_nivel)
        self.chk_comp.toggled.connect(ventana.set_comp)
        lay.addWidget(self.chk_comp)
        self.btn_modo = QPushButton()
        self.btn_modo.setCheckable(True)
        self.btn_modo.setStyleSheet(_qss_boton("#ffd35a", "#e08a00", "#fff0b8", "#2a1700", "#ffe08a", "#f09a10")        # MANUAL: ámbar
                                    + "QPushButton:checked { background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #4be08a, stop:1 #17894a); color:#032413; border:1px solid #c5f7da; }"   # AUTO: verde
                                    + "QPushButton:checked:hover { border:2px solid #ffffff; }")
        self.btn_modo.setToolTip("✋ MANUAL: el cruce usa los deslizadores de abajo (A, B y Bajo), igual en todos los temas.\n"
                                 "🤖 AUTO: el programa analiza cada par de temas y diseña SU cruce: la duración (en compases), cuándo entra el que viene,\n"
                                 "cómo se va el que sale y en qué compás se traspasa el bajo. Los deslizadores y la duración no se usan.\n"
                                 "(Necesita 'Forma de cruce' y 'Por bandas'; con BPM muy distintos hace el cruce simple.)")
        self.btn_modo.setChecked(ventana.cruce_auto)
        self.btn_modo.toggled.connect(self._modo_cambio)
        lay.addWidget(self.btn_modo)
        self.lbl_dur = QLabel(); self.lbl_dur.hide()
        fila_voto = QHBoxLayout(); fila_voto.setSpacing(6)
        self.btn_voto_ok = QPushButton("👍 Me gustó"); self.btn_voto_mal = QPushButton("👎 No me gustó")
        self.btn_voto_ok.setToolTip("Valora el último cruce del Auto «como mi manual». El Auto aprende: con pares de temas parecidos corre la duración hacia lo que te gustó.")
        self.btn_voto_mal.setToolTip("El último cruce del Auto no te gustó: elegí por qué (muy corto, muy largo, voces…) y el Auto lo tiene en cuenta la próxima vez.")
        self.btn_voto_ok.setStyleSheet(_qss_boton("#4be08a", "#17894a", "#c5f7da", "#032413", "#7af0b0", "#22a85c"))
        self.btn_voto_mal.setStyleSheet(_qss_boton("#ff8a95", "#c9283b", "#ffc7cd", "#ffffff", "#ffa1aa", "#dc3a4d"))
        self.btn_voto_ok.clicked.connect(lambda: self._votar(+1)); self.btn_voto_mal.clicked.connect(lambda: self._votar(-1))
        fila_voto.addWidget(self.btn_voto_ok); fila_voto.addWidget(self.btn_voto_mal)
        lay.addLayout(fila_voto)
        self.btn_copiar = QPushButton("📋 Copiar el último cruce Auto")
        self.btn_copiar.setToolTip("Pasa al modo manual los valores del último cruce que diseñó el Auto (A, B, subida, fin de A, forma, bajo y duración),\npara que los puedas retocar o dejarlos fijos para todos los temas.")
        self.btn_copiar.setStyleSheet(_qss_boton("#b794ff", "#6a3fd4", "#e0d2ff", "#ffffff", "#c9adff", "#7d52e6"))     # violeta
        self.btn_copiar.clicked.connect(self._copiar_auto)
        lay.addWidget(self.btn_copiar)
        b_def = QPushButton("Valores por defecto"); b_def.clicked.connect(self._defecto)
        b_def.setStyleSheet(_qss_boton("#ff8a95", "#c9283b", "#ffc7cd", "#ffffff", "#ffa1aa", "#dc3a4d"))        # rojo
        lay.addWidget(b_def)
        lay.addStretch()

        self.sl_a.valueChanged.connect(self._cambio); self.sl_b.valueChanged.connect(self._cambio)
        self.sl_s.valueChanged.connect(self._cambio); self.chk_bandas.toggled.connect(self._cambio)
        for sl in (self.sl_rb, self.sl_fa, self.sl_g):
            sl.valueChanged.connect(self._cambio)
        self.chk.toggled.connect(self._cambio)
        self.sl_pp.valueChanged.connect(self._cambio_pausa); self.cb_pd.currentIndexChanged.connect(self._cambio_pausa)
        self._timer = QTimer(self); self._timer.timeout.connect(self._refrescar); self._timer.start(50)
        self._textos()
        self._pintar_modo()

    def _cambio_pausa(self, *_):
        """«Pausa en» (posición) y «Pausa dura» (segundos) del cruce manual: se aplican, se guardan y se repinta el gráfico."""
        self._textos()
        vals = {"PAUSA_POS": self.sl_pp.value() / 100.0, "PAUSA": float(self.cb_pd.currentData() or 0)}
        d = getattr(self.v, "_dlg_ajc", None)
        if d is not None:
            d.auto_set(vals)                                       # (aplica, guarda y deja al día lo que muestre ⚙ Ajustes)
        else:
            from setup import ajustes_cruce
            cruce_auto.aplicar(vals); ajustes_cruce.guardar()
        self._refrescar()

    def refrescar_pausa(self):
        """Deja «Pausa en» y «Pausa dura» con los valores de ahora (los cambió ⚙ Ajustes o «Valores por defecto»)."""
        for w in (self.sl_pp, self.cb_pd):
            w.blockSignals(True)
        self.sl_pp.setValue(int(round(cruce_auto.PAUSA_POS * 100)))
        self.cb_pd.setCurrentIndex(max(0, min(9, int(round(cruce_auto.PAUSA)))))
        for w in (self.sl_pp, self.cb_pd):
            w.blockSignals(False)
        self._textos(); self._refrescar()

    def _textos(self):
        self.lv_a.setText(f"{self.sl_a.value()}%"); self.lv_b.setText(f"{self.sl_b.value()}%"); self.lv_s.setText(f"{self.sl_s.value()}%")
        self.lv_rb.setText(f"{self.sl_rb.value()}%"); self.lv_fa.setText(f"{self.sl_fa.value()}%")
        self.lv_g.setText(f"{self.sl_g.value() / 10.0:.1f}")
        self.lv_pp.setText(f"{self.sl_pp.value()}%")

    def _votar(self, voto):
        """👍 / 👎 al último cruce que hizo el Auto «como mi manual»: lo guarda y el Auto aprende para los pares de temas parecidos."""
        ul = getattr(self.v, "_ultimo_plan", None)
        if not ul or ul.get("estrategia") != "manual":
            self.v._set_status("🗳 Todavía no hay un cruce del Auto «como mi manual» para valorar: dejá que haga una mezcla primero")
            return
        if ul.get("_votado"):
            self.v._set_status("🗳 Ya valoraste ese cruce")
            return
        motivo = None
        if voto < 0:
            menu = QMenu(self)
            acc = {menu.addAction(txt): k for k, txt in aprendizaje.MOTIVOS.items()}
            elegido = menu.exec(self.btn_voto_mal.mapToGlobal(QPoint(0, self.btn_voto_mal.height())))
            if elegido is None:
                return
            motivo = acc[elegido]
        if aprendizaje.registrar(ul, voto, motivo):
            ul["_votado"] = True
            self.v._set_status(("👍" if voto > 0 else "👎") + f" Anotado: el Auto lo tiene en cuenta · {aprendizaje.resumen()}")
        else:
            self.v._set_status("🗳 No se pudo guardar el voto")

    def _copiar_auto(self):
        ul = getattr(self.v, "_ultimo_plan", None)
        if not ul:
            self.v._set_status("📋 Todavía no hay ningún cruce Auto para copiar: dejá que el Auto haga una mezcla primero")
            return
        self.btn_modo.setChecked(False)                                  # pasa a manual
        self.sl_a.setValue(int(round(ul["pa"] * 100))); self.sl_b.setValue(int(round(ul["pb"] * 100)))
        self.sl_rb.setValue(int(round(ul["rb"] * 100))); self.sl_fa.setValue(int(round(ul["fa"] * 100)))
        self.sl_g.setValue(int(round(ul.get("gamma", 1.0) * 10))); self.sl_s.setValue(int(round(ul["ps"] * 100)))
        try:
            self.v.spin_mix.setValue(int(round(ul["dur"])))
        except Exception:
            pass
        self.v._set_status("📋 Cruce Auto copiado al modo manual")

    def _pintar_modo(self):
        auto = self.btn_modo.isChecked()
        self.btn_modo.setText("🤖 Cruce: AUTO" if auto else "✋ Cruce: MANUAL")
        for w in (self.sl_a, self.sl_b):
            w.setEnabled(not auto)
        for w in (self.sl_rb, self.sl_fa, self.sl_g):                    # estos tres solo existen "por bandas"
            w.setEnabled(not auto and self.chk_bandas.isChecked())
        self.sl_s.setEnabled(self.chk_bandas.isChecked() and not auto)
        self.sl_pp.setEnabled(not auto); self.cb_pd.setEnabled(not auto)      # la pausa del Auto se maneja en ⚙ Ajustes

    def _modo_cambio(self, auto):
        if auto:                                    # el Auto trabaja con la forma de cruce y por bandas
            self.chk.setChecked(True)
            self.chk_bandas.setChecked(True)
        self._pintar_modo()
        self.v.set_modo_auto(bool(auto))
        self._refrescar()

    def _defecto(self):
        self.sl_a.setValue(int(round(DEF_PUNTO_A * 100))); self.sl_b.setValue(int(round(DEF_PUNTO_B * 100))); self.sl_s.setValue(int(round(DEF_PUNTO_S * 100)))
        self.sl_rb.setValue(int(round(DEF_RAMPA_B * 100))); self.sl_fa.setValue(int(round(DEF_FIN_A * 100))); self.sl_g.setValue(int(round(DEF_GAMMA_A * 10)))
        self.cb_pd.setCurrentIndex(3); self.sl_pp.setValue(50)    # pausa: 3 s en el 50 %
        self.chk.setChecked(True)               # forma de cruce A/B activada
        self.chk_bandas.setChecked(True)        # por bandas
        self.btn_modo.setChecked(False)         # cruce manual
        self.chk_comp.setChecked(True)          # compensar nivel
        try:                                    # multibanda, tono, volumen, zoom y marca del auto-enganche
            self.v.aplicar_valores_defecto()
        except Exception:
            import traceback; traceback.print_exc()

    def _cambio(self, *_):
        self._textos()
        self._pintar_modo()
        self.v.set_forma_cruce(self.sl_a.value() / 100.0, self.sl_b.value() / 100.0, self.chk.isChecked(),
                               self.sl_s.value() / 100.0, self.chk_bandas.isChecked(),
                               self.sl_rb.value() / 100.0, self.sl_fa.value() / 100.0, self.sl_g.value() / 10.0)
        self._refrescar()

    def _plan_previo(self):
        """El cruce que el Auto diseñaría AHORA para los dos temas cargados (None si falta alguno o su análisis)."""
        v = self.v
        try:
            f = v.crossfader.value()
            sale = v.deck_a if f <= 50 else v.deck_b
            entra = v.deck_b if sale is v.deck_a else v.deck_a
            if sale.audio is not None and entra.audio is not None and sale.analysis and entra.analysis:
                # El plan se recalcula solo si cambió algo real (temas, tempo, ajustes o forma de cruce), NO por el avance de la canción: si no, la línea del bajo
                # (que cae en la próxima línea de compás desde "ahora") se corre sin parar hacia la izquierda y se rediseña 20 veces por segundo.
                clave = (sale.path, entra.path, round(float(sale.rate_eff), 3), round(float(entra.rate_eff), 3), tuple(sorted(cruce_auto.valores().items())),
                         round(v.punto_a, 3), round(v.punto_b, 3), round(v.punto_s, 3), round(v.rampa_b, 3), round(v.fin_a, 3), round(v.gamma_a, 3),
                         bool(v.cruce_bandas), int(v.spin_mix.value()))
                c = getattr(self, "_prev_cache", None)
                if c is not None and c[0] == clave:
                    return c[1]
                plan = v._disenar_cruce_auto(sale, entra)
                self._prev_cache = (clave, plan)
                return plan
        except Exception:
            pass
        return None

    def _refrescar(self):
        if not hasattr(self.v, "spin_mix"):
            return
        x = self.v.crossfader.value() / 100.0
        t = x if self.v._cf_dir == "AB" else 1.0 - x
        pl = self.v._plan_activo() if hasattr(self.v, "mix_timer") else None
        if self.v._cruce_simple():
            if cruce_auto.INC_ACTIVO >= 0.5:                # temas incompatibles: el fundido de ⚙ Ajustes (A baja en rampa, B entra casi al final)
                d = max(1.0, float(cruce_auto.INC_DUR))
                self.graf.actualizar(0.0, 0.0, t, None, False, 1.0, inc=(1.0 - float(cruce_auto.INC_ENTRA), float(cruce_auto.INC_SUBE) / d),
                                     etiqueta=f"📉 INCOMPATIBLES · {cruce_auto.INC_DUR:.0f} s")
            else:
                self.graf.actualizar(0.0, 0.0, t, None, False, 1.0, True)
        elif pl:                                           # durante una mezcla Auto, el gráfico muestra el cruce diseñado
            self.graf.actualizar(pl["pa"], pl["pb"], t, pl["ps"], True, pl["fa"], rb=pl["rb"], gamma=pl.get("gamma", 1.0),
                                 etiqueta=f"🤖 AUTO · {pl['n']} comp · {pl['dur']:.0f} s" + (" + pausa" if pl.get("pausa", True) else " · sin pausa"))
        elif self.btn_modo.isChecked():                    # Auto sin mezcla en curso: el cruce que se diseñaría ahora para los dos temas cargados
            prev = self._plan_previo()
            ul = prev or getattr(self.v, "_ultimo_plan", None)
            if ul:
                self.graf.actualizar(ul["pa"], ul["pb"], None, ul["ps"], True, ul["fa"], rb=ul["rb"], gamma=ul.get("gamma", 1.0),
                                     etiqueta=(f"🤖 {'próximo' if prev else 'último'}: {ul['n']} comp · {ul['dur']:.0f} s"
                                               + ("" if ul.get("pausa", True) else " · sin pausa")))
            elif cruce_auto.ESTRATEGIA >= 1.5:             # todavía sin temas / sin mezclas: la forma propia del Auto «como mi manual» (la de ⚙ Ajustes)
                fa = cruce_auto.AUTO_FA
                self.graf.actualizar(cruce_auto.AUTO_PA, cruce_auto.AUTO_PB, None, cruce_auto.AUTO_PS, True,
                                     None if fa >= 0.995 else fa, rb=cruce_auto.AUTO_RB, gamma=cruce_auto.AUTO_G,
                                     etiqueta="🤖 AUTO · su propia forma (⚙ Ajustes)")
            elif cruce_auto.ESTRATEGIA >= 0.5:             # todavía sin temas / sin mezclas: se dibuja la forma que usa el Auto Pro (la de los deslizadores)
                fa = self.sl_fa.value() / 100.0
                self.graf.actualizar(self.sl_a.value() / 100.0, self.sl_b.value() / 100.0, None, self.sl_s.value() / 100.0, True,
                                     None if fa >= 0.995 else fa, rb=self.sl_rb.value() / 100.0, gamma=self.sl_g.value() / 10.0,
                                     etiqueta=f"🤖 AUTO Pro · tu forma · {cruce_auto.PRO_COMPASES:.0f} comp")
            else:
                self.graf.actualizar(0.0, 0.0, None, None, False, None, vacio="🤖 AUTO · cada cruce se diseña solo")
        else:
            fa = self.sl_fa.value() / 100.0
            self.graf.actualizar(self.sl_a.value() / 100.0, self.sl_b.value() / 100.0, t,
                                 self.sl_s.value() / 100.0, self.chk_bandas.isChecked() and self.chk.isChecked(),
                                 None if fa >= 0.995 else fa, rb=self.sl_rb.value() / 100.0, gamma=self.sl_g.value() / 10.0,
                                 pausa=(self.sl_pp.value() / 100.0, float(self.cb_pd.currentData() or 0)) if self.cb_pd.currentData() else None)
        self.lbl_dur.setText(f"⏱ Mezcla: {self.v.spin_mix.value()} s")
