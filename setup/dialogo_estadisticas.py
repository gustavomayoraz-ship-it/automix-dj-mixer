"""AutoMix — ventana de estadísticas de los temas (reproducciones, estrellas y 👍)."""
import time
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout)
from setup.estadisticas import EST
from setup.tema import TEMA


class _ItemOrden(QTableWidgetItem):
    """Celda que se ordena por un número (UserRole + 1) y no por el texto que muestra."""
    def __lt__(self, otro):
        a, b = self.data(Qt.ItemDataRole.UserRole + 1), otro.data(Qt.ItemDataRole.UserRole + 1)
        try:
            return a < b
        except TypeError:
            return super().__lt__(otro)


class DialogoEstadisticas(QDialog):
    def __init__(self, parent, al_cambiar):
        super().__init__(parent)
        self.al_cambiar = al_cambiar                 # se llama cuando cambia un 👍 (para que la lista lo muestre al instante)
        T = TEMA
        self.setWindowTitle("AutoMix 🎚️ — Estadísticas de los temas")
        self.resize(820, 460)
        self.setStyleSheet(
            f"QDialog {{ background:{T['bg1']}; }} QLabel {{ color:{T['texto']}; }} QCheckBox {{ color:{T['texto']}; }}"
            f"QTableWidget {{ background:{T['bg2']}; color:{T['texto']}; gridline-color:{T['linea']}; border:1px solid {T['linea']}; }}"
            f"QHeaderView::section {{ background:{T['bg3']}; color:{T['suave']}; border:0; padding:4px; }}"
            f"QPushButton {{ background:{T['bg3']}; color:{T['texto']}; border:1px solid {T['linea']}; border-radius:8px; padding:7px 14px; }}"
            f"QPushButton:hover {{ border:1px solid {T['cian']}; }}")
        lay = QVBoxLayout(self); lay.setContentsMargins(16, 14, 16, 14); lay.setSpacing(10)
        self.lbl = QLabel(); self.lbl.setStyleSheet("font-size:14px; font-weight:bold;")
        lay.addWidget(self.lbl)
        nota = QLabel("Un tema suma una reproducción cuando suena más del 50 % (los saltos no cuentan). Las estrellas salen solas: cuanto más suena "
                      "un tema comparado con los demás, más estrellas. El 👍 lo marcas tú y no cambia las estadísticas. "
                      "Clic en el título de una columna para ordenar.")
        nota.setWordWrap(True); nota.setStyleSheet(f"color:{T['suave']}; font-size:11px;")
        lay.addWidget(nota)
        self.chk_like = QCheckBox("Ver solo los que tienen 👍")
        self.chk_like.toggled.connect(self._llenar)
        lay.addWidget(self.chk_like)
        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(["👍", "Estrellas", "Reproducciones", "Tema", "Última vez"])
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.verticalHeader().setVisible(False)
        h = self.tabla.horizontalHeader()
        for c in (0, 1, 2, 4):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.tabla, 1)
        fila = QHBoxLayout(); fila.setSpacing(8)
        b1 = QPushButton("👍 Marcar / quitar el 👍 de los elegidos"); b1.clicked.connect(self._alternar_like)
        b2 = QPushButton("Cerrar"); b2.clicked.connect(self.accept)
        fila.addWidget(b1); fila.addStretch(1); fila.addWidget(b2)
        lay.addLayout(fila)
        self._llenar()

    def _llenar(self, *_):
        filas = EST.filas()
        if self.chk_like.isChecked():
            filas = [f for f in filas if f["like"]]
        self.tabla.setSortingEnabled(False)
        self.tabla.setRowCount(len(filas))
        for r, f in enumerate(filas):
            fecha = time.strftime("%d/%m/%Y %H:%M", time.localtime(f["ult"])) if f["ult"] else ""
            celdas = [("👍" if f["like"] else "", int(f["like"])), ("★" * f["estrellas"], f["estrellas"]), (str(f["n"]), f["n"]),
                      (f["nombre"], f["nombre"].lower()), (fecha, f["ult"])]
            for c, (txt, orden) in enumerate(celdas):
                it = _ItemOrden(txt)
                it.setData(Qt.ItemDataRole.UserRole + 1, orden)
                it.setToolTip(f["ruta"])
                it.setData(Qt.ItemDataRole.UserRole, f["ruta"])
                if c in (0, 1, 2):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if c == 1:
                    it.setForeground(QColor("#ffd400"))
                self.tabla.setItem(r, c, it)
        self.tabla.setSortingEnabled(True)
        self.tabla.sortItems(2, Qt.SortOrder.DescendingOrder)               # al abrir: los más escuchados arriba
        total = sum(f["n"] for f in filas)
        likes = sum(1 for f in filas if f["like"])
        self.lbl.setText(f"📊 {len(filas)} temas · {total} reproducciones · {likes} con 👍" if filas
                         else "📊 Todavía no hay estadísticas: aparecen cuando un tema suena más del 50 % o le marcas el 👍")

    def _alternar_like(self):
        filas = sorted({i.row() for i in self.tabla.selectedIndexes()})
        rutas = [self.tabla.item(r, 0).data(Qt.ItemDataRole.UserRole) for r in filas]
        if not rutas:
            return
        todos = all(EST.like(r) for r in rutas)
        EST.poner_like(rutas, not todos)
        self._llenar(); self.al_cambiar()
