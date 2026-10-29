"""AutoMix — sonoridad (volumen que se oye) de los temas y parejado del nivel al mezclar.
· `ganancia_k`: reemplaza al Auto-Gain por RMS con una medida parecida a LUFS (filtro K de la norma BS.1770 y compuertas que ignoran
  los silencios y los tramos muy bajos), así dos temas con la misma sonoridad real suenan igual de fuertes aunque tengan intros calladas.
· `trim_entrada_db`: cuánto subir o bajar el tema que entra al empezar el cruce para que suene al nivel del que sale (y se va soltando hasta 0)."""
import math
import numpy as np

try:
    from scipy.signal import sosfilt, tf2sos
except ImportError:                                  # sin scipy no hay filtro K: el que llama se queda con el RMS de siempre
    sosfilt = tf2sos = None

TRIM_MAX_DB = 3.0            # el entrante como mucho se corrige ±3 dB al arrancar
BLOQUE_S = 0.4               # bloques de 400 ms (como la norma)
COMPUERTA_ABS = 1e-7         # ≈ -70 LUFS en potencia (1e-7)
COMPUERTA_REL_DB = 10.0      # se ignoran los bloques 10 dB por debajo del promedio


def _sos_k(sr):
    """Filtro K de BS.1770 (realce de agudos + pasa-altos) para cualquier frecuencia de muestreo."""
    f0, G, Q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    K = math.tan(math.pi * f0 / sr); Vh = 10.0 ** (G / 20.0); Vb = Vh ** 0.4996667741545416
    a0 = 1.0 + K / Q + K * K
    b1 = [(Vh + Vb * K / Q + K * K) / a0, 2.0 * (K * K - Vh) / a0, (Vh - Vb * K / Q + K * K) / a0]
    a1 = [1.0, 2.0 * (K * K - 1.0) / a0, (1.0 - K / Q + K * K) / a0]
    f0, Q = 38.13547087602444, 0.5003270373238773
    K = math.tan(math.pi * f0 / sr)
    a0 = 1.0 + K / Q + K * K
    a2 = [1.0, 2.0 * (K * K - 1.0) / a0, (1.0 - K / Q + K * K) / a0]
    return np.vstack([tf2sos(b1, a1), tf2sos([1.0, -2.0, 1.0], a2)])


def rms_k(audio, sr):
    """RMS (lineal) con peso K y compuertas, de un audio estéreo (n, 2). None si no se puede medir (sin scipy, muy corto o en silencio)."""
    if sosfilt is None or audio is None or len(audio) < int(2 * BLOQUE_S * sr):
        return None
    sos = _sos_k(sr)
    n_b = int(BLOQUE_S * sr)
    energias = []
    chunk = n_b * 75                                 # ~30 s por vez: poca memoria
    zi = None
    for ini in range(0, (len(audio) // n_b) * n_b, chunk):
        x = np.asarray(audio[ini:min(len(audio), ini + chunk)], dtype=np.float64)
        n_ok = (len(x) // n_b) * n_b
        if n_ok == 0:
            break
        y = np.empty_like(x[:n_ok])
        for c in range(x.shape[1]):
            y[:, c] = sosfilt(sos, x[:n_ok, c])      # (el estado entre trozos no importa para una medida global)
        e = (y * y).reshape(-1, n_b, y.shape[1]).mean(axis=(1, 2))
        energias.append(e)
    if not energias:
        return None
    e = np.concatenate(energias)
    e = e[e > COMPUERTA_ABS]
    if not len(e):
        return None
    media = float(e.mean())
    e = e[e > media * 10.0 ** (-COMPUERTA_REL_DB / 10.0)]
    return math.sqrt(float(e.mean())) if len(e) else None


def ganancia_k(audio, sr, objetivo=0.15, lo=0.25, hi=4.0):
    """Ganancia para llevar el audio a la sonoridad `objetivo` (la misma escala que el Auto-Gain de siempre). None si no se pudo medir."""
    r = rms_k(audio, sr)
    if r is None or r < 1e-6:
        return None
    return float(np.clip(objetivo / r, lo, hi))


def nivel_local(rms, dt, pos, rate, ganancia, ventana_s):
    """Nivel (lineal) que se va a oír en los próximos `ventana_s` s reales: promedio de la curva de energía del análisis × la ganancia del deck."""
    if rms is None or len(rms) == 0 or dt <= 0:
        return None
    arr = np.asarray(rms, dtype=np.float64)
    k0 = int(max(0.0, pos) / dt); k1 = int((max(0.0, pos) + ventana_s * max(1e-6, rate)) / dt) + 1
    seg = arr[k0:min(len(arr), max(k0 + 1, k1))]
    return float(seg.mean() * ganancia) if len(seg) else None


def trim_entrada_db(nivel_sale, nivel_entra):
    """dB a sumarle al que entra para que arranque al mismo nivel que el que sale (limitado a ±TRIM_MAX_DB). 0 si falta algún dato."""
    if not nivel_sale or not nivel_entra or nivel_sale <= 1e-5 or nivel_entra <= 1e-5:
        return 0.0
    d = 20.0 * math.log10(nivel_sale / nivel_entra)
    return float(max(-TRIM_MAX_DB, min(TRIM_MAX_DB, d)))
