"""AutoMix — mezcla automática: plan, siguiente tema, duración y disparo."""
import math
import os
import time
import numpy as np
from PySide6.QtCore import QTimer
from setup import cruce_auto
from setup.analisis import compat_armonica
from setup.base import _log_diferido, log
from setup.config import guardar_config, leer_config


class AutomaticoMixin:
    """Mezcla automática: plan, siguiente tema, duración y disparo (parte de la ventana principal)."""


    def _cargar_duracion_mezcla(self):
        try:
            return max(1, min(120, int(leer_config().get("mezcla_s", 10))))
        except Exception:
            return 10

    def _duracion_mezcla_cambio(self, v):
        log("config", f"duración de la mezcla: {v} s")
        self.btn_mix.setText(self._texto_btn_mix())
        guardar_config(mezcla_s=int(v))

    # ================= CRUCE AUTO (lo diseña el programa para cada par de temas) =================
    def _spin_mix_activo(self):
        """La duración se edita en Manual y también en el Auto 'como el manual' (estrategia 2), que usa esa misma duración."""
        return (not self.cruce_auto) or (cruce_auto.ESTRATEGIA >= 1.5 and cruce_auto.MAN_COMPASES < 1)

    def _texto_btn_mix(self):
        if self.cruce_auto and cruce_auto.ESTRATEGIA >= 1.5 and cruce_auto.MAN_COMPASES >= 1:
            return f"🎬 Mezclar (auto · {cruce_auto.MAN_COMPASES:.0f} comp) [F2]"
        return "🎬 Mezclar (auto) [F2]" if not self._spin_mix_activo() else f"🎬 Mezclar ({self.spin_mix.value()}s) [F2]"

    def _plan_activo(self):
        pl = getattr(self, "_plan", None)
        if pl and (self.mix_timer.isActive() or self.mix_pausa_timer.isActive()):
            return pl
        return None

    def set_modo_auto(self, v):
        log("config", f"cruce: {'AUTO (lo diseña el programa)' if v else 'MANUAL (los deslizadores)'}")
        self.cruce_auto = bool(v)
        guardar_config(cruce_auto=self.cruce_auto)
        if hasattr(self, "spin_mix"):
            self.spin_mix.setEnabled(self._spin_mix_activo())
        if hasattr(self, "btn_mix") and not (self.mix_timer.isActive() or self.mix_pausa_timer.isActive()):
            self.btn_mix.setText(self._texto_btn_mix())

    def _datos_cruce(self, d, es_sale):
        """Lo que el diseñador del cruce necesita de un deck: curvas de voz y bajo, compases, velocidad y cuánto le queda."""
        an = d.analysis or {}
        pos = d.position_virtual_seconds(); rate = max(1e-6, d.rate_eff)
        dd = {"voz": an.get("voz") or [], "bajo": an.get("bajo") or [], "dt": float(an.get("voz_dt", 0.5) or 0.5),
              "pos": pos, "rate": rate, "bpm": float(an.get("bpm", 0) or 0), "db": self._db_de(d)}
        if d.audio is not None:
            fin = self._fin_audible(d) if es_sale else len(d.audio) / max(1, d.sr)
            dd["resta"] = max(0.0, (fin - pos) / rate)
        return dd

    def _disenar_cruce_auto(self, sale, entra):
        """Diseña el cruce de esta mezcla mirando los dos temas (ver setup/cruce_auto.py). Devuelve el dict del plan."""
        S, E = self._datos_cruce(sale, True), self._datos_cruce(entra, False)
        compat = compat_armonica(self._clave_de(sale), self._clave_de(entra))
        try:
            bs, be = S["bpm"] * S["rate"], E["bpm"] * E["rate"]
            dif = abs(be / bs - 1.0) if bs > 0 and be > 0 else 0.0
        except Exception:
            dif = 0.0
        forma = None
        try:                                              # la forma de los deslizadores "Forma de cruce A/B" (lo que se afina a mano) también vale en el Auto Pro
            forma = {"pa": self.punto_a, "pb": self.punto_b, "rb": self.rampa_b, "ps": self.punto_s, "gamma": self.gamma_a,
                     "fa": (None if self.fin_a >= 0.995 else self.fin_a), "dur": float(self.spin_mix.value())}
            zona = self._punto_cruce_manual()             # dónde se cruzan las dos líneas (para frenar ahí), igual que el manual
            if zona:
                forma["pc"], forma["zpb"] = zona
        except Exception:
            forma = None
        return cruce_auto.disenar(S, E, compat=compat, dif_tempo=dif, forma=forma)

    def _dur_auto_estimada(self, sale, entra):
        """Tiempo total que tendría ahora la mezcla Auto, con la pausa del medio (sirve para saber con cuánta anticipación
        arrancarla). Se recalcula como mucho una vez por segundo."""
        ahora = time.monotonic()
        c = getattr(self, "_dur_auto_cache", None)
        if c is not None and c[0] == (sale.path, entra.path) and ahora - c[1] < 1.0:
            return c[2]
        try:
            pl = self._disenar_cruce_auto(sale, entra)
            dur = float(pl["dur"]) + (cruce_auto.PAUSA if pl.get("pausa", True) else 0.0)
        except Exception:
            dur = 16.0
        self._dur_auto_cache = ((sale.path, entra.path), ahora, dur)
        return dur

    def set_comp(self, v):
        log("config", f"compensar nivel: {'sí' if v else 'no'}")
        self.comp_nivel = bool(v)
        guardar_config(comp_nivel=self.comp_nivel)
        if hasattr(self, "mixer"):
            self.mixer.comp_activo = self.comp_nivel

    def set_forma_cruce(self, pa, pb, activo, ps=None, bandas=None, rb=None, fa=None, gamma=None):
        _log_diferido("forma", "config", f"forma de cruce: A {pa:.0%} · B {pb:.0%} · activa {'sí' if activo else 'no'}"
                      f"{'' if ps is None else f' · bajo {ps:.0%}'}{'' if bandas is None else f' · por bandas {chr(115)+chr(237) if bandas else chr(110)+chr(111)}'}"
                      f"{'' if rb is None else f' · B sube en {rb:.0%}'}{'' if fa is None else f' · A termina {fa:.0%}'}"
                      f"{'' if gamma is None else f' · forma A {gamma:.1f}'}")
        self.punto_a, self.punto_b, self.cruce_ab = float(pa), float(pb), bool(activo)
        if ps is not None:
            self.punto_s = float(ps)
        if bandas is not None:
            self.cruce_bandas = bool(bandas)
        if rb is not None:
            self.rampa_b = float(rb)
        if fa is not None:
            self.fin_a = float(fa)
        if gamma is not None:
            self.gamma_a = float(gamma)
        guardar_config(punto_a=self.punto_a, punto_b=self.punto_b, cruce_ab=self.cruce_ab,
                       punto_s=self.punto_s, cruce_bandas=self.cruce_bandas,
                       rampa_b=self.rampa_b, fin_a=self.fin_a, gamma_a=self.gamma_a)
        self._update_cf()

    def _auto_s_cambio(self, v):
        self.auto_s = int(v)
        guardar_config(auto_s=self.auto_s)

    def _programar_carga(self, detenido):
        if not self.carga_auto:
            return
        if self._carga_pendiente:
            return
        self._carga_pendiente = True
        def _run():
            self._carga_pendiente = False
            self._cargar_siguiente(detenido)
        QTimer.singleShot(400, _run)

    def _clave_de(self, deck):
        """Clave Camelot del tema cargado en un deck (de su análisis o del caché de la biblioteca)."""
        try:
            if deck is None or not deck.path:
                return None
            k = ((deck.analysis or {}).get("key") or {}).get("camelot")
            return k or self.biblioteca.info(deck.path)[1]
        except Exception:
            return None

    def _hay_filtro_busqueda(self):
        """True si el usuario tiene algo escrito en el buscador de la lista: la 'cola' pasa a ser
        solamente lo que se ve en pantalla (temas que coinciden con la búsqueda)."""
        try:
            return bool(self.ed_filtro.text().strip())
        except Exception:
            return False

    def _siguiente_armonico(self, path_actual):
        """Modo estricto: SOLO temas de clave compatible (misma, relativa o vecina) y BPM a ±8 %; el mejor primero,
        sin repetir los ya tocados y SALTEANDO los tildados como 'saltear'. Si el buscador tiene algo escrito,
        solo se consideran los temas visibles en la lista (respeta el filtro). Devuelve (ruta, None) o (None, motivo)."""
        bib = self.biblioteca
        if not path_actual:
            return None, "no hay tema de referencia"
        if not hasattr(self, "_tocados"):
            self._tocados = set()
        ref = bib._clave(path_actual)
        self._tocados.add(ref)
        for d in (self.deck_a, self.deck_b):
            if d.path:
                self._tocados.add(bib._clave(d.path))
        bpm0, cam0, _, _ = bib.info(path_actual)
        if cam0 is None or not bpm0:
            return None, "el tema que suena no tiene clave analizada todavía"
        # ← el filtro del buscador manda: si hay texto, la lista útil es la que el usuario ve
        candidatas = bib.todas_visibles() if self._hay_filtro_busqueda() else bib.todas()
        def candidatos():
            res = []
            for orden, r in enumerate(candidatas):
                if bib._clave(r) in self._tocados or not os.path.isfile(r):
                    continue
                if bib.esta_salteado(r):         # ← SALTEADO: no se considera
                    continue
                bpm, cam, _, _ = bib.info(r)
                nivel = compat_armonica(cam0, cam)
                if not nivel or not bpm:                  # sin clave o que choca: no se considera
                    continue
                d = abs(bpm / bpm0 - 1.0)
                if d > 0.08:                              # tempo demasiado lejano para enganchar
                    continue
                res.append((nivel * 10.0 - d * 150.0 - orden * 1e-3, d, r))
            return res
        cands = candidatos()
        if not cands:                                  # ya se tocó todo lo compatible: se empieza otra vuelta
            self._tocados = {ref} | {bib._clave(d.path) for d in (self.deck_a, self.deck_b) if d.path}
            cands = candidatos()
        if not cands:
            return None, "ningún tema de la lista es compatible (clave y BPM) con el que suena"
        return max(cands, key=lambda c: c[0])[2], None

    def _siguiente_en_biblioteca(self, path_actual):
        """Elige el siguiente tema a cargar. Respeta el filtro de búsqueda de la lista: si el usuario está buscando
        algo, la 'cola' es lo que ve en pantalla. Los temas tildados con ⏭ (salteados) se ignoran por completo."""
        if getattr(self, "chk_armonico", None) is not None and self.chk_armonico.isChecked():
            try:
                return self._siguiente_armonico(path_actual)      # estricto: si no hay compatible, no se carga ninguno
            except Exception:
                import traceback; traceback.print_exc()
        # ← lista base: si hay filtro, solo lo visible; si no, la lista completa (como antes)
        todas = self.biblioteca.todas_visibles() if self._hay_filtro_busqueda() else self.biblioteca.todas()
        activas = [r for r in todas if not self.biblioteca.esta_salteado(r)]
        if not activas:
            if self.biblioteca.todas():
                return None, "todos los temas están salteados (destildá alguno con ⏭)"
            return None, "biblioteca vacía"
        clave = os.path.normcase(os.path.abspath(path_actual)) if path_actual else None
        for i, r in enumerate(todas):
            if os.path.normcase(os.path.abspath(r)) == clave:
                for j in range(i + 1, len(todas)):
                    rr = todas[j]
                    if os.path.isfile(rr) and not self.biblioteca.esta_salteado(rr):
                        return rr, None
                for rr in activas:
                    if os.path.isfile(rr):
                        return rr, None
                return None, "fin de la lista"
        for rr in activas:
            if os.path.isfile(rr):
                return rr, None
        return None, "biblioteca vacía"

    def _cargar_siguiente(self, destino):
        if not self.carga_auto:
            return
        otro = self.deck_a if destino is self.deck_b else self.deck_b
        if not otro.path:          # el otro deck está vacío (p. ej. al iniciar): no cargar nada solo
            return
        referencia_path = otro.path
        ruta, motivo = self._siguiente_en_biblioteca(referencia_path)
        if ruta is None:
            self._set_status(f"🔁 Carga automática: {motivo}")
            return
        destino.load_track(ruta)
        k_sale, k_entra = self._clave_de(otro), self.biblioteca.info(ruta)[1]
        extra = f"  🎼 {k_sale}→{k_entra}" if (k_sale and k_entra) else ""
        self._set_status(f"🔁 Deck {destino.name} en espera: {os.path.basename(ruta)}{extra}")

    # ================= MEZCLA EN FRASE =================
    FRASE_COMPASES = 8

    def _db_de(self, deck):
        a = deck.analysis or {}
        db = a.get("downbeats_full") or a.get("downbeats") or []
        return np.asarray(db, dtype=np.float64)

    def _hasta_proxima_frase(self, sale):
        """Segundos reales hasta que el tema que suena empiece su próxima frase (cada 8 compases desde su primer
        compás). None si no hay grilla."""
        db = self._db_de(sale)
        if len(db) < self.FRASE_COMPASES + 1 or sale.audio is None:
            return None
        pos = sale.position_virtual_seconds()
        lim = db[::self.FRASE_COMPASES]
        sig = lim[lim > pos + 0.12]
        if not len(sig):
            return None
        return float((sig[0] - pos) / max(1e-6, sale.rate_eff))

    def _disparar_mezcla_auto(self, exacto=False):
        """Punto único de arranque de las mezclas automáticas (auto-enganche y carga automática).
        Con '🥁 En frase' espera al próximo comienzo de frase del tema que suena para arrancar justo ahí."""
        if getattr(self, "_frase_armada", False):
            return
        if self.mix_timer.isActive() or self.mix_pausa_timer.isActive():
            return
        f = self.crossfader.value()
        sale = self.deck_a if f <= 50 else self.deck_b
        entra = self.deck_b if sale is self.deck_a else self.deck_a
        if self.chk_armonico.isChecked():              # estricto: solo se engancha un tema compatible
            ks, ke = self._clave_de(sale), self._clave_de(entra)
            nivel = compat_armonica(ks, ke)
            try:
                bs = float((sale.analysis or {}).get("bpm", 0)) * sale.rate_eff
                be = float((entra.analysis or {}).get("bpm", 0)) * entra.tempo_rate
                lejos = bs > 0 and be > 0 and abs(be / bs - 1.0) > 0.08
            except Exception:
                lejos = False
            if not nivel or lejos:
                msg = (f"🎼 No se mezcla: {ks or '?'} → {ke or '?'} no es compatible" if not nivel
                       else "🎼 No se mezcla: el BPM del tema en espera está demasiado lejos")
                if getattr(self, "_aviso_armonico", None) != msg:
                    self._aviso_armonico = msg
                    print("[mezcla]", msg)
                    self._set_status(msg)
                return
            self._aviso_armonico = None
        espera = None
        if self.chk_frases.isChecked() and not exacto and not self._cruce_simple() and sale.playing and sale.analysis and entra.analysis and entra.audio is not None:
            espera = self._hasta_proxima_frase(sale)
            if espera is not None:
                dur = self._duracion_mezcla_para(sale, entra, True)
                resta = (len(sale.audio) - sale.cursor - sale.loop_desfase) / (sale.sr * max(1e-6, sale.rate_eff))
                if espera + dur + 4.0 > resta:        # esperar a la frase no deja tiempo: se mezcla ya
                    espera = None
        if espera is None or espera < 0.05:
            if not entra.playing and entra.audio is not None and entra.analysis and not entra.pos_manual:
                db_e = self._db_de(entra)
                if len(db_e):
                    entra.set_position_seconds(float(db_e[0]))      # el entrante sale desde su primer compás
            self._mix_auto = True
            self._mix_clicked()
            return
        self._frase_armada = True
        pa, pb = self.deck_a.path, self.deck_b.path
        self._set_status(f"🥁 Mezcla armada: arranca en la próxima frase ({espera:.1f} s)")
        def _go():
            self._frase_armada = False
            if (self.deck_a.path, self.deck_b.path) != (pa, pb) or self.mix_timer.isActive() or self.mix_pausa_timer.isActive():
                return                                  # cambió algo mientras esperaba (mezcla manual, otro tema…)
            if not entra.playing and entra.audio is not None and entra.analysis and not entra.pos_manual:
                db_e = self._db_de(entra)
                if len(db_e):
                    entra.set_position_seconds(float(db_e[0]))      # el entrante sale desde su primer compás
            self._mix_auto = True
            self._mix_clicked()
        QTimer.singleShot(int(max(0.0, espera - 0.02) * 1000), _go)

    def _duracion_mezcla_para(self, sale, entra, auto):
        """Duración de la mezcla: la elegida por el usuario. En las automáticas se ajusta a compases enteros y,
        si las tonalidades chocan o los BPM son muy distintos, se acorta para pasar rápido de un tema al otro."""
        dur = float(self.spin_mix.value())
        if not auto:
            return dur
        try:
            bpm = float((sale.analysis or {}).get("bpm", 0)) * sale.rate_eff
            comp = compat_armonica(self._clave_de(sale), self._clave_de(entra)) if self.chk_armonico.isChecked() else None
            bpm_e = float((entra.analysis or {}).get("bpm", 0)) * entra.tempo_rate
            dif = abs(bpm_e / bpm - 1.0) if bpm > 0 and bpm_e > 0 else 0.0
            if bpm > 0 and self.chk_frases.isChecked():
                compas = 4.0 * 60.0 / bpm
                n = min((2, 4, 8, 16), key=lambda c: abs(math.log2(c) - math.log2(max(0.5, dur / compas))))   # compases de verdad: 2, 4, 8 o 16
                if comp == 0 or dif > 0.08:
                    n = 2                             # choque de tonalidad o de tempo: corte rápido, 2 compases
                dur = n * compas
            elif comp == 0 or dif > 0.08:
                dur = min(dur, 4.0)
        except Exception:
            pass
        return max(1.0, dur)

    def _auto_vigilar(self):
        if not self.carga_auto or self.mix_timer.isActive() or self.mix_pausa_timer.isActive():
            return
        f = self.crossfader.value()
        if f not in (0, 100):
            return
        sonando = self.deck_a if f == 0 else self.deck_b
        espera = self.deck_b if f == 0 else self.deck_a
        if not sonando.playing or sonando.audio is None or espera.playing:
            return
        if espera.audio is None or not espera.analysis:
            return
        resta = (len(sonando.audio) - sonando.cursor - sonando.loop_desfase) / (sonando.sr * max(1e-6, sonando.rate_eff))
        if self.cruce_auto and self.cruce_ab and self.cruce_bandas and not self._cruce_simple():
            necesita = self._dur_auto_estimada(sonando, espera) + 1.0               # fundido + pausa del 50 % + 1 s de margen
        else:
            necesita = self.spin_mix.value() + (cruce_auto.PAUSA if cruce_auto.hay_pausa() else 0.0) + 1.0      # + pausa al 50 % + 1 s de margen
        if resta <= max(float(self.auto_s), necesita):
            self._set_status(f"🔁 Mezcla automática hacia el Deck {espera.name}")
            self._disparar_mezcla_auto()
