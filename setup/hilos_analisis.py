"""AutoMix — hilos (QThread) que analizan los temas sin trabar la interfaz."""
from pathlib import Path
import json
import os
import sys
import time
from collections import deque
from PySide6.QtCore import QThread, Signal
from setup.analisis import BPM_MAX, BPM_MIN, _guardar_cache, _limpiar_grilla_cache, _pista_bpm, analizar_archivo
from setup.base import CACHE_DIR


_PRIORITARIOS = 0              # análisis de un deck esperando: la biblioteca le cede el turno
_SONANDO = False               # algún deck está sonando (lo pone la ventana): el lote baja a UN solo proceso para no cortar el audio




class Analyzer(QThread):
    done = Signal(str, dict)
    uno_listo = Signal(str, object)       # (ruta, {"uno": [fase, confianza], "kicks": [...]}): lo que le faltaba a un análisis viejo

    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        global _PRIORITARIOS
        _PRIORITARIOS += 1
        try:
            self._run()
        finally:
            _PRIORITARIOS = max(0, _PRIORITARIOS - 1)

    def _completar_uno(self, data):
        """El "1" del compás (votación sobre todo el tema) se calcula DESPUÉS de mostrar el tema, en el proceso aparte,
        y llega por la señal `uno_listo`. Así cargar un tema nunca espera por este cálculo."""
        if data.get("uno_auto") or len(data.get("beats_full") or []) < 16:
            return
        try:
            res = analizar_archivo(self.path, solo_uno=list(data["beats_full"]))
            self.uno_listo.emit(self.path, res)
        except Exception:
            import traceback; traceback.print_exc()

    def _run(self):
        try:
            cache_key = CACHE_DIR / (Path(self.path).stem + ".json")
            if cache_key.exists():
                with open(cache_key) as f:
                    data = json.load(f)
                hint = _pista_bpm(self.path)
                dudoso = (data.get("ver", 1) < 3 and hint is not None
                          and abs(float(data.get("bpm", 0)) - hint) / hint > 0.06)
                if dudoso or (data.get("ver", 1) < 2 and not (BPM_MIN <= float(data.get("bpm", 0)) < BPM_MAX)):
                    result = analizar_archivo(self.path)          # BPM de otra octava (ej. 161 en vez de 80): se rehace una vez
                    _guardar_cache(cache_key, result)
                    self.done.emit(self.path, result)
                    self._completar_uno(result)
                    return
                if data.get("grid") is None and data.get("ver", 1) < 4:
                    if _limpiar_grilla_cache(data):
                        data["ver"] = 4
                        _guardar_cache(cache_key, data)           # grilla regular lista: no se vuelve a calcular
                    else:
                        result = analizar_archivo(self.path)      # pulso irregular: se rehace una vez con la grilla del audio
                        _guardar_cache(cache_key, result)
                        self.done.emit(self.path, result)
                        self._completar_uno(result)
                        return
                if "key" not in data or "voz" not in data:       # caché viejo sin tonalidad / voz: se completa una vez
                    try:
                        data.update(analizar_archivo(self.path, solo_clave=True))
                        _guardar_cache(cache_key, data)
                    except Exception:
                        import traceback; traceback.print_exc()
                self.done.emit(self.path, data)     # caché viejo sin auto_gain: lo calcula el deck del audio ya cargado
                self._completar_uno(data)
                return

            result = analizar_archivo(self.path)
            _guardar_cache(cache_key, result)
            self.done.emit(self.path, result)
            self._completar_uno(result)
        except Exception as e:
            import traceback; traceback.print_exc()
            self.done.emit(self.path, {"error": str(e)})




