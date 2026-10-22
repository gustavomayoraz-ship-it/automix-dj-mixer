"""AutoMix — efectos de sonido: lista de efectos, botón que lo reproduce y volumen."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSlider, QVBoxLayout
from setup.config import guardar_config, leer_config
from setup.efectos import EFECTOS
from setup.tema import TEMA
from setup.widgets import qss_marco


class EfectosMixin:
    """Efectos de sonido para mezclar (parte de la ventana principal)."""

    def _crear_efectos(self):
        cfg = leer_config()
        fx = self.mixer.fx
        self.marco_fx = QFrame()                        # fila plana dentro de la tarjeta 🛠 Herramientas
        self.marco_fx.setObjectName("marcoFx")
        self.marco_fx.setStyleSheet("QFrame#marcoFx { background:transparent; border:none; }")
        col_fx = QVBoxLayout(self.marco_fx); col_fx.setContentsMargins(0, 0, 0, 0); col_fx.setSpacing(6)
        fila = QHBoxLayout(); fila.setContentsMargins(0, 0, 0, 0); fila.setSpacing(6)         # arriba: 🎆 + lista de efectos + volumen (largo)
        col_fx.addLayout(fila)
        fila.addWidget(QLabel("🎆"))
        self.cmb_fx = QComboBox()
        self.cmb_fx.setFixedHeight(28); self.cmb_fx.setMinimumContentsLength(8)
        self.cmb_fx.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.cmb_fx.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        for i, (nombre, _f, tip) in enumerate(EFECTOS):
            self.cmb_fx.addItem(nombre, i)
            self.cmb_fx.setItemData(i, tip, Qt.ItemDataRole.ToolTipRole)
        self.cmb_fx.setMaxVisibleItems(16)               # lista larga: se ve con barra de desplazamiento
        _n = cfg.get("fx_nombre")                        # se recuerda por nombre (el orden de la lista puede crecer)
        _i = next((k for k, e in enumerate(EFECTOS) if e[0] == _n), 0)
        self.cmb_fx.setCurrentIndex(_i)
        self.cmb_fx.setToolTip("Elegí el efecto de sonido; el botón ▶ lo reproduce.")
        self.cmb_fx.currentIndexChanged.connect(lambda i: guardar_config(fx_nombre=EFECTOS[int(i)][0]))
        fila.addWidget(self.cmb_fx, 1)
        self.btn_fx = QPushButton("▶")                  # abajo, ancho y alto: fácil de tocar
        self.btn_fx.setMinimumHeight(40); self.btn_fx.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_fx.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_fx.setStyleSheet("QPushButton { padding:0px; font-size:30px; font-weight:bold; color:#2a0a10; background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                                  " stop:0 #ff8a96, stop:1 #ff3b4e); border:1px solid #ffb3bb; border-radius:9px; }"
                                  "QPushButton:hover { background:#ff6272; } QPushButton:pressed { background:#d92a3b; }")
        self.btn_fx.setToolTip("Reproduce el efecto elegido (suena en la salida principal, mezclado con los temas).\n"
                               "Si lo tocás mientras suena, vuelve a empezar.")
        self.btn_fx.clicked.connect(self._fx_reproducir)
        col_fx.addWidget(self.btn_fx)
        self.sld_fx = QSlider(Qt.Orientation.Horizontal)
        self.sld_fx.setRange(0, 100); self.sld_fx.setFixedHeight(28); self.sld_fx.setMinimumWidth(110); self.sld_fx.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.sld_fx.setValue(int(cfg.get("fx_vol", 60)))
        fx.vol = self.sld_fx.value() / 100.0
        self.sld_fx.setToolTip("Volumen de los efectos (60 % queda por debajo de la música, sin ser invasivo).")
        self.sld_fx.valueChanged.connect(self._fx_vol_cambio)
        fila.addWidget(self.sld_fx, 1)
        return self.marco_fx

    def _fx_reproducir(self):
        i = self.cmb_fx.currentIndex()
        self.mixer.fx.lanzar(i)
        self._set_status(f"{EFECTOS[i][0]}")

    def _fx_vol_cambio(self, v):
        self.mixer.fx.vol = v / 100.0
        guardar_config(fx_vol=int(v))
