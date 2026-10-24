"""AutoMix — biblioteca: análisis de los temas, orden, carga en los decks."""
import os
from PySide6.QtWidgets import QAbstractItemView, QApplication
from PySide6.QtCore import QTimer, Qt
from setup.ajustes import SUPPORTED
from setup.analisis import _mantener_vivo
from setup.base import log
from setup.config import guardar_config, leer_config
from setup.deck import Deck
from setup.dialogo_analisis import DialogoAnalisis
from setup.hilos_analisis import AnalizadorBiblioteca

UMBRAL_MASIVO = 100        # a partir de esta cantidad de temas por analizar aparece la ventana de análisis a máxima velocidad


class BibliotecaMixin:
    """Biblioteca: análisis de los temas, orden, carga en los decks (parte de la ventana principal)."""


    _analizador_bib = None
    _fallidos = None
    _ordenar_al_terminar = False
    _modo_siguiente = None            # 'max' / 'suave': al terminar el análisis en curso (cancelado a propósito) se reinicia en ese modo
    _dlg_analisis = None
    _oculta_por_analisis = False

    def _analisis_en_curso(self):
        return self._analizador_bib is not None and self._analizador_bib.isRunning()

    def _iniciar_analisis(self, rutas, forzar, fin, texto, masivo=False):
        self._dlg_analisis = None
        if masivo:
            n = max(1, min(12, os.cpu_count() or 2))
            base = 0 if forzar else max(0, len(self.biblioteca.todas()) - len(rutas))     # los ya analizados cuentan en el avance
            dlg = self._dlg_analisis = DialogoAnalisis(None, len(rutas), n, permitir_fondo=not forzar, base=base)
            dlg.show(); dlg.raise_(); dlg.activateWindow()
            self._oculta_por_analisis = self.isVisible()
            self.hide()                                       # el reproductor se oculta mientras se analiza a máxima velocidad
            QApplication.processEvents()                      # que se vea la ventana antes del trabajo pesado de marcar la lista
        self.biblioteca.marcar(rutas)
        a = AnalizadorBiblioteca(rutas, forzar=forzar, modo_max=masivo)
        _mantener_vivo(a)
        self._lote_listos = []
        if masivo:
            a.progreso.connect(dlg.poner)
            dlg.cancelar.connect(lambda: setattr(a, "cancelar", True))
            dlg.segundo_plano.connect(lambda: self._pasar_a_modo("suave"))
        elif not forzar:
            self.btn_reanalizar.setText("⚡ Acelerar")
            self.btn_reanalizar.setToolTip("Pasa el análisis a máxima velocidad: aparece una ventanita con el avance y el reproductor se oculta hasta que termine")
        a.progreso.connect(lambda i, t: self._set_status(f"{texto}: {i}/{t}"))
        a.tema_listo.connect(self._tema_analizado)        # los temas terminados se acumulan y la lista se actualiza por lotes
        a.terminado.connect(fin)
        self._analizador_bib = a
        self._actualizar_titulo_lib()
        a.start()

    def _ms_lote(self):
        """Cada cuánto se actualiza la lista con los temas ya analizados: casi enseguida si la lista es chica; con miles de
        temas, cada actualización recorre toda la lista (0,2-0,4 s), así que se hace cada pocos segundos."""
        n = self.biblioteca.count()
        if n < 800:
            return 600
        try:
            from setup import hilos_analisis as _ha
            if _ha._SONANDO:
                return 15000                  # con música sonando, el repintado de la lista (miles de filas) se hace pocas veces
        except Exception:
            pass
        return min(4000, 600 + n // 3)

    def _tema_analizado(self, ruta):
        """Un tema terminó su análisis: se anota y se actualiza la lista en el próximo lote (no uno por uno)."""
        if not hasattr(self, "_lote_listos") or self._lote_listos is None:
            self._lote_listos = []
        self._lote_listos.append(ruta)
        if getattr(self, "_dlg_analisis", None) is not None:
            return                                            # análisis masivo: la lista se actualiza una sola vez, al final
        t = getattr(self, "_t_lote", None)
        if t is None:
            t = self._t_lote = QTimer(self)
            t.setSingleShot(True)
            t.timeout.connect(self._vaciar_lote)
        if not t.isActive():
            t.start(self._ms_lote())

    def _vaciar_lote(self):
        """Actualiza la lista de una vez con todos los temas analizados desde el último lote."""
        rutas, self._lote_listos = (getattr(self, "_lote_listos", None) or []), []
        if not rutas:
            return
        self.biblioteca.quitar_de_cola_lote(rutas)
        self._actualizar_titulo_lib()                                    # Biblioteca (5/17)
        # la lista se va ordenando a medida que se analiza: con miles de temas, como mucho una vez cada 20 s (reordenar cuesta)
        n = self.biblioteca.count()
        if n < 800:
            ms_ord = 600
        else:
            try:
                from setup import hilos_analisis as _ha
                ms_ord = 60000 if _ha._SONANDO else 20000      # reordenar miles de temas cuesta: menos seguido si hay música sonando
            except Exception:
                ms_ord = 20000
        self._reordenar_pronto(ms_ord, fijo=True)

    def _pendientes(self):
        if self._fallidos is None:
            self._fallidos = set()
        return [r for r in self.biblioteca.temas_sin_analisis()
                if self.biblioteca._clave(r) not in self._fallidos and os.path.isfile(r)]

    def _cerrar_dlg(self, dlg):
        """Cierra la ventanita del análisis y devuelve el reproductor. Primero el reproductor: si no, al cerrarse la
        última ventana visible el programa entero se cerraría."""
        try:
            if self._oculta_por_analisis or not self.isVisible():
                self.show()
            self._oculta_por_analisis = False
            self.raise_(); self.activateWindow()
        finally:
            dlg.btn.setEnabled(False); dlg.btn_fondo.setEnabled(False)
            dlg.close(); dlg.deleteLater()

    def _pasar_a_modo(self, modo):
        """Con un análisis en curso: lo detiene a propósito y lo reinicia en 'max' (ventanita, a toda velocidad) o 'suave' (segundo plano)."""
        a = self._analizador_bib
        if a is None or not a.isRunning():
            return
        self._modo_siguiente = modo
        a.cancelar = True

    def _reiniciar_analisis(self, modo, intentos=0):
        if self._analisis_en_curso() and intentos < 75:       # esperar a que el hilo anterior termine de cerrarse
            QTimer.singleShot(200, lambda: self._reiniciar_analisis(modo, intentos + 1))
            return
        self._auto_analizar(modo)

    def _auto_analizar(self, modo=None):
        """Los temas nuevos de la lista se analizan solos (se ven con ⏳ hasta que terminan).
        modo: None = automático (ventanita si son más de UMBRAL_MASIVO y no suena nada), 'max' = a máxima velocidad, 'suave' = segundo plano."""
        if not isinstance(modo, str):
            modo = None
        if self.biblioteca._cargando_lib:                    # la lista todavía se está cargando al abrir: cuando termine, avisa sola
            return
        if self._analisis_en_curso():
            return
        faltan = self._pendientes()
        if not faltan:
            self._ordenar_al_terminar = False
            return
        self._set_status(f"⏳ Analizando {len(faltan)} temas (BPM)…")
        sonando = bool(self.deck_a.playing or self.deck_b.playing)
        if modo == "suave":
            masivo = False
        elif modo == "max":
            masivo = not sonando
        else:
            masivo = len(faltan) > UMBRAL_MASIVO and not sonando     # (con música sonando se analiza en modo suave)
        self._iniciar_analisis(faltan, False, self._fin_analisis, "⏳ Analizando BPM", masivo=masivo)

    def _fin_analisis(self):
        dlg = getattr(self, "_dlg_analisis", None)
        modo, self._modo_siguiente = self._modo_siguiente, None
        self.btn_reanalizar.setText("🔄 Re-analizar")
        self.btn_reanalizar.setToolTip("Si hay temas sin analizar, los analiza a máxima velocidad (ventanita con el avance, el reproductor se oculta); si no hay pendientes no hace nada (Ctrl + clic = volver a analizar TODO desde cero)")
        if dlg is not None:
            dlg.fase("Actualizando la lista…" if modo else "Actualizando y ordenando la lista…")
            QApplication.processEvents()
            self._dlg_analisis = None                         # a partir de acá la lista se actualiza normal
        self._vaciar_lote()                                   # los últimos temas analizados
        self.biblioteca.marcar(())
        if dlg is not None:
            if not modo:
                try:
                    self._ordenar_lista()                     # orden final, con la ventana de progreso todavía a la vista
                except Exception:
                    import traceback; traceback.print_exc()
                self._ordenar_al_terminar = False
            self._cerrar_dlg(dlg)
        elif not modo:
            self._reordenar_pronto(300)                       # orden final con todo lo analizado
        self._actualizar_titulo_lib()
        if modo:                                              # cancelado a propósito para cambiar de modo: se sigue con lo que falta
            self._set_status("⚡ Analizando a máxima velocidad…" if modo == "max" else "⏬ Analizando en segundo plano…")
            self._reiniciar_analisis(modo)
            return
        if self._fallidos is None:
            self._fallidos = set()
        hechos = {self.biblioteca._clave(r) for r in (getattr(getattr(self, "_analizador_bib", None), "rutas", None) or ())}
        for r in self.biblioteca.temas_sin_analisis():       # los que se intentaron y no se pudieron analizar no se reintentan en bucle
            k = self.biblioteca._clave(r)                    # (los agregados mientras se analizaba NO: esos todavía no se probaron)
            if k in hechos:
                self._fallidos.add(k)
        if self._ordenar_al_terminar:
            self._ordenar_al_terminar = False
            self._ordenar_lista()
            self._set_status("✅ Biblioteca ordenada")
        else:
            self._set_status("✅ Lista analizada")
        QTimer.singleShot(300, self._auto_analizar)           # por si se agregaron temas mientras tanto

    def _ordenar_lista(self):
        """Con 🎼 Armónico y/o 🥁 En frase la lista se ordena como cadena de mezcla (empezando por el tema que
        suena); sin ninguna, por BPM de menor a mayor."""
        arm, fra = self.chk_armonico.isChecked(), self.chk_frases.isChecked()
        if getattr(self, "_orden_tono", False):
            self.biblioteca.ordenar_por_tono()
            return
        if not (arm or fra):
            self.biblioteca.ordenar_por_bpm()
            return
        prim = self._deck_primario()
        inicio = prim.path if (prim is not None and prim.path) else None
        self.biblioteca.ordenar_inteligente(arm, fra, inicio)

    def _reordenar_pronto(self, ms=600, fijo=False):
        """Reordena la lista (con retardo, para agrupar varios cambios) a medida que se analizan los temas.
        Con fijo=True, si ya hay un reordenado programado no se reprograma (así corre cada `ms` aunque lleguen cambios sin parar)."""
        t = getattr(self, "_t_reordenar", None)
        if t is None:
            t = self._t_reordenar = QTimer(self)
            t.setSingleShot(True)
            t.timeout.connect(self._reordenar_ahora)
        if fijo and t.isActive():
            return
        t.start(ms)

    def _reordenar_ahora(self):
        if QApplication.mouseButtons() & Qt.MouseButton.LeftButton:     # no mover la lista mientras se arrastra un tema
            self._reordenar_pronto(500)
            return
        if self.mix_timer.isActive() or self.mix_pausa_timer.isActive():     # durante una mezcla no se reordena la lista (con miles de temas traba la ventana)
            self._reordenar_pronto(2500)
            return
        try:
            self._ordenar_lista()
        except Exception:
            import traceback; traceback.print_exc()

    def _alternar_agrupada(self, v):
        self.biblioteca.set_agrupado(bool(v))
        if v:
            self._ordenar_lista()                             # dentro de cada carpeta, el orden de siempre (BPM o tono)
        guardar_config(lib_agrupada=bool(v))
        self._set_status("📂 Lista separada por carpetas (clic en un título para cerrarlo o abrirlo)" if v else "📃 Lista plana")

    # ---------- botón << (contraer / expandir todas las carpetas) ----------
    def _toggle_plegar_carpetas(self):
        """Botón << del buscador: contrae / expande TODAS las carpetas. Si la vista por carpetas está apagada,
        la activa primero y deja todo contraído."""
        bib = self.biblioteca
        if not bib.agrupado:
            self.btn_agrupar.setChecked(True)      # activa «Por carpetas» (dispara _alternar_agrupada)
            bib.plegar_todas()
            self.btn_plegar.setText(">>")
            self.btn_plegar.setToolTip("Expandir todas las carpetas")
            self._set_status("📂 Carpetas contraídas")
            return
        if bib.todas_plegadas():
            bib.desplegar_todas()
            self.btn_plegar.setText("<<")
            self.btn_plegar.setToolTip("Contraer todas las carpetas")
            self._set_status("📂 Carpetas expandidas")
        else:
            bib.plegar_todas()
            self.btn_plegar.setText(">>")
            self.btn_plegar.setToolTip("Expandir todas las carpetas")
            self._set_status("📂 Carpetas contraídas")

    def _ordenar_biblioteca_tono(self):
        self._orden_tono = True                               # se mantiene mientras se analiza y suenan los temas
        self.biblioteca.ordenar_por_tono()
        faltan = [r for r in self._pendientes()]
        self._set_status("🎼 Biblioteca ordenada por tono" + (f" — analizando {len(faltan)} temas sin tono…" if faltan else ""))
        if faltan and not self._analisis_en_curso():
            self._ordenar_al_terminar = True
            self._iniciar_analisis(faltan, False, self._fin_analisis, "⏳ Analizando tono")

    def _ordenar_biblioteca_bpm(self):
        self._orden_tono = False
        self._ordenar_lista()                                 # ya: primero los que tienen BPM conocido
        self._fallidos = set()                                # un clic explícito vuelve a intentar los que fallaron
        faltan = self._pendientes()
        if not faltan:
            self._set_status("✅ Biblioteca ordenada por BPM")
            return
        self._ordenar_al_terminar = True
        if self._analisis_en_curso():
            self._set_status("⏳ Analizando la lista… se ordena sola al terminar")
            return
        self._set_status(f"⏳ Analizando {len(faltan)} temas (BPM)…")
        self._iniciar_analisis(faltan, False, self._fin_analisis, "⏳ Analizando BPM")

    def _reanalizar_biblioteca(self):
        sonando = bool(self.deck_a.playing or self.deck_b.playing)
        if self._analizador_bib is not None and self._analizador_bib.isRunning():
            a = self._analizador_bib
            if a.forzar:                                          # re-análisis completo en curso: segundo clic = cancelar
                a.cancelar = True
                self._set_status("⏹ Cancelando re-análisis…")
            elif getattr(a, "modo_max", False):
                pass                                              # ya va a máxima velocidad (la ventanita está a la vista)
            elif sonando:
                self._set_status("🔇 Pausá la música para analizar a máxima velocidad (el reproductor se oculta)")
            else:
                self._set_status("⚡ Pasando a máxima velocidad…")
                self._pasar_a_modo("max")                         # análisis normal en curso → a toda velocidad con la ventanita
            return
        self._fallidos = set()                                    # lo que quedó sin analizar (cancelado, etc.) se vuelve a intentar
        desde_cero = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier)      # Ctrl + clic = volver a analizar TODO
        if self._pendientes() and not desde_cero:
            if sonando:
                self._set_status("🔇 Pausá la música para analizar a máxima velocidad (el reproductor se oculta)")
                return
            self._auto_analizar("max")
            return
        rutas = self.biblioteca.todas()
        if not rutas:
            self._set_status("La lista está vacía")
            return
        if not desde_cero:
            self._set_status("✅ Todo está analizado (Ctrl + clic en el botón para volver a analizar todo desde cero)")
            return
        masivo = len(rutas) > UMBRAL_MASIVO and not sonando
        if masivo:
            self._set_status(f"🔄 Re-analizando {len(rutas)} temas a máxima velocidad…")
        else:
            self._set_status(f"🔄 Re-analizando {len(rutas)} temas… (clic otra vez en el botón para cancelar)")
            self.btn_reanalizar.setText("⏹ Cancelar")
        self._iniciar_analisis(rutas, True, self._fin_reanalisis, "🔄 Re-analizando BPM", masivo=masivo)

    def _fin_reanalisis(self):
        dlg = getattr(self, "_dlg_analisis", None)
        if dlg is not None:
            dlg.fase("Actualizando y ordenando la lista…")
            QApplication.processEvents()
            self._dlg_analisis = None
            self._vaciar_lote()
        self.biblioteca.marcar(())
        if dlg is not None:
            try:
                self._ordenar_lista()
            except Exception:
                import traceback; traceback.print_exc()
            self._cerrar_dlg(dlg)
        cancelado = bool(self._analizador_bib and self._analizador_bib.cancelar)
        self.btn_reanalizar.setText("🔄 Re-analizar")
        self._set_status("⏹ Re-análisis cancelado" if cancelado else
                         "✅ Lista re-analizada. Si un tema ya estaba cargado en un deck, volvé a cargarlo para usar el BPM nuevo")

    def _filtrar_biblioteca(self, txt):
        t = txt.strip().lower()
        for i in range(self.biblioteca.count()):
            it = self.biblioteca.item(i)
            if self.biblioteca._es_cab(it):
                continue
            it.setHidden(bool(t) and t not in it.text().lower())

    def _actualizar_titulo_lib(self):
        """Título de la lista: 'Biblioteca (17)'; mientras se analiza, 'Biblioteca (5/17)' = analizados / total."""
        total = len(self.biblioteca.todas())
        pend = len(self.biblioteca._cola)
        if pend and pend <= total:
            hechos = total - pend
            self.lbl_lib.setText(f"📁 Biblioteca ({hechos}/{total})")
            self.setWindowTitle(f"AutoMix 🎚️  —  🔬 Analizando {hechos:,} / {total:,}  ({100 * hechos // max(1, total)} %)".replace(",", "."))
        else:
            self.lbl_lib.setText(f"📁 Biblioteca ({total})")
            self.setWindowTitle("AutoMix 🎚️")

    def _biblioteca_cambio(self):
        self._actualizar_titulo_lib()
        self.biblioteca.guardar()
        if self.biblioteca.count() == 0:
            an = self._analizador_bib
            if an is not None and an.isRunning():
                an.cancelar = True                   # lista vaciada: no se sigue analizando temas que ya no están
            self._lote_listos = []
            self._vaciar_decks()

    def _vaciar_decks(self):
        """La lista quedó vacía: se descargan los reproductores que NO están sonando. El que está sonando sigue hasta que termine el tema
        (así hay tiempo de cargar carpetas nuevas sin que se corte la música); la mezcla en curso tampoco se toca."""
        a, b = self.deck_a, self.deck_b
        if a.audio is None and b.audio is None and not a.path and not b.path:
            return
        sonando = [d for d in (a, b) if d.playing and d.audio is not None]
        if sonando:
            log("programa", "lista vacía: sigue sonando el Deck " + " y ".join(d.name for d in sonando) + " hasta que termine el tema")
            for d in (a, b):
                if d not in sonando:
                    try:
                        d.descargar()
                    except Exception:
                        import traceback; traceback.print_exc()
            try:
                self.timeline.redraw()
            except Exception:
                pass
            self.biblioteca.pintar(a.path if a in sonando else None, b.path if b in sonando else None)
            self._set_status("🗑️ Lista vacía: " + " y ".join(f"el Deck {d.name}" for d in sonando) + " sigue sonando hasta que termine. Cargá las carpetas nuevas")
            return
        log("programa", "lista vacía: se descargan los dos decks")
        self.mix_timer.stop(); self.mix_pausa_timer.stop()
        self._plan = None
        self._frase_armada = False
        self._mix_esperando = False
        self._mix_auto = False
        self._target_rate_a = self._target_rate_b = None
        try:
            self._soltar_sync(None)
        except Exception:
            pass
        self.magnet_on = False
        a.descargar(); b.descargar()
        try:
            self.timeline.redraw()
        except Exception:
            import traceback; traceback.print_exc()
        self.biblioteca.pintar(None, None)
        self._set_status("🗑️ Lista vacía: reproductores descargados")

    def _restaurar_decks(self):
        """Al abrir: vuelven a quedar cargados los temas que tenían los decks al cerrar (si siguen existiendo y la lista no está vacía)."""
        if self.biblioteca.count() == 0:
            return
        cfg = leer_config().get("decks_cargados") or {}
        for d in (self.deck_a, self.deck_b):
            p = cfg.get(d.name)
            if p and os.path.isfile(p) and p.lower().endswith(SUPPORTED) and not d.path:
                log("programa", f"se recupera el Deck {d.name}: {os.path.basename(p)}")
                d.load_track(p)

    def _ubicar_en_lista(self, path):
        """Clic en el nombre del tema de un deck: lo busca en la biblioteca, lo selecciona y lo deja a la vista."""
        if not path:
            self._set_status("No hay ningún tema cargado en ese deck")
            return
        bib = self.biblioteca
        clave = bib._clave(path)
        for i in range(bib.count()):
            it = bib.item(i)
            if bib._es_cab(it):
                continue
            if bib._clave(it.data(Qt.ItemDataRole.UserRole)) == clave:
                if it.isHidden():                       # el filtro de búsqueda (o una carpeta cerrada) lo estaba ocultando
                    self.ed_filtro.clear()
                    if bib.agrupado:
                        bib._plegadas.discard(bib._carpeta(path)); bib._quitar_cab(); bib._poner_cab()
                        for j in range(bib.count()):
                            if not bib._es_cab(bib.item(j)) and bib._clave(bib.item(j).data(Qt.ItemDataRole.UserRole)) == clave:
                                it = bib.item(j); break
                bib.clearSelection()
                bib.setCurrentItem(it)
                it.setSelected(True)
                bib.scrollToItem(it, QAbstractItemView.ScrollHint.PositionAtCenter)
                self._set_status(f"📍 Ubicado en la lista: {os.path.basename(path)}")
                return
        self._set_status("Ese tema no está en la biblioteca")

    def _biblioteca_doble_clic(self, it):
        if self.biblioteca._es_cab(it):
            return
        p = it.data(Qt.ItemDataRole.UserRole)
        if not os.path.isfile(p): return
        a, b = self.deck_a, self.deck_b
        if a.playing and b.playing:
            self._set_status("Los dos decks están sonando.")
            return
        if not a.playing and not b.playing:
            # no suena nada: el tema elegido va al deck A y el que le sigue (según la lista / el modo armónico) al B
            a.load_track(p)
            try:
                ruta, motivo = self._siguiente_en_biblioteca(p)
            except Exception:
                import traceback; traceback.print_exc()
                ruta, motivo = None, "no se pudo elegir el siguiente"
            if ruta is not None and os.path.normcase(os.path.abspath(ruta)) != os.path.normcase(os.path.abspath(p)):
                b.load_track(ruta)
                k0, k1 = self._clave_de(a), self.biblioteca.info(ruta)[1]
                extra = f"  🎼 {k0}→{k1}" if (k0 and k1) else ""
                self._set_status(f"▶ Deck A: {os.path.basename(p)} · Deck B en espera: {os.path.basename(ruta)}{extra}")
            else:
                self._set_status(f"▶ Deck A: {os.path.basename(p)} · Deck B: {motivo or 'sin tema siguiente'}")
            return
        (b if a.playing else a).load_track(p)      # suena uno: el elegido va al deck que está en espera

    def _on_analysis(self, deck, res):
        self.timeline.redraw()
        try:
            self._apply_shared_bpm(self.crossfader.value() / 100.0)
        except Exception:
            import traceback; traceback.print_exc()
        try:                                  # el análisis llegó con el tema ya sonando: se empareja ahora mismo
            d = deck if isinstance(deck, Deck) else (self.deck_a if deck == "A" else self.deck_b)   # llega el nombre ("A"/"B")
            otro = self.deck_b if d is self.deck_a else self.deck_a
            if d.playing and otro.playing and not self.magnet_on and d.analysis and otro.analysis:
                self._auto_sync(d)
                self._alinear_ya(d)
        except Exception:
            import traceback; traceback.print_exc()
