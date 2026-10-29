"""AutoMix — truco para cruzar temas que no combinan: el que sale se va cerrando en un filtro pasa-bajos y se disuelve
en un eco sincronizado con su compás, así el que entra aparece sobre una cola que se apaga sola.
Todo se maneja por el volumen con que está sonando el tema que sale (sirve para cualquier forma de cruce)."""
import math
import numpy as np
from scipy.signal import lfilter


def _suave(x):
    x = 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)
    return x * x * (3.0 - 2.0 * x)


class EcoSalida:
    FC_ABIERTO = 16000.0       # filtro abierto (no se nota)
    FC_CERRADO = 550.0         # hasta dónde se cierra cuando el tema que sale ya casi no se oye
    FEEDBACK = 0.52            # cuánto de cada repetición vuelve al eco
    NIVEL_ECO = 0.8            # volumen del eco que se suma a la mezcla
    FC_REALIM = 3200.0         # cada repetición suena un poco más oscura que la anterior
    COLA_S = 4.0               # cuánto sigue sonando la cola después de soltar
    MAX_ARMADO_S = 90.0        # seguridad: si nadie lo suelta, se suelta solo

    def __init__(self, sr=44100, blocksize=1024):
        self.sr = int(sr)
        self.activo = False            # el callback lo procesa mientras esté en True
        self.armado = False            # True = la mezcla en curso lo usa; al soltarlo la cola sigue unos segundos
        self.lado = "a"                # qué deck es el que sale
        self.retardo = int(0.4 * sr)   # muestras entre repeticiones (sincronizado con el compás del que sale)
        self._n = int(2.0 * sr) + int(blocksize) * 2
        self._ring = np.zeros((self._n, 2), dtype=np.float32)
        self._w = 0
        self._zi_f = np.zeros((2, 2))                 # biquad pasa-bajos (2 secciones de estado × 2 canales)
        self._zi_r = np.zeros((1, 2))                 # pasa-bajos de la realimentación
        self._a_r = 1.0 - math.exp(-2.0 * math.pi * self.FC_REALIM / self.sr)
        self._pedir_limpiar = False
        self._t_cola = 0.0
        self._t_armado = 0.0
        self._send = 0.0

    # ---- lo maneja la ventana (hilo de la interfaz) ----
    def armar(self, lado, retardo_s):
        self.lado = "a" if lado == "a" else "b"
        self.retardo = int(max(0.15, min(0.95, float(retardo_s))) * self.sr)
        self._pedir_limpiar = True
        self._t_cola = 0.0; self._t_armado = 0.0; self._send = 0.0
        self.armado = True
        self.activo = True

    def soltar(self):
        self.armado = False            # la cola del eco sigue sonando COLA_S segundos y luego se apaga sola

    # ---- callback de audio ----
    def _biquad(self, fc):
        w0 = 2.0 * math.pi * min(fc, 0.45 * self.sr) / self.sr
        q = 0.75
        al = math.sin(w0) / (2.0 * q)
        c = math.cos(w0)
        b0 = (1.0 - c) / 2.0; b1 = 1.0 - c; b2 = b0
        a0 = 1.0 + al; a1 = -2.0 * c; a2 = 1.0 - al
        return np.array([b0 / a0, b1 / a0, b2 / a0]), np.array([1.0, a1 / a0, a2 / a0])

    def aplicar(self, p_a, p_b, g_a, g_b, frames):
        """Recibe las dos señales YA con su volumen. Devuelve (p_a, p_b, eco): el que sale filtrado y la cola de eco (o None)."""
        dt = frames / float(self.sr)
        if self._pedir_limpiar:
            self._ring.fill(0.0); self._zi_f.fill(0.0); self._zi_r.fill(0.0); self._w = 0
            self._pedir_limpiar = False
        if self.armado:
            self._t_armado += dt
            if self._t_armado > self.MAX_ARMADO_S:
                self.armado = False
            self._t_cola = 0.0
        else:
            self._t_cola += dt
            if self._t_cola > self.COLA_S:
                self.activo = False
                return p_a, p_b, None
        sale_a = self.lado == "a"
        src = p_a if sale_a else p_b
        g = float(g_a if sale_a else g_b)
        x = 1.0 - min(1.0, max(0.0, g))                      # 0 = suena a pleno · 1 = ya no se oye
        if self.armado:
            fc = self.FC_ABIERTO * (self.FC_CERRADO / self.FC_ABIERTO) ** _suave((x - 0.10) / 0.85)
            send_obj = _suave((x - 0.25) / 0.5)
        else:
            fc, send_obj = self.FC_CERRADO, 0.0
        if fc < 0.97 * self.FC_ABIERTO:
            b, a = self._biquad(fc)
            filtrada, self._zi_f = lfilter(b, a, src, axis=0, zi=self._zi_f)
            filtrada = filtrada.astype(np.float32)
        else:
            filtrada = src
            self._zi_f.fill(0.0)
        # eco: lo que se grabó hace `retardo` muestras sale ahora, y vuelve a entrar (más oscuro y más bajo)
        n, D, w = self._n, max(self.retardo, frames), self._w
        r = (w - D) % n
        if r + frames <= n:
            eco = self._ring[r:r + frames].copy()
        else:
            eco = np.concatenate((self._ring[r:], self._ring[:r + frames - n]))
        s0, s1 = self._send, send_obj
        self._send = s1
        env = np.linspace(s0, s1, frames, dtype=np.float32)[:, None] if s0 != s1 else s1
        real, self._zi_r = lfilter([self._a_r], [1.0, -(1.0 - self._a_r)], eco, axis=0, zi=self._zi_r)
        nuevo = filtrada * env + real.astype(np.float32) * self.FEEDBACK
        if w + frames <= n:
            self._ring[w:w + frames] = nuevo
        else:
            k = n - w
            self._ring[w:] = nuevo[:k]; self._ring[:frames - k] = nuevo[k:]
        self._w = (w + frames) % n
        eco *= self.NIVEL_ECO
        if sale_a:
            return filtrada, p_b, eco
        return p_a, filtrada, eco
