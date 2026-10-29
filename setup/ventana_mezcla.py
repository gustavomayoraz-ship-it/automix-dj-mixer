"""AutoMix — botón Mezclar (F2), auto-enganche y reproducción."""
import math
import os
import sys
import threading
import traceback
import time
import numpy as np
from PySide6.QtWidgets import QApplication, QLineEdit, QSpinBox
from PySide6.QtCore import QTimer
from setup.ajustes import fmt_time
from setup.analisis import compat_armonica
from setup.base import _log_diferido, log
from setup.config import guardar_config
from setup import cruce_auto, nivel, tono


class MezclaMixin:
    """Botón Mezclar (F2), auto-enganche y reproducción (parte de la ventana principal)."""


    # ================= MEZCLA CON PAUSA AL 50% =================
    def _f2_global_cambio(self, activo, guardar=True):
        if activo:
            if not self.f2_global.registrar() and sys.platform == "win32":
                try: self._set_status("⚠️ F2 ya lo usa otro programa: solo funciona con AutoMix en primer plano")
                except Exception: print("[F2] otro programa ya usa F2: solo funciona con AutoMix en primer plano")
            self.vol_global.registrar()
        else:
            self.f2_global.quitar()
            self.vol_global.quitar()
        if guardar:
            try: guardar_config(f2_global=bool(activo))
            except Exception: pass

    def _vol_tecla(self, delta):
        """Flechas ↑ / ↓: suben o bajan el volumen general de a 2 %."""
        try:
            self.sld_master.setValue(max(0, min(100, self.sld_master.value() + 2 * delta)))
            self._set_status(f"🔊 Volumen {self.sld_master.value()}%")
        except Exception:
            pass

    def _mix_clicked(self):
        """Botón 🎬 Mezclar / F2: hace EXACTAMENTE lo mismo que el auto-enganche al llegar a la marca roja
        (mismo diseño de cruce, entrante desde su primer compás, espera al inicio de frase). Un segundo clic en la espera arranca ya."""
        if self.mix_pausa_timer.isActive() or self.mix_timer.isActive():
            self._mix_arrancar()                     # en la pausa del 50 %: seguir ya · ya mezclando: no reiniciar
            return
        self._disparar_mezcla_auto(exacto=True, manual=True)

    def _mix_arrancar(self):
        if self.mix_pausa_timer.isActive():          # en la pausa del 50 %: seguir ya, sin invertir el sentido
            self.mix_pausa_timer.stop()
            self._reanudar_mix()
            return
        if self.mix_timer.isActive():                # ya hay una mezcla en curso: no reiniciarla
            return
        current = self.crossfader.value()
        if current <= 50:
            target = 100
            direction = "A → B"
        else:
            target = 0
            direction = "B → A"

        entra = self.deck_b if target == 100 else self.deck_a
        if entra.audio is None:
            self._mix_auto = False
            self._set_status(f"⚠️ Cargá un tema en Deck {entra.name}")
            return
        if not entra.analysis:               # sin grilla no se puede emparejar: se espera a que termine el análisis
            n = getattr(self, "_mix_espera_n", 0)
            if n < 360:                      # hasta ~90 s
                if n == 0:
                    self._mix_esperando = True
                self._mix_espera_n = n + 1
                self._set_status(f"⏳ Esperando el análisis del Deck {entra.name} para mezclar emparejado…")
                QTimer.singleShot(250, self._mix_arrancar)
                return
        self._mix_espera_n = 0
        self._mix_esperando = False
        entra.pos_manual = False
        entra.tempo_manual = False                   # al mezclar, el entrante vuelve a seguir al sync
        simple = self._cruce_simple()
        auto0 = bool(getattr(self, "_mix_auto", False))
        sale0 = self.deck_a if entra is self.deck_b else self.deck_b
        self._inc_mix = bool(simple and auto0 and cruce_auto.INC_ACTIVO >= 0.5)       # fundido especial de temas incompatibles (⚙ Ajustes)
        self._inc_entra = entra
        if simple:                           # BPM muy distintos: sin emparejar nada, solo se arranca el entrante
            if not entra.playing and not self._inc_mix:        # (en el fundido especial el nuevo arranca más tarde, cuando al que sale le queda poco volumen)
                entra.play()
            print(f"[mezcla] BPM muy distintos ({self.deck_a.original_bpm:.0f} / {self.deck_b.original_bpm:.0f}): cruce simple")
        else:
            if not entra.playing:
                entra.play()                     # al arrancar, _auto_sync ya lo alinea
            else:
                self._auto_sync(entra)           # ya sonaba (en espera): al empezar la mezcla se alinea A LA FUERZA
            self._alinear_ya(entra)              # y se confirma con el primer downbeat, antes de que se escuche

        self._cf_dir = "AB" if target == 100 else "BA"
        self.mix_from = current
        self.mix_to = target

        auto = bool(getattr(self, "_mix_auto", False)); self._mix_auto = False
        sale_d = self.deck_a if entra is self.deck_b else self.deck_b
        self._plan = None
        if self.cruce_auto and self.cruce_ab and self.cruce_bandas and not simple:
            self._tono_decidir(sale_d, entra)                     # antes de diseñar: el diseño ya cuenta con la tonalidad con que va a sonar el que entra
            try:
                self._plan = self._disenar_cruce_auto(sale_d, entra)      # modo Auto: el cruce se diseña para ESTE par de temas
            except Exception:
                import traceback; traceback.print_exc()
                self._plan = None
        self._pc_mix = None                                       # dónde se cruzan las dos líneas (para frenar ahí el crossfader)
        if self._plan:
            pl = self._plan
            self._ultimo_plan = pl
            duration_s = float(pl["dur"])
            self._nivelar_entrada(sale_d, entra, duration_s + float(pl.get("pausa_s", 0.0)))
            log("cruce auto", f"{pl['nombre']} · {pl['razon']} · A baja de {pl['pa']:.0%} a {pl['fa']:.0%} · B entra desde {pl['pb']:.0%} "
                              f"(sube en {pl['rb']:.0%}) · bajo en {pl['ps']:.0%}")
        else:
            duration_s = self._duracion_mezcla_para(sale_d, entra, auto)
            if auto:
                ks, ke = self._clave_de(sale_d), self._clave_de(entra)
                nivel = compat_armonica(ks, ke)
                marca = {2: "✔ compatibles", 1: "≈ vecinas", 0: "✖ chocan → mezcla corta"}.get(nivel, "")
                print(f"[mezcla] {ks or '?'} → {ke or '?'} {marca} · {duration_s:.1f} s")
        if self._inc_mix:                                          # que la rampa no pase de lo que le queda al tema que sale
            try:
                resta = (len(sale_d.audio) - sale_d.cursor) / (sale_d.sr * max(1e-6, sale_d.rate_eff))
                duration_s = min(duration_s, max(2.0, resta - 0.3))
            except Exception:
                pass
            log("cruce incompatible", f"BPM {self.deck_a.original_bpm:.0f} / {self.deck_b.original_bpm:.0f}: el Deck {sale_d.name} baja en {duration_s:.0f} s y el Deck {entra.name} entra "
                                      f"cuando le queda {cruce_auto.INC_ENTRA:.0%} (a los {duration_s * (1 - cruce_auto.INC_ENTRA):.1f} s)")
        if not self._plan and not simple:
            try:
                self._pc_mix = self._punto_cruce_manual()          # modo Manual: la misma lógica de frenado que el Auto, con tus deslizadores
            except Exception:
                import traceback; traceback.print_exc()
                self._pc_mix = None
        self._eco_decidir(sale_d, simple)
        interval_ms = 50
        self._mix_dur = max(0.5, float(duration_s))      # la mezcla se mide con el RELOJ REAL (dura lo que marca el gráfico de ⚙, aunque el temporizador se atrase)
        self._mix_acum = 0.0
        self._mix_tref = time.perf_counter()
        self.mix_steps_total = 1000                      # (solo para mostrar el avance en %)
        self.mix_steps_done = 0
        self._mix_pausa_hecha = bool(simple) or (bool(self._plan) and not self._plan.get("pausa", True)) or not cruce_auto.hay_pausa(self._es_auto2())     # cruce simple: sin pausa · Auto y Manual: con la pausa del 50 % de ⚙ Ajustes (3 s por defecto; Auto la omite si no queda tiempo)
        self.mix_pausa_timer.stop()
        self.mix_timer.start(interval_ms)
        self._set_status(f"🎬 Mezclando {direction} en {int(duration_s)} s..." + (f"  🤖 {self._plan['nombre']}" if self._plan else ""))

    def _eco_decidir(self, sale_d, simple):
        """Cruce de temas que no combinan (BPM muy distintos o tonalidades que chocan): arma el filtro + eco al compás en el que sale."""
        try:
            self.mixer.eco.soltar()
            if cruce_auto.AUTO_ECO < 0.5:
                return
            choca = bool(getattr(self, "_inc_mix", False)) or bool(self._plan and self._plan.get("compat") == 0)
            if not choca:
                return
            bpm = float(sale_d.original_bpm or 0.0) * max(1e-6, float(sale_d.rate_eff))
            retardo = 0.75 * 60.0 / bpm if bpm > 30.0 else 0.4          # corchea con puntillo: cae "entre" los golpes y no los pisa
            while retardo > 0.9:
                retardo /= 2.0
            while retardo < 0.2:
                retardo *= 2.0
            self.mixer.eco.armar("a" if sale_d is self.deck_a else "b", retardo)
            log("eco", f"el Deck {sale_d.name} se va con filtro y eco ({retardo * 1000:.0f} ms, al compás) porque los dos temas no combinan")
        except Exception:
            traceback.print_exc()

    def _tono_decidir(self, sale_d, entra):
        """Si las tonalidades chocan y UN semitono arriba o abajo del que entra las vuelve compatibles, el que entra suena así (mismo tempo)."""
        try:
            if getattr(entra, "semitonos", 0):
                return                                            # ya suena movido: no se vuelve a tocar
            if cruce_auto.AUTO_TONO < 0.5 or entra.audio is None:
                return
            def clave_conf(d):
                k = (d.analysis or {}).get("key") or {}
                return k.get("camelot"), k.get("conf")
            cs, fs = clave_conf(sale_d); ce, fe = clave_conf(entra)
            cs = self._clave_de(sale_d); ce = ce or self._clave_de(entra)
            if not cs or not ce:
                return
            for f in (fs, fe):                                    # tonalidad poco clara (los dos mejores candidatos casi empatan): no se arriesga
                if f is not None and float(f) < tono.CONF_MIN:
                    return
            s, comp, nueva = tono.mejor_desplazamiento(cs, ce, 1)
            if s == 0:
                return
            entra.set_semitonos(s)
            log("tono", f"{cs} → {ce} chocan: el Deck {entra.name} entra {s:+d} semitono ({nueva}, {'misma clave' if comp == 2 else 'clave vecina'}) con el mismo tempo; sigue así mientras esté en el deck")
        except Exception:
            traceback.print_exc()

    def _nivel_restaurar(self):
        """Devuelve al tema que entró su ganancia normal (termina la corrección de nivel del cruce)."""
        n = getattr(self, "_nivel", None)
        self._nivel = None
        if n and n["deck"].path == n["path"]:
            n["deck"].auto_gain = n["base"]

    def _nivelar_entrada(self, sale_d, entra, duration_s):
        """Al empezar un cruce del Auto: el que entra arranca al mismo nivel que el que sale en el tramo donde suenan juntos (hasta ±3 dB),
        y esa corrección se va soltando hasta 0 dB al terminar (ver `_nivel_paso`). Se mide con la curva de energía del análisis."""
        self._nivel_restaurar()
        if cruce_auto.AUTO_NIVELA < 0.5 or not self._plan:
            return
        try:
            vent = max(4.0, min(12.0, float(duration_s) / 3.0))
            def local(d):
                an = d.analysis or {}
                wf = an.get("waveform") or []
                if not wf:
                    return None
                dt = float(an.get("duration", 0.0)) / len(wf)
                return nivel.nivel_local(wf, dt, d.position_virtual_seconds(), max(1e-6, d.rate_eff), float(d.auto_gain), vent)
            db = nivel.trim_entrada_db(local(sale_d), local(entra))
            if abs(db) < 0.3:
                return
            self._nivel = {"deck": entra, "path": entra.path, "base": float(entra.auto_gain), "db": db}
            entra.auto_gain = self._nivel["base"] * 10.0 ** (db / 20.0)
            log("nivel", f"Deck {entra.name} entra con {db:+.1f} dB para igualar el nivel del que sale; vuelve a 0 dB al terminar el cruce")
        except Exception:
            traceback.print_exc()
            self._nivel = None

    def _nivel_paso(self, frac):
        """Suelta de a poco la corrección de nivel del que entró (frac = avance del cruce, 0..1)."""
        n = getattr(self, "_nivel", None)
        if not n:
            return
        d = n["deck"]
        if d.path != n["path"]:                      # se cargó otro tema en ese deck: no se toca nada
            self._nivel = None
            return
        d.auto_gain = n["base"] * 10.0 ** (n["db"] * (1.0 - min(1.0, max(0.0, frac))) / 20.0)

    def _es_auto2(self):
        """¿La mezcla en curso es del Auto «como mi manual»? (usa su propia pausa y su propio ritmo, separados del manual)"""
        return bool(self._plan) and self._plan.get("estrategia") == "manual"

    def _mix_step(self):
        with cruce_auto.contexto(self._es_auto2()):
            self._mix_step_interno()

    def _mix_step_interno(self):
        ahora = time.perf_counter()
        self._mix_acum += ahora - self._mix_tref         # tiempo real transcurrido de mezcla (sin contar la pausa del 50 %)
        self._mix_tref = ahora
        if self._mix_acum >= self._mix_dur:
            self.mix_steps_done = self.mix_steps_total
            self.mix_timer.stop()
            self._nivel_restaurar()
            self.mixer.eco.soltar()                         # el eco ya no recibe más, pero su cola termina de sonar
            self.crossfader.setValue(self.mix_to)
            self._plan = None
            self._inc_mix = False
            log("mezcla", f"completada · A {self.deck_a.position_seconds():.1f} s / B {self.deck_b.position_seconds():.1f} s")
            self._set_status("🎬 Mezcla completada")
            return

        frac = min(1.0, self._mix_acum / self._mix_dur)
        self._nivel_paso(frac)
        self.mix_steps_done = int(frac * self.mix_steps_total)
        if getattr(self, "_inc_mix", False):               # temas incompatibles: el nuevo arranca (a su tempo natural) cuando al que sale le queda INC_ENTRA
            en = getattr(self, "_inc_entra", None)
            if en is not None and not en.playing and frac >= 1.0 - float(cruce_auto.INC_ENTRA) - 1e-6 and en.audio is not None:
                en.play()
                log("cruce incompatible", f"entra el Deck {en.name}")
        pc, zpb = (self._plan.get("pc"), self._plan.get("zpb")) if self._plan else (getattr(self, "_pc_mix", None) or (None, None))
        if pc is not None:                               # frena al acercarse al cruce de las dos líneas, sale lento y acelera hasta el 50 % (Auto y Manual)
            frac = cruce_auto.pos_cruce(frac, pc, zpb)
        value = int(round(self.mix_from + (self.mix_to - self.mix_from) * frac))

        if not self._mix_pausa_hecha:
            prev = self.crossfader.value()
            q = cruce_auto.pausa_pos()                       # dónde se queda la pausa (0.5 = en el 50 %; se mueve en ⚙ Ajustes)
            vp = 100.0 * q if self.mix_to > self.mix_from else 100.0 * (1.0 - q)       # (0.5 → 50 en los dos sentidos, como siempre)
            cruzando = (prev < vp <= value) or (prev > vp >= value)
            if cruzando:
                self.crossfader.setValue(int(round(vp)))
                self._mix_pausa_hecha = True
                self.mix_timer.stop()
                self._set_status(f"⏸ Mezcla pausada {cruce_auto.pausa_s():g} s en el {int(round(q * 100))}%…")
                self.mix_pausa_timer.start(max(50, int(self._pausa_s() * 1000)))
                return

        self.crossfader.setValue(value)

    def _pausa_s(self):
        with cruce_auto.contexto(self._es_auto2()):
            return self._pausa_s_interno()

    def _pausa_s_interno(self):
        """Duración de la pausa del 50 %. Con ⚙ «Pausa hasta línea de compás»: termina justo en una línea de compás del tema que sale
        (la 1.ª línea es donde el mezclador pasa el bajo; la pausa termina en esa línea o en una posterior, la más cercana a lo configurado), así
        el resto del fundido sigue en el compás y no a media frase."""
        base = float(cruce_auto.pausa_s())
        if cruce_auto.PAUSA_EN_LINEA < 0.5 or base < 0.5:
            return base
        try:
            sale = self.deck_a if getattr(self, "_cf_dir", "AB") == "AB" else self.deck_b
            db = self._db_de(sale)
            if len(db) < 4 or not sale.playing:
                return base
            pos = sale.position_virtual_seconds(); rate = max(1e-6, sale.rate_eff)
            T = (db[db > pos + 0.05] - pos) / rate
            if len(T) < 2:
                return base
            compas = float(np.median(np.diff(db[:64]))) / rate if len(db) > 2 else 2.0
            t1 = float(T[0])                                        # línea donde se pasa el bajo
            cand = [float(t) for t in T if t >= max(1.5, t1) and t <= base + 1.5 * compas]      # desde la línea del cambio de bajo en adelante
            if not cand:
                return base
            return max(0.2, min(cand, key=lambda t: abs(t - base)))
        except Exception:
            return base

    def _punto_cruce_manual(self):
        """Modo Manual: (cruce, inicio de la rampa de B) en posición del crossfader (0..1) con los deslizadores actuales;
        None si el cruce cae pasado el 50 % (ahí no se frena: la segunda mitad va pareja)."""
        if not self.cruce_ab:
            return None
        if self.cruce_bandas:
            rb = max(0.02, min(self.rampa_b, 1.0 - self.punto_b))
            pc = cruce_auto.punto_cruce(self.punto_a, (None if self.fin_a >= 0.995 else self.fin_a), self.punto_b, rb, self.gamma_a)
        else:
            pc = cruce_auto.punto_cruce_simple(self.punto_a, self.punto_b)
        return (pc, self.punto_b) if (pc is not None and 0.0 < pc <= 0.5) else None

    def _abrir_ajustes_cruce(self):
        """Botón ⚙: ventana de ajustes generales con todos los tiempos del cruce."""
        from setup.ajustes_cruce import AjustesCruce
        d = getattr(self, "_dlg_ajc", None)
        if d is None:
            d = self._dlg_ajc = AjustesCruce(self)
        d.vista.update()
        d.show(); d.raise_(); d.activateWindow()

    def _reanudar_mix(self):
        if self._mix_acum < self._mix_dur:
            self._set_status("🎬 Mezcla reanudada")
            self._mix_tref = time.perf_counter()
            self.mix_timer.start(50)

    # ================= PAUSA/PLAY CON ESPACIO =================
    def _toggle_play_pausa(self):
        fw = QApplication.focusWidget()
        if isinstance(fw, (QLineEdit, QSpinBox)):
            return
        prim = self._deck_primario()
        if prim is None or prim.audio is None:
            self._set_status("▶ No hay deck cargado para pausar/reanudar")
            return
        if prim.playing:
            prim.pause()
            self._set_status(f"⏸ Deck {prim.name} pausado (Espacio)")
        else:
            prim.play()
            self._set_status(f"▶ Deck {prim.name} reanudado (Espacio)")

    # ================= AUTO-ENGANCHE =================
    def _deck_primario(self):
        a, b = self.deck_a, self.deck_b
        a_ok = a.playing and a.audio is not None
        b_ok = b.playing and b.audio is not None
        if a_ok and b_ok:
            return a if self.crossfader.value() < 50 else b
        if a_ok: return a
        if b_ok: return b
        f = self.crossfader.value()
        if f < 50 and a.audio is not None:
            return a
        if f >= 50 and b.audio is not None:
            return b
        if a.audio is not None: return a
        if b.audio is not None: return b
        return None

    def _marca_cambiada(self, f):
        self._marca_frac = float(f)
        self._marca_pendiente = False
        _log_diferido("marca", "auto-enganche", f"marca en {self._marca_frac * 100:.1f} %")
        self._marca_disparada = False
        prim = self._deck_primario()
        if prim is not None and prim.analysis and prim.analysis.get("duration", 0) > 0:
            d = float(prim.analysis["duration"]); fin = self._fin_audible(prim)
            d = min(d, fin) if fin > 1.0 else d
            self._ultimo_prog_primario = min(1.0, prim.position_seconds() / d)
        else:
            self._ultimo_prog_primario = 0.0
        guardar_config(marca_frac=self._marca_frac)
        self._actualizar_lbl_marca()

    def _marca_cruzada(self, f):
        pass

    def _break_tilde(self, on):
        """Tilde del frente «Mezclar en break»: enciende/apaga BREAK_ACTIVO, lo guarda y refresca la barra y la línea de tiempo."""
        from setup import ajustes_cruce
        cruce_auto.aplicar({"BREAK_ACTIVO": 1.0 if on else 0.0})
        ajustes_cruce.guardar()
        d = getattr(self, "_dlg_ajc", None)
        if d is not None and hasattr(d, "refrescar"):
            d.refrescar()
        self.barra_prog.update(); self.timeline.redraw()

    def _actualizar_lbl_marca(self):
        if not hasattr(self, "lbl_marca"):
            return
        self.lbl_marca.setText(f"⚓ Marca: {self._marca_frac * 100:.1f}%\nDoble clic para restablecer")

    UMBRAL_SILENCIO = 0.004        # ≈ -48 dBFS: por debajo de esto se considera silencio
    SILENCIO_MIN = 3.0             # el silencio del final tiene que durar al menos esto (s) para tenerlo en cuenta

    def _fin_audible(self, deck):
        """Segundo en que termina la música del tema (sin el silencio del final). Si no hay silencio final largo,
        devuelve la duración completa. Se calcula una vez por tema cargado, en un hilo aparte (recorrer todo el audio en el hilo
        de la interfaz congelaba el timeline casi 2 s); mientras tanto devuelve la duración completa."""
        a = deck.audio
        if a is None:
            return 0.0
        c = getattr(deck, "_fin_cache", None)
        if c is not None and c[0] is a:
            return c[1]
        sr = max(1, int(deck.sr))
        total = len(a) / sr
        if getattr(deck, "_fin_calc", None) is a:
            return total                                  # ya se está calculando
        deck._fin_calc = a
        nombre = deck.name

        def _calcular():
            fin = total
            try:
                bloque = max(1, sr // 10)                 # bloques de 0,1 s
                n = len(a) // bloque
                if n > 0:
                    v = a[: n * bloque]
                    v = v.reshape(n, bloque, -1) if v.ndim > 1 else v.reshape(n, bloque, 1)
                    pic = np.maximum(v.max(axis=(1, 2)), -v.min(axis=(1, 2)))      # pico por bloque, sin copiar todo el audio
                    con = np.nonzero(pic > self.UMBRAL_SILENCIO)[0]
                    ultimo = (int(con[-1]) + 1) * bloque / sr if len(con) else 0.0
                    if total - ultimo >= self.SILENCIO_MIN and ultimo > 5.0:
                        fin = ultimo + 0.5                # un resto de cola
                        log("silencio", f"deck {nombre}: la música termina en {fmt_time(fin)}; "
                                        f"los últimos {fmt_time(total - fin)} son silencio")
            except Exception:
                fin = total
            deck._fin_cache = (a, fin)

        threading.Thread(target=_calcular, daemon=True, name="fin-audible").start()
        return total

    def _break_vigilar(self, prim, prog):
        """Si el tema que suena está dentro de un break (energía baja, varios compases) y estamos en el tramo previo a la marca
        (BREAK_VENTANA antes de ella), devuelve el segundo en que empezó ese break; si no, None. Solo si el otro deck está listo."""
        try:
            marca = float(self._marca_frac)
            if not (marca - cruce_auto.BREAK_VENTANA <= prog < marca):
                return None
            entra = self.deck_b if prim is self.deck_a else self.deck_a
            if entra.audio is None or not entra.analysis:
                return None
            an = prim.analysis
            db = self._db_de(prim)
            compas = float(np.median(np.diff(db))) if len(db) > 2 else 2.0
            pos = prim.position_virtual_seconds()
            if cruce_auto.break_adelante(an, pos, compas):      # desde la línea blanca hasta la amarilla, bajo las líneas rojas
                return pos
        except Exception:
            import traceback; traceback.print_exc()
        return None

    def _tick_auto_enganche(self):
        try:
            from setup import hilos_analisis as _ha
            _ha._SONANDO = bool(self.deck_a.playing or self.deck_b.playing)
        except Exception:
            pass
        prim = self._deck_primario()

        if prim is not self._ultimo_deck_primario:
            self._ultimo_deck_primario = prim
            self._marca_pendiente = False
            self._marca_disparada = False
            self._break_disparo = False
            self._ultimo_prog_primario = 0.0

        if prim is None or not prim.analysis or prim.analysis.get("duration", 0) <= 0:
            self.barra_prog.set_progreso(0.0, 0.0, 0.0)
            return

        dur = float(prim.analysis["duration"])
        seg = float(prim.position_seconds())
        prog_barra = max(0.0, min(1.0, seg / dur if dur > 0 else 0.0))
        self.barra_prog.set_progreso(prog_barra, seg, dur)
        # La marca se mide sobre la parte CON música: si el tema trae silencio al final, no se espera a que pase.
        fin = self._fin_audible(prim)
        dur_ef = min(dur, fin) if fin > 1.0 else dur
        prog = max(0.0, min(1.0, seg / dur_ef if dur_ef > 0 else 0.0))

        if self._marca_frac >= 0 and not self._marca_disparada:
            if self._ultimo_prog_primario < self._marca_frac <= prog:
                self._marca_pendiente = True; self._marca_t_reintento = 0.0
                log("auto-enganche", f"marca {self._marca_frac * 100:.1f} % cruzada en {fmt_time(seg)} de {fmt_time(dur)}")
                self._set_status(
                    f"⚓ Auto-enganche disparado (marca {self._marca_frac * 100:.1f}%) → mezcla"
                )
            elif (not getattr(self, "_marca_pendiente", False) and dur_ef < dur - 0.5 and seg >= dur_ef
                  and prim.playing and not (self.mix_timer.isActive() or self.mix_pausa_timer.isActive())):
                # entró (o saltó) directo al silencio del final sin cruzar la marca: se mezcla igual
                self._marca_pendiente = True; self._marca_t_reintento = 0.0
                log("auto-enganche", "silencio al final del tema → mezcla")
                self._set_status("🔇 Silencio al final del tema → mezcla")
            elif (not getattr(self, "_marca_pendiente", False) and cruce_auto.BREAK_ACTIVO >= 0.5 and prim.playing
                  and not (self.mix_timer.isActive() or self.mix_pausa_timer.isActive())
                  and self._break_vigilar(prim, prog) is not None):
                # entró un break (la energía del tema que suena cae) en el tramo previo a la marca: se mezcla ahí, sin esperar a la marca
                t_ini = self._break_vigilar(prim, prog)
                self._marca_pendiente = True; self._marca_t_reintento = 0.0; self._break_disparo = True
                log("auto-enganche", f"break del tema que suena (desde {fmt_time(t_ini)}) antes de la marca → mezcla")
                self._set_status("🌫 Break detectado → mezcla (antes de la marca)")
            if getattr(self, "_marca_pendiente", False):
                # Si al cruzar la marca no se pudo arrancar (el otro deck aún sin análisis/tonalidad, sin tema cargado…),
                # se reintenta cada segundo hasta que la mezcla arranque (antes se perdía y el tema se pasaba de largo).
                ahora = time.monotonic()
                if ahora >= getattr(self, "_marca_t_reintento", 0.0):
                    self._marca_t_reintento = ahora + 1.0
                    try:
                        self._disparar_mezcla_auto(exacto=True, sin_espera=bool(getattr(self, "_break_disparo", False)))      # la marca roja manda: se engancha JUSTO ahí (si fue por un break, también sin esperar frase)
                    except Exception:
                        import traceback; traceback.print_exc()
                    if (self.mix_timer.isActive() or self.mix_pausa_timer.isActive()
                            or getattr(self, "_mix_esperando", False) or getattr(self, "_frase_armada", False)):
                        self._marca_pendiente = False; self._marca_disparada = True; self._break_disparo = False
                        log("auto-enganche", "mezcla arrancada")

        self._ultimo_prog_primario = prog

    def _vigilar_salida(self):
        """Si se desenchufó la placa/DAC USB, la salida pasa sola a la predeterminada de Windows."""
        m = self.mixer
        ahora = time.monotonic()
        if ahora - getattr(self, "_t_vig_sal", 0) >= 0.5:
            self._t_vig_sal = ahora
            m.vigilar_salida()
        try:
            self._aur_auto_dispositivos()
        except Exception:
            import traceback; traceback.print_exc()
        msg, m._aviso_salida = m._aviso_salida, None
        if msg:
            log("audio", msg)
            self._set_status(msg)
        if getattr(m, "aur_perdida", False):
            m.aur_perdida = False
            try:
                for b in self.btn_cue.values():
                    b.setChecked(False)
                for nom, b in getattr(self, "btn_prev", {}).items():
                    b.blockSignals(True); b.setChecked(False); b.blockSignals(False)
                self._aur_refrescar()
            except Exception:
                pass

    def _vigilar_cortes_audio(self):
        """Avisa en la consola cuando la salida principal se queda sin audio (trancada) o un bloque tarda demasiado.
        Además consume la bandera de error del callback (que NUNCA debe imprimir por su cuenta)."""
        m = self.mixer
        # errores del callback: el callback solo marca, la UI imprime
        e = m._err_flag
        if e:
            m._err_flag = 0
            log("audio", f"⚠ error en el callback de audio ({m.ERR.get(e, e)}): esa parte se desactivó para no cortar el sonido")
        n = m.cortes_audio
        if n != getattr(self, "_cortes_vistos", 0):
            log("audio", f"⚠ corte de audio en la salida principal (van {n}) · bloque más lento: {m.cb_max_ms:.0f} ms"
                         f" (el límite es {m.blocksize / m.sr * 1000:.0f} ms)")
            self._cortes_vistos = n
            m.cb_max_ms = 0.0
        elif m.cb_max_ms > 0.8 * m.blocksize / m.sr * 1000 and time.monotonic() - getattr(self, "_t_lento", 0) > 5:
            log("audio", f"un bloque de audio tardó {m.cb_max_ms:.0f} ms (el límite es {m.blocksize / m.sr * 1000:.0f} ms): casi se corta")
            self._t_lento = time.monotonic()
            m.cb_max_ms = 0.0

    def _vigia_ui(self):
        """Vigía de congelamientos: si la interfaz no responde por más de 150 ms, deja en el registro (consola) DÓNDE estaba trabado
        el programa ([congelado] …). Sirve para encontrar qué causa un tirón del timeline."""
        if getattr(self, "_vigia_on", False):
            return
        self._vigia_on = True
        self._latido = time.perf_counter()
        main_id = threading.main_thread().ident

        def _run():
            ult = 0.0
            while True:
                time.sleep(0.03)
                try:
                    ahora = time.perf_counter()
                    dt = ahora - self._latido
                    if dt > 0.15 and ahora - ult > 0.14:
                        ult = ahora
                        fr = sys._current_frames().get(main_id)
                        pila = traceback.extract_stack(fr)[-7:] if fr is not None else []
                        txt = " > ".join(f"{os.path.basename(f.filename)}:{f.lineno} {f.name}" for f in pila)
                        mez = "mezclando" if (self.mix_timer.isActive() or self.mix_pausa_timer.isActive()) else "libre"
                        print(f"[congelado] interfaz sin responder {dt * 1000:.0f} ms ({mez}) · {txt}")
                except Exception:
                    pass
        threading.Thread(target=_run, daemon=True, name="vigia-ui").start()

    def _tick(self):
        self._latido = time.perf_counter()
        if not getattr(self, "_vigia_on", False):
            self._vigia_ui()
        self.deck_a.tick()
        self.deck_b.tick()
        self._vigilar_cortes_audio()
        self._vigilar_salida()
        self._mb_actualizar_barras()
        try:
            self._animar_cruce()
        except Exception:
            import traceback; traceback.print_exc()
        prim = self._deck_primario()
        rutas = (self.deck_a.path, self.deck_b.path, self.biblioteca.count(), prim.path if prim is not None else None,
                 self._clave_de(prim))
        if rutas != getattr(self, "_rutas_pintadas", None):
            self._rutas_pintadas = rutas
            self.biblioteca.set_referencia(rutas[4])
            self.biblioteca.pintar(self.deck_a.path, self.deck_b.path)
            if self.chk_armonico.isChecked() or self.chk_frases.isChecked():
                self._reordenar_pronto(400)               # la cadena sigue al tema que suena
        try:
            self._auto_vigilar()
        except Exception:
            import traceback; traceback.print_exc()
        try:
            self._vigilar_sync()
        except Exception:
            import traceback; traceback.print_exc()
        try:
            self._tick_auto_enganche()
        except Exception:
            import traceback; traceback.print_exc()
        self.timeline.redraw()

    _QSS_MIX_BASE = (
        "QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffd84a, stop:1 #ff9a00); color:#2a1700; font-weight:bold;"
        " border:1px solid #ffe08a; border-radius:11px; }"
        "QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffe473, stop:1 #ffae2e); }"
        "QPushButton:pressed { background:#d98400; padding-top:2px; }"
        "QPushButton:disabled { background:#3a3322; color:#7a7155; border-color:#4a422c; }")

    def _animar_cruce(self):
        """Los decks brillan según cuánto suenan y el botón Mezclar muestra el avance de la mezcla."""
        try:
            self._loop_actualizar_ui()
        except Exception:
            pass
        for d in (self.deck_a, self.deck_b):
            peso = max(d.vol_hi, d.vol_lo) if d.playing else 0.0
            paso = int(round(peso * 10))
            if paso != d._glow_paso:
                d._glow_paso = paso
                d.set_brillo(paso / 10.0)
        mezclando = self.mix_timer.isActive() or self.mix_pausa_timer.isActive()
        frase = bool(getattr(self, "_frase_armada", False))
        if not mezclando and (frase or getattr(self, "_mix_esperando", False)):
            # esperando el enganche (inicio de frase o análisis): el botón late entre ámbar y celeste y cuenta los segundos
            t = time.monotonic()
            if frase:
                texto = f"🥁 Esperando la frase…  {max(0.0, getattr(self, '_frase_t_fin', t) - t):.1f} s"
            else:
                texto = "⏳ Esperando el análisis…"
            if texto != getattr(self, "_mix_pulso_texto", None):
                self._mix_pulso_texto = texto
                self.btn_mix.setText(texto)
            fase = int(round((0.5 + 0.5 * math.sin(t * 2 * math.pi / 0.8)) * 8))
            if fase != getattr(self, "_mix_pulso_fase", None):
                self._mix_pulso_fase = fase
                k = fase / 8.0
                def _mezcla(a, b):
                    return "#%02x%02x%02x" % tuple(int(round(x + (y - x) * k)) for x, y in zip(a, b))
                c1 = _mezcla((255, 216, 74), (92, 240, 255))      # ámbar → celeste (arriba)
                c2 = _mezcla((255, 154, 0), (0, 168, 216))        # (abajo)
                self.btn_mix.setStyleSheet(
                    "QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 %s, stop:1 %s); color:#10161a; font-weight:bold;"
                    " border:1px solid #ffffff; border-radius:11px; }" % (c1, c2))
            self._mix_prog_clave = -1
        elif mezclando and self.mix_steps_total > 0:
            pct = max(0, min(100, int(round(100.0 * self.mix_steps_done / self.mix_steps_total))))
            clave = pct // 2
            if clave != getattr(self, "_mix_prog_clave", None):
                self._mix_prog_clave = clave
                p = clave * 0.02
                self.btn_mix.setStyleSheet(
                    "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #ffd84a, stop:%.3f #ff9a00, stop:%.3f #2b2112, stop:1 #1c160b);"
                    " color:#ffffff; font-weight:bold; border:1px solid #ffe08a; border-radius:11px; }" % (p, min(1.0, p + 0.002)))
                self.btn_mix.setText(f"⏳ Mezclando…  {pct} %")
        elif getattr(self, "_mix_prog_clave", None) is not None:
            self._mix_prog_clave = None
            self._mix_pulso_texto = self._mix_pulso_fase = None
            self.btn_mix.setStyleSheet(self._QSS_MIX_BASE)
            self.btn_mix.setText(self._texto_btn_mix())