class AnalizadorBiblioteca(QThread):
    progreso = Signal(int, int)
    tema_listo = Signal(str)
    terminado = Signal()

    def __init__(self, rutas, forzar=False, modo_max=False):
        super().__init__()
        self.rutas = list(rutas)
        self.forzar = forzar
        self.modo_max = modo_max           # análisis masivo con la ventana de progreso: todos los núcleos, prioridad normal
        self.cancelar = False

    def run(self):
        try:
            self._analizar_todo()
        except Exception:
            import traceback; traceback.print_exc()
        finally:
            self.terminado.emit()          # pase lo que pase, la lista se ordena con lo que haya

    @staticmethod
    def _num_trabajadores():
        """Cuántos temas se analizan a la vez: todos los núcleos menos 2 (quedan para el audio y la ventana), entre 1 y 8.
        Cada análisis corre en su propio proceso (con prioridad baja), así que aprovecha todos los núcleos de verdad."""
        return max(1, min(8, (os.cpu_count() or 2) - 2))

    def _n_trab(self):
        if self.modo_max:
            return max(1, min(12, os.cpu_count() or 2))
        return self._num_trabajadores()

    def _en_vuelo_max(self, n):
        """Cuántos análisis puede haber en curso a la vez (corriendo + en cola). Con un deck sonando se baja a lo mínimo
        (1 por cada 4 trabajadores, al menos 1) para no arriesgar el audio; sin audio, uno más que los trabajadores."""
        if _SONANDO and not self.modo_max:
            return max(1, n // 4)
        return n + 1               # los n trabajadores ocupados + 1 esperando: la cola es corta, así al empezar a sonar un deck casi no queda trabajo en curso

    def _analizar_todo(self):
        self._hechos = set()
        n = self._n_trab()
        self.n_procesos = n
        if n >= 2 and len(self.rutas) >= 3:
            try:
                self._analizar_paralelo(n)
                return
            except Exception:
                import traceback; traceback.print_exc()
                print("[análisis] el análisis en paralelo falló: se sigue de a un tema")
        self._analizar_secuencial()

    def _tarea(self, ruta):
        """Qué hay que hacer con este tema: 'full' (análisis completo), 'clave' (completar tonalidad/voz) o None (ya está).
        Devuelve (tarea, cache_key)."""
        cache_key = CACHE_DIR / (Path(ruta).stem + ".json")
        if self.forzar or not cache_key.exists():
            return "full", cache_key
        with open(cache_key, encoding="utf-8") as f:
            data = json.load(f)
        if "key" not in data or "voz" not in data:
            return "clave", cache_key
        return None, cache_key

    def _calentar(self):
        """numba compila (y guarda en su caché) las funciones de librosa la PRIMERA vez que se usan. Si varios procesos lo hacen
        a la vez en Windows pueden pisarse y morir ('access violation'). Por eso el primer tema de cada arranque se analiza
        solo, en el proceso de siempre; recién después se lanzan varios a la vez."""
        from setup import analisis as an
        if an._CALENTADO:
            return
        intentos = 0
        for i, ruta in enumerate(self.rutas, 1):
            if self.cancelar:
                return
            try:
                tarea, key = self._tarea(ruta)
            except Exception:
                continue
            if tarea is None:
                continue
            t0 = time.monotonic()
            intentos += 1
            try:
                res = an.analizar_archivo(ruta, solo_clave=(tarea == "clave"))
            except Exception as e:                   # un archivo dañado no debe tumbar el análisis en paralelo: se prueba con otro
                print(f"[análisis] no se pudo calentar con {os.path.basename(ruta)}: {e}")
                if intentos >= 6:
                    return
                continue
            if tarea == "full":
                _guardar_cache(key, res)
                print(f"Analizado: {os.path.basename(ruta)} -> {res['bpm']:.1f} BPM, clave {(res.get('key') or {}).get('camelot') or '?'}")
            else:
                with open(key, encoding="utf-8") as f:
                    data = json.load(f)
                data.update(res)
                _guardar_cache(key, data)
            self._hechos.add(ruta)
            self.tema_listo.emit(ruta); self.progreso.emit(i, len(self.rutas))
            return

    def _analizar_paralelo(self, n):
        from concurrent.futures._base import TimeoutError as _TO          # (imports directos: en Python 3.15 el paquete los carga 'perezosos' y no se pueden llamar)
        from concurrent.futures.process import ProcessPoolExecutor, BrokenProcessPool
        import multiprocessing
        from setup.analisis import TIMEOUT_ANALISIS, _analizar_archivo, _analizar_clave, _bajar_prioridad
        self._calentar()
        for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
            os.environ.setdefault(_v, "1")          # cada proceso usa UN hilo de cálculo: con varios procesos a la vez, no se pisan entre sí
        ctx = multiprocessing.get_context("spawn")
        pw = Path(sys.executable).with_name("pythonw.exe")             # el hijo no abre ventana negra
        if os.name == "nt" and pw.exists():
            ctx.set_executable(str(pw))
        total = len(self.rutas)
        print(f"[análisis] biblioteca: {n} temas a la vez (prioridad baja)")
        pool = ProcessPoolExecutor(max_workers=n, mp_context=ctx, initializer=_bajar_prioridad)
        if self.modo_max:
            os.environ["AUTOMIX_ANALISIS_MAX"] = "1"        # los procesos hijos heredan esto y NO bajan su prioridad
        else:
            os.environ.pop("AUTOMIX_ANALISIS_MAX", None)
        pend = deque()                      # (i, ruta, cache_key, tarea, futuro, t0), en el orden de la lista
        sig = iter(enumerate(self.rutas, 1))
        agotada = False
        falla = None
        try:
            while True:
                while (not agotada and len(pend) < self._en_vuelo_max(n) and not self.cancelar and _PRIORITARIOS == 0):
                    nxt = next(sig, None)
                    if nxt is None:
                        agotada = True
                        break
                    i, ruta = nxt
                    if ruta in self._hechos:            # ya se hizo en el calentamiento
                        continue
                    try:
                        tarea, key = self._tarea(ruta)
                    except Exception:
                        import traceback; traceback.print_exc()
                        tarea, key = None, None
                    if tarea is None:
                        self._hechos.add(ruta)
                        self.tema_listo.emit(ruta); self.progreso.emit(i, total)
                        continue
                    fut = pool.submit(_analizar_archivo if tarea == "full" else _analizar_clave, ruta)
                    pend.append((i, ruta, key, tarea, fut, time.monotonic()))
                if self.cancelar:
                    break
                if not pend:
                    if agotada:
                        break
                    time.sleep(0.2)         # un deck espera su análisis: se le cede el turno
                    continue
                i, ruta, key, tarea, fut, t0 = pend.popleft()
                try:
                    res = fut.result(timeout=TIMEOUT_ANALISIS)
                except (_TO, BrokenProcessPool) as e:
                    falla = e               # proceso colgado o caído: se corta el lote y sigue el modo de a uno
                    pend.appendleft((i, ruta, key, tarea, fut, t0))
                    break
                except Exception:
                    import traceback; traceback.print_exc()      # ese tema falló: se sigue con los demás
                    self._hechos.add(ruta)
                    self.tema_listo.emit(ruta); self.progreso.emit(i, total)
                    continue
                try:
                    if tarea == "full":
                        _guardar_cache(key, res)
                        k = (res.get("key") or {}).get("camelot")
                        print(f"Analizado: {os.path.basename(ruta)} -> {res['bpm']:.1f} BPM, clave {k or '?'}")
                    else:
                        with open(key, encoding="utf-8") as f:
                            data = json.load(f)
                        data.update(res)
                        _guardar_cache(key, data)
                        print(f"Clave y voz: {os.path.basename(ruta)} -> {(data.get('key') or {}).get('camelot') or '?'}")
                    if time.monotonic() - t0 > 60.0:
                        print(f"[análisis] ese tema tardó {time.monotonic() - t0:.0f} s")
                except Exception:
                    import traceback; traceback.print_exc()
                self._hechos.add(ruta)
                self.tema_listo.emit(ruta); self.progreso.emit(i, total)
        finally:
            try:
                procs = list((getattr(pool, "_processes", None) or {}).values())
            except Exception:
                procs = []
            try:
                pool.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass
            for pr in procs:
                try:
                    pr.kill()
                except Exception:
                    pass
        if falla is not None:
            if isinstance(falla, BrokenProcessPool):          # un proceso murió de golpe: la caché de numba pudo quedar a medias
                try:
                    from setup.analisis import _limpiar_cache_numba
                    _limpiar_cache_numba()
                except Exception:
                    pass
            raise RuntimeError(f"{type(falla).__name__}")

    def _analizar_secuencial(self):
        total = len(self.rutas)
        for i, ruta in enumerate(self.rutas, 1):
            if self.cancelar:
                break
            if ruta in getattr(self, "_hechos", ()):
                continue
            while _PRIORITARIOS > 0 and not self.cancelar:      # un deck está esperando su análisis: pasa primero
                time.sleep(0.2)
            try:
                cache_key = CACHE_DIR / (Path(ruta).stem + ".json")
                if self.forzar or not cache_key.exists():
                    t0 = time.monotonic()
                    result = analizar_archivo(ruta)
                    _guardar_cache(cache_key, result)
                    k = (result.get("key") or {}).get("camelot")
                    print(f"Analizado: {os.path.basename(ruta)} -> {result['bpm']:.1f} BPM, clave {k or '?'}")
                    if time.monotonic() - t0 > 60.0:
                        print(f"[análisis] ese tema tardó {time.monotonic() - t0:.0f} s")
                else:                                   # análisis viejo sin tonalidad: se completa solo la clave
                    with open(cache_key, encoding="utf-8") as f:
                        data = json.load(f)
                    if "key" not in data or "voz" not in data:
                        data.update(analizar_archivo(ruta, solo_clave=True))
                        _guardar_cache(cache_key, data)
                        print(f"Clave y voz: {os.path.basename(ruta)} -> {(data.get('key') or {}).get('camelot') or '?'}")
            except Exception:
                import traceback; traceback.print_exc()
            self.tema_listo.emit(ruta)
            self.progreso.emit(i, total)




class RehacerUno(QThread):
    """Vuelve a calcular el "1" de un tema cuando la grilla cambió de octava (el compás ya no tiene el mismo largo).
    Corre en un hilo + el proceso de análisis aparte, así no traba el audio que está sonando."""
    listo = Signal(str, object)           # (ruta, [fase, confianza] o None)

    def __init__(self, path, beats):
        super().__init__()
        self.path = path
        self.beats = [float(b) for b in beats]

    def run(self):
        try:
            r = analizar_archivo(self.path, solo_uno=self.beats).get("uno")
        except Exception:
            import traceback; traceback.print_exc()
            r = None
        self.listo.emit(self.path, r)
