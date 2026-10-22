"""AutoMix — grabación de la mezcla."""
from pathlib import Path
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from setup.base import ROOT, log
from setup.config import guardar_config


class GrabacionMixin:
    """Grabación de la mezcla (parte de la ventana principal)."""


    CARPETA_GRAB = ROOT / "grabaciones"
    FADE_GRAB_S = 15.0            # al parar: rampa de bajada de 15 s en el archivo...
    COLA_GRAB_S = 3.0             # ...y 3 s de silencio al final, para que no corte en seco

    def _formato_grab(self):
        return "wav" if self.btn_fmt_grab.text().upper() == "WAV" else "mp3"

    def _cambiar_formato_grab(self):
        """Botón MP3 / WAV junto al de grabar: alterna el formato (se recuerda)."""
        nuevo = "wav" if self._formato_grab() == "mp3" else "mp3"
        self._poner_formato_grab(nuevo)
        guardar_config(grab_formato=nuevo)
        self._set_status("🎙 Se grabará en " + ("MP3 (320 kbps)" if nuevo == "mp3" else "WAV (sin pérdida)"))

    def _poner_formato_grab(self, f):
        mp3 = (f != "wav")
        self.btn_fmt_grab.setText("MP3" if mp3 else "WAV")
        self.btn_grabar.setToolTip("Graba la mezcla completa (con ecualizador y limitador) en un " + (".mp3 de 320 kbps" if mp3 else ".wav sin pérdida")
                                   + ".\nEl formato se cambia con el botón de al lado.")

    def _alternar_grabacion(self):
        g = self.mixer.grabador
        if not g.activo:
            try:
                ruta = g.iniciar(self.CARPETA_GRAB, self._formato_grab())
            except Exception as e:
                log("grabación", f"no se pudo iniciar ({e})")
                self._set_status(f"⚠️ No se pudo grabar: {e}")
                return
            log("grabación", f"grabando en {ruta}")
            if Path(ruta).suffix.lower().lstrip(".") != self._formato_grab():
                self._set_status("⚠️ MP3 no disponible en este equipo: se graba en WAV")
            self.btn_fmt_grab.setEnabled(False)
            self.btn_grabar.setStyleSheet("QPushButton { background:#7a1620; border:2px solid #ff4d5e; color:#ffffff; font-weight:bold; }")
            self._tic_grabacion()
            self._t_grab.start()
        elif not g.terminando:
            g.finalizar(self.FADE_GRAB_S, self.COLA_GRAB_S)          # 1.er clic: cierre suave (15 s de rampa + 3 s de silencio)
            log("grabación", f"cierre suave: {self.FADE_GRAB_S:.0f} s de rampa + {self.COLA_GRAB_S:.0f} s de silencio")
            self._tic_grabacion()
        else:
            self._parar_grabacion()                                  # 2.º clic durante el cierre: corta ya

    def _parar_grabacion(self):
        g = self.mixer.grabador
        self._t_grab.stop()
        ruta, seg = g.detener()
        self.btn_grabar.setStyleSheet(self._QSS_GRAB)
        self.btn_grabar.setText("⏺ Grabar mezcla")
        self.btn_fmt_grab.setEnabled(True)
        if ruta and seg > 0:
            m, s = divmod(int(seg), 60)
            self.lbl_grab.setText(f"✅ {Path(ruta).name} ({m}:{s:02d})")
            log("grabación", f"guardada {ruta} ({seg:.1f} s)" + (f" · {g.perdidos} muestras perdidas" if g.perdidos else ""))
            self._set_status(f"✅ Mezcla guardada en grabaciones/{Path(ruta).name}")
        else:
            self.lbl_grab.setText("")

    def _tic_grabacion(self):
        g = self.mixer.grabador
        if g._error:
            self._parar_grabacion()
            self.lbl_grab.setText("⚠️ Error de disco")
            return
        if g.listo:
            self._parar_grabacion()
            return
        if g.terminando:
            self.btn_grabar.setText(f"⏳ Terminando… {int(g.restante) + 1} s   (clic = cortar ya)")
            self.lbl_grab.setText("")
            return
        seg = int(g.segundos)
        h, r = divmod(seg, 3600); m, s = divmod(r, 60)
        t = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
        self.btn_grabar.setText(("⏹ " if seg % 2 == 0 else "⏺ ") + f"Grabando  {t}")
        self.lbl_grab.setText("")

    def _abrir_carpeta_grabaciones(self):
        try:
            self.CARPETA_GRAB.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.CARPETA_GRAB)))
        except Exception as e:
            log("grabación", f"no se pudo abrir la carpeta ({e})")
