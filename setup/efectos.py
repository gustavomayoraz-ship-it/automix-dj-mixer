"""AutoMix — efectos de sonido para mezclar (sirena, bocina, láser, subida...). Se generan con numpy: no hace falta ningún archivo."""
import numpy as np
from scipy.signal import butter, sosfilt

# Cada efecto se normaliza a este nivel (RMS). El deslizador de efectos lo sube o baja desde ahí.
RMS_OBJETIVO = 0.11
PICO_MAX = 0.8


def _env(n, sr, ataque=0.008, relajo=0.02):
    e = np.ones(n)
    a = max(1, int(ataque * sr)); r = max(1, int(relajo * sr))
    e[:a] = np.linspace(0, 1, a); e[-r:] = np.minimum(e[-r:], np.linspace(1, 0, r))
    return e


def _ruido(n, rng):
    return rng.standard_normal(n)


def _filtro(x, tipo, fc, sr, orden=2):
    return sosfilt(butter(orden, fc, btype=tipo, fs=sr, output="sos"), x)


def _sirena(sr):
    n = int(2.4 * sr); t = np.arange(n) / sr
    f = 520 + 560 * (0.5 - 0.5 * np.cos(2 * np.pi * t / 0.8))            # sube y baja cada 0,8 s
    fase = 2 * np.pi * np.cumsum(f) / sr
    y = np.sin(fase) + 0.33 * np.sin(3 * fase) + 0.2 * np.sin(5 * fase)
    return y * _env(n, sr, 0.03, 0.35)


def _bocina(sr):
    partes = []
    for dur, pausa in ((0.28, 0.07), (0.28, 0.07), (0.85, 0.0)):
        n = int(dur * sr); t = np.arange(n) / sr
        y = np.zeros(n)
        for f in (415.3, 523.3, 622.3):                                     # acorde de bocina de aire
            fase = 2 * np.pi * f * t + 0.4 * np.sin(2 * np.pi * 6 * t)
            for k in range(1, 8):
                y += np.sin(k * fase) / k
        partes.append(y * _env(n, sr, 0.012, 0.06 if pausa else 0.25))
        partes.append(np.zeros(int(pausa * sr)))
    return np.concatenate(partes)


def _laser(sr):
    n = int(0.45 * sr); t = np.arange(n) / sr
    f = 3200 * np.exp(-t * 7.5) + 140
    fase = 2 * np.pi * np.cumsum(f) / sr
    y = np.sin(fase) + 0.4 * np.sin(2 * fase)
    return y * np.exp(-t * 3.0) * _env(n, sr, 0.002, 0.05)


def _subida(sr):
    rng = np.random.default_rng(3)
    n = int(3.2 * sr); t = np.arange(n) / sr; u = t / t[-1]
    ruido = _filtro(_ruido(n, rng), "high", 800, sr)
    # el ruido se va abriendo (más brillante) y más fuerte hacia el final
    ruido = ruido * (0.15 + 0.85 * u ** 2)
    f = 180 * (12.0 ** u)
    fase = 2 * np.pi * np.cumsum(f) / sr
    tono = 0.5 * np.sin(fase) * (0.2 + 0.8 * u)
    return (ruido * 0.55 + tono) * _env(n, sr, 0.05, 0.04)


def _impacto(sr):
    rng = np.random.default_rng(5)
    n = int(1.7 * sr); t = np.arange(n) / sr
    f = 32 + 90 * np.exp(-t * 14)
    fase = 2 * np.pi * np.cumsum(f) / sr
    bombo = np.sin(fase) * np.exp(-t * 2.6)
    golpe = _filtro(_ruido(n, rng), "low", 1800, sr) * np.exp(-t * 22) * 0.9
    return (bombo + golpe) * _env(n, sr, 0.001, 0.08)


def _caida(sr):
    rng = np.random.default_rng(7)
    n = int(1.6 * sr); t = np.arange(n) / sr; u = t / t[-1]
    f = 1800 * np.exp(-u * 3.2) + 70
    fase = 2 * np.pi * np.cumsum(f) / sr
    y = np.sin(fase) * 0.8 + _filtro(_ruido(n, rng), "low", 2500, sr) * 0.25
    return y * (1 - u) ** 1.5 * _env(n, sr, 0.005, 0.03)


def _redoble(sr):
    rng = np.random.default_rng(11)
    n = int(2.6 * sr); y = np.zeros(n)
    pos = 0.0; paso = 0.17
    golpe_base = _filtro(_ruido(int(0.12 * sr), rng), "high", 1200, sr) * np.exp(-np.arange(int(0.12 * sr)) / sr * 38)
    while pos < 2.3:
        i = int(pos * sr); g = (0.25 + 0.75 * pos / 2.3)
        seg = golpe_base[:max(0, min(len(golpe_base), n - i))]
        y[i:i + len(seg)] += seg * g
        pos += paso; paso = max(0.035, paso * 0.88)                        # cada vez más rápido
    i = int(2.35 * sr)                                                      # golpe final
    fin = _filtro(_ruido(n - i, rng), "high", 300, sr) * np.exp(-np.arange(n - i) / sr * 9)
    y[i:] += fin * 1.6
    return y * _env(n, sr, 0.002, 0.03)


# ───────────────────────── más efectos ─────────────────────────
def _palmas(n, sr, rng, dens, tono=(1200, 5200), vida=0.018):
    """n muestras de aplausos: ráfagas de ruido muy cortas repartidas al azar (dens = palmas por segundo, array o número)."""
    y = np.zeros(n)
    d = np.broadcast_to(np.asarray(dens, dtype=float), (n,)) if np.ndim(dens) == 0 else np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(dens)), dens)
    cuenta = rng.random(n) < d / sr
    for i in np.flatnonzero(cuenta):
        L = int(vida * sr * (0.6 + 0.8 * rng.random()))
        if i + L >= n:
            continue
        g = _ruido(L, rng) * np.exp(-np.arange(L) / (L / 4.0)) * (0.4 + 0.6 * rng.random())
        y[i:i + L] += g
    return _filtro(y, "band", [tono[0], tono[1]], sr)


def _aplausos(sr):
    rng = np.random.default_rng(21); n = int(3.2 * sr); u = np.linspace(0, 1, n)
    dens = np.interp(u, [0, .12, .6, 1], [30, 520, 420, 40])
    return _palmas(n, sr, rng, dens[::200]) * _env(n, sr, 0.05, 0.4)


def _ovacion(sr):
    rng = np.random.default_rng(22); n = int(4.2 * sr); u = np.linspace(0, 1, n)
    pal = _palmas(n, sr, rng, np.interp(np.linspace(0, 1, 60), [0, .1, .7, 1], [80, 900, 800, 60]), (900, 6000))
    vocal = _filtro(_ruido(n, rng), "band", [350, 1800], sr) * np.interp(u, [0, .15, .65, 1], [0, 1, .8, 0]) * (1 + 0.35 * np.sin(2 * np.pi * 5.5 * u * 4.2))
    return (pal * 1.0 + vocal * 0.55) * _env(n, sr, 0.05, 0.5)


def _palmas_ritmo(sr):
    rng = np.random.default_rng(23); n = int(3.0 * sr); y = np.zeros(n)
    for k in range(8):                                                       # 8 palmadas a 120 BPM
        i = int(k * 0.5 * sr); L = int(0.09 * sr)
        if i + L >= n:
            break
        seg = _filtro(_ruido(L, rng), "band", [900, 3800], sr) * np.exp(-np.arange(L) / sr * 55)
        y[i:i + L] += seg
    return y * _env(n, sr, 0.002, 0.05)


def _abucheo(sr):
    rng = np.random.default_rng(24); n = int(2.4 * sr); t = np.arange(n) / sr
    f = 150 - 40 * t / t[-1]
    fase = 2 * np.pi * np.cumsum(f * (1 + 0.04 * np.sin(2 * np.pi * 5 * t))) / sr
    y = sum(np.sin(k * fase) / k for k in range(1, 9))
    y = _filtro(y, "band", [180, 900], sr) + 0.15 * _filtro(_ruido(n, rng), "band", [300, 1500], sr)
    return y * _env(n, sr, 0.25, 0.5)


def _scratch(sr):
    rng = np.random.default_rng(25); n = int(1.2 * sr); t = np.arange(n) / sr
    pos = 0.5 + 0.5 * np.sin(2 * np.pi * (2.2 * t + 1.6 * t * t))           # vaivén de disco
    vel = np.abs(np.gradient(pos)) * sr / 2.0
    fase = 2 * np.pi * np.cumsum(180 + 900 * vel) / sr
    y = (np.sign(np.sin(fase)) * 0.5 + np.sin(fase * 2.01) * 0.3 + _ruido(n, rng) * 0.15)
    y = _filtro(y, "band", [300, 6000], sr)
    return y * np.minimum(1, vel * 3) * _env(n, sr, 0.005, 0.1)


def _freno_disco(sr):
    n = int(1.5 * sr); t = np.arange(n) / sr; u = t / t[-1]
    vel = (1 - u) ** 1.6
    base = np.cumsum(vel) / sr * 220
    y = np.sin(2 * np.pi * base) + 0.5 * np.sign(np.sin(2 * np.pi * base * 1.5))
    y = _filtro(y, "low", 2500, sr)
    return y * vel ** 0.5 * _env(n, sr, 0.003, 0.04)


def _rebobinado(sr):
    rng = np.random.default_rng(26); n = int(1.3 * sr); t = np.arange(n) / sr; u = t / t[-1]
    f = 200 * (14 ** u)
    fase = 2 * np.pi * np.cumsum(f) / sr
    y = np.sin(fase) + 0.4 * np.sign(np.sin(fase * 1.5)) + 0.3 * _ruido(n, rng)
    y = _filtro(y, "band", [250, 7000], sr)
    return y * (0.3 + 0.7 * u) * _env(n, sr, 0.01, 0.08)


def _policia(sr):
    n = int(2.6 * sr); t = np.arange(n) / sr
    f = 700 + 700 * (0.5 - 0.5 * np.cos(2 * np.pi * t / 0.35)) ** 1.0       # "yelp" rápido
    fase = 2 * np.pi * np.cumsum(f) / sr
    y = np.sign(np.sin(fase)) * 0.6 + np.sin(fase) * 0.5
    return _filtro(y, "low", 3500, sr) * _env(n, sr, 0.03, 0.25)


def _ambulancia(sr):
    n = int(2.6 * sr); t = np.arange(n) / sr
    f = np.where((t % 1.2) < 0.6, 960, 770).astype(float)                   # dos notas alternas (ta-tu)
    f = _filtro(f, "low", 25, sr, 1)
    fase = 2 * np.pi * np.cumsum(f) / sr
    y = np.sin(fase) + 0.35 * np.sin(2 * fase) + 0.15 * np.sin(3 * fase)
    return y * _env(n, sr, 0.03, 0.25)


def _alarma(sr):
    n = int(2.4 * sr); t = np.arange(n) / sr
    f = 1000 + 600 * (t / 0.5 % 1)                                          # diente de sierra ascendente
    fase = 2 * np.pi * np.cumsum(f) / sr
    y = np.sin(fase) + 0.3 * np.sin(2 * fase)
    return y * _env(n, sr, 0.02, 0.2)


def _aire_ataque(sr):
    n = int(5.0 * sr); t = np.arange(n) / sr
    f = 300 + 400 * np.minimum(1, t / 3.0) ** 2
    f = f * (1 + 0.5 * (t > 3.0) * np.sin(2 * np.pi * 1.5 * t) * 0.0)
    fase = 2 * np.pi * np.cumsum(f) / sr
    y = np.sin(fase) + 0.5 * np.sin(2 * fase) + 0.3 * np.sin(3 * fase)
    return y * np.interp(t, [0, 1.2, 4.2, 5.0], [0.1, 1.0, 1.0, 0]) * _env(n, sr, 0.3, 0.3)


def _barco(sr):
    n = int(2.4 * sr); t = np.arange(n) / sr
    y = sum(np.sin(2 * np.pi * f * t + 0.3 * np.sin(2 * np.pi * 3 * t)) / (i + 1) for i, f in enumerate((98, 196, 294, 392)))
    y = _filtro(y, "low", 1500, sr)
    return y * np.interp(t, [0, .12, 1.7, 2.4], [0, 1, .9, 0])


def _tren(sr):
    rng = np.random.default_rng(27); n = int(2.6 * sr); t = np.arange(n) / sr
    y = sum(np.sin(2 * np.pi * f * t) for f in (311, 392, 466)) * 0.5        # silbato de tren: acorde
    y += _filtro(_ruido(n, rng), "band", [900, 3500], sr) * 0.12
    return _filtro(y, "low", 3000, sr) * np.interp(t, [0, .1, 1.9, 2.6], [0, 1, .9, 0])


def _silbato(sr):
    rng = np.random.default_rng(28); n = int(0.9 * sr); t = np.arange(n) / sr
    f = 2800 + 120 * np.sin(2 * np.pi * 38 * t)
    y = np.sin(2 * np.pi * np.cumsum(f) / sr) + 0.12 * _filtro(_ruido(n, rng), "high", 2000, sr)
    return y * _env(n, sr, 0.02, 0.1)


def _platillo(sr):
    rng = np.random.default_rng(29); n = int(3.0 * sr); t = np.arange(n) / sr
    y = _filtro(_ruido(n, rng), "high", 3500, sr)
    y += 0.4 * sum(np.sin(2 * np.pi * f * t) for f in (3150, 4370, 5290, 6900)) * 0.25
    return y * np.exp(-t * 2.0) * _env(n, sr, 0.001, 0.2)


def _platillo_inv(sr):
    return _platillo(sr)[::-1].copy() * 1.0


def _charles(sr):
    rng = np.random.default_rng(30); n = int(1.6 * sr); y = np.zeros(n); paso = 0.1
    for k in range(int(1.5 / paso)):
        i = int(k * paso * sr); L = int(0.05 * sr)
        if i + L >= n:
            break
        y[i:i + L] += _filtro(_ruido(L, rng), "high", 6000, sr) * np.exp(-np.arange(L) / sr * 70) * (0.5 + 0.5 * (k % 2 == 0))
    return y * _env(n, sr, 0.001, 0.05)


def _timbal(sr):
    n = int(1.4 * sr); t = np.arange(n) / sr
    y = np.zeros(n)
    for ini, f0 in ((0.0, 190), (0.22, 150), (0.44, 110), (0.66, 80)):      # cuatro toms que bajan
        i = int(ini * sr); m = n - i
        tt = np.arange(m) / sr
        f = f0 * (1 + 0.5 * np.exp(-tt * 25))
        y[i:] += np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-tt * 7)
    return y * _env(n, sr, 0.002, 0.05)


def _gong(sr):
    n = int(4.0 * sr); t = np.arange(n) / sr
    y = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t * d) for f, a, d in ((110, 1, .9), (165, .6, 1.1), (232, .5, 1.3), (351, .35, 1.7), (496, .25, 2.2)))
    return y * (1 + 0.15 * np.sin(2 * np.pi * 3.2 * t)) * _env(n, sr, 0.002, 0.3)


def _campana(sr):
    n = int(2.2 * sr); t = np.arange(n) / sr
    y = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t * d) for f, a, d in ((880, 1, 2.2), (2217, .5, 3.0), (3520, .3, 4.0), (5100, .15, 5.0)))
    return y * _env(n, sr, 0.001, 0.2)


def _ding_ding(sr):
    n = int(2.0 * sr); y = np.zeros(n)
    for ini in (0.0, 0.35):
        i = int(ini * sr); m = n - i; tt = np.arange(m) / sr
        y[i:] += sum(a * np.sin(2 * np.pi * f * tt) * np.exp(-tt * d) for f, a, d in ((1318, 1, 4.0), (3300, .4, 6.0)))
    return y * _env(n, sr, 0.001, 0.2)


def _moneda(sr):
    n = int(0.6 * sr); t = np.arange(n) / sr
    f = np.where(t < 0.08, 988, 1319).astype(float)                         # estilo videojuego 8 bits: dos notas
    y = np.sign(np.sin(2 * np.pi * np.cumsum(f) / sr)) * 0.6
    return _filtro(y, "low", 6000, sr) * np.exp(-np.maximum(0, t - 0.1) * 7) * _env(n, sr, 0.002, 0.05)


def _power_up(sr):
    n = int(1.0 * sr); t = np.arange(n) / sr
    notas = (523, 659, 784, 1047, 1319, 1568)
    f = np.array([notas[min(len(notas) - 1, int(x * 9))] for x in t], dtype=float)
    y = np.sign(np.sin(2 * np.pi * np.cumsum(f) / sr)) * 0.55
    return _filtro(y, "low", 6000, sr) * np.exp(-np.maximum(0, t - 0.6) * 4) * _env(n, sr, 0.002, 0.08)


def _game_over(sr):
    n = int(1.5 * sr); t = np.arange(n) / sr
    notas = (392, 370, 349, 330)
    f = np.array([notas[min(3, int(x / 0.34))] for x in t], dtype=float)
    f = f * np.where(t > 1.0, 1 - (t - 1.0) * 0.8, 1)
    y = np.sign(np.sin(2 * np.pi * np.cumsum(f) / sr)) * 0.55
    return _filtro(y, "low", 3500, sr) * _env(n, sr, 0.004, 0.2)


def _fanfarria(sr):
    n = int(2.4 * sr); y = np.zeros(n)
    for ini, f0, dur in ((0.0, 392, 0.2), (0.22, 392, 0.2), (0.44, 392, 0.2), (0.66, 523, 0.9), (1.7, 659, 0.7)):
        i = int(ini * sr); m = min(int(dur * sr), n - i); tt = np.arange(m) / sr
        nota = sum(np.sin(2 * np.pi * f0 * k * tt) / k for k in range(1, 7))
        y[i:i + m] += _filtro(nota, "low", 3000, sr) * _env(m, sr, 0.015, 0.06)
    return y


def _trueno(sr):
    rng = np.random.default_rng(31); n = int(3.5 * sr); t = np.arange(n) / sr
    y = _filtro(_ruido(n, rng), "low", 220, sr) * np.exp(-t * 1.1) + 0.6 * _filtro(_ruido(n, rng), "low", 700, sr) * np.exp(-t * 3.0)
    y *= 0.6 + 0.4 * np.sin(2 * np.pi * 4 * t) ** 2
    return y * _env(n, sr, 0.03, 0.3)


def _explosion(sr):
    rng = np.random.default_rng(32); n = int(2.6 * sr); t = np.arange(n) / sr
    y = _filtro(_ruido(n, rng), "low", 900, sr) * np.exp(-t * 3.2) + np.sin(2 * np.pi * np.cumsum(45 + 80 * np.exp(-t * 8)) / sr) * np.exp(-t * 2.0)
    return y * _env(n, sr, 0.002, 0.2)


def _descarga(sr):
    rng = np.random.default_rng(33); n = int(1.0 * sr); t = np.arange(n) / sr
    y = _filtro(_ruido(n, rng), "high", 1500, sr) * (np.sin(2 * np.pi * 50 * t) > -0.2) * np.exp(-t * 3.0)
    y += 0.4 * np.sin(2 * np.pi * np.cumsum(2000 + 1500 * np.sin(2 * np.pi * 17 * t)) / sr) * np.exp(-t * 3.0)
    return y * _env(n, sr, 0.001, 0.1)


def _ovni(sr):
    n = int(2.2 * sr); t = np.arange(n) / sr
    f = 600 + 350 * np.sin(2 * np.pi * 3.3 * t) + 150 * np.sin(2 * np.pi * 11 * t)
    y = np.sin(2 * np.pi * np.cumsum(f) / sr)
    return y * _env(n, sr, 0.15, 0.4)


def _helicoptero(sr):
    rng = np.random.default_rng(34); n = int(3.0 * sr); t = np.arange(n) / sr
    pulso = (0.5 + 0.5 * np.sin(2 * np.pi * 11 * t)) ** 3
    y = _filtro(_ruido(n, rng), "low", 500, sr) * pulso
    return y * np.interp(t, [0, .5, 2.4, 3.0], [0, 1, 1, 0])


def _gotas(sr):
    n = int(2.4 * sr); y = np.zeros(n)
    for ini, f0 in ((0.0, 1300), (0.5, 1100), (0.95, 1500), (1.5, 900)):
        i = int(ini * sr); m = int(0.18 * sr); tt = np.arange(m) / sr
        y[i:i + m] += np.sin(2 * np.pi * np.cumsum(f0 * (1 + 2.0 * tt)) / sr) * np.exp(-tt * 28)
    return y


def _risa_sinte(sr):
    n = int(1.6 * sr); t = np.arange(n) / sr
    y = np.zeros(n)
    for k in range(7):                                                       # "ja ja ja" sintético: sílabas con formantes
        i = int((0.05 + k * 0.17) * sr); m = int(0.12 * sr)
        if i + m >= n:
            break
        tt = np.arange(m) / sr; f0 = 260 - k * 12
        voz = sum(np.sin(2 * np.pi * f0 * h * tt) / h for h in range(1, 12))
        voz = _filtro(voz, "band", [500, 1600], sr)
        y[i:i + m] += voz * np.exp(-tt * 14) * (1 - 0.06 * k)
    return y * _env(n, sr, 0.01, 0.1)


def _hey(sr):
    n = int(0.7 * sr); t = np.arange(n) / sr
    f0 = 200 + 80 * np.exp(-((t - 0.12) / 0.1) ** 2) - 60 * t
    fase = 2 * np.pi * np.cumsum(f0) / sr
    voz = sum(np.sin(h * fase) / h for h in range(1, 14))
    form = _filtro(voz, "band", [450, 2600], sr)
    return form * np.interp(t, [0, .04, .35, .7], [0, 1, .8, 0])


def _tension(sr):
    rng = np.random.default_rng(35); n = int(4.0 * sr); t = np.arange(n) / sr; u = t / t[-1]
    y = sum(np.sin(2 * np.pi * np.cumsum(f * (1 + 0.5 * u)) / sr) for f in (110, 164.8, 233)) * 0.4
    y += _filtro(_ruido(n, rng), "band", [400, 4000], sr) * u ** 2 * 0.5
    return y * (0.2 + 0.8 * u) * _env(n, sr, 0.1, 0.05)


def _barrido_ruido(sr):
    rng = np.random.default_rng(36); n = int(2.2 * sr); u = np.linspace(0, 1, n)
    r = _ruido(n, rng); salida = np.zeros(n); bloque = 2048
    for i in range(0, n, bloque):
        fc = 300 * (40 ** (1 - u[i])) + 200
        sos = butter(2, min(fc, 0.45 * sr), btype="low", fs=sr, output="sos")
        salida[i:i + bloque] = sosfilt(sos, r[i:i + bloque])
    return salida * (1 - u) ** 0.5 * _env(n, sr, 0.01, 0.1)


def _sub_drop(sr):
    n = int(2.4 * sr); t = np.arange(n) / sr
    f = 90 * np.exp(-t * 1.3) + 30
    return np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t * 0.9) * _env(n, sr, 0.004, 0.2)


def _snare_unica(sr):
    rng = np.random.default_rng(37); n = int(0.5 * sr); t = np.arange(n) / sr
    y = _filtro(_ruido(n, rng), "high", 900, sr) * np.exp(-t * 16) + np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30) * 0.7
    return y * _env(n, sr, 0.001, 0.05)


def _clap_drop(sr):
    rng = np.random.default_rng(38); n = int(1.0 * sr); y = np.zeros(n)
    for ini in (0.0, 0.012, 0.027):
        i = int(ini * sr); m = int(0.2 * sr)
        y[i:i + m] += _filtro(_ruido(m, rng), "band", [900, 3500], sr) * np.exp(-np.arange(m) / sr * 25)
    return y * _env(n, sr, 0.001, 0.1)


EFECTOS = (
    # — aplausos y público —
    ("👏 Aplausos", _aplausos, "Aplausos de público (3,2 s)"),
    ("🙌 Ovación", _ovacion, "Aplausos fuertes con gritos de público (4,2 s)"),
    ("🖐 Palmas al ritmo", _palmas_ritmo, "Ocho palmadas a 120 BPM (3 s)"),
    ("😂 Risas", _risa_sinte, "Risas sintéticas: ja ja ja (1,6 s)"),
    ("🗣 ¡Hey!", _hey, "Grito corto de 'hey' (0,7 s)"),
    ("👎 Abucheo", _abucheo, "Abucheo grave de público (2,4 s)"),
    # — sirenas y bocinas —
    ("🚨 Sirena", _sirena, "Sirena que sube y baja (2,4 s)"),
    ("🚓 Policía (yelp)", _policia, "Sirena de policía rápida (2,6 s)"),
    ("🚑 Ambulancia", _ambulancia, "Dos notas alternas, ta-tu (2,6 s)"),
    ("⚠ Alarma", _alarma, "Alarma ascendente repetida (2,4 s)"),
    ("📯 Bocina de aire", _bocina, "Bocina de DJ: dos toques cortos y uno largo (1,6 s)"),
    ("📢 Bocina larga", _aire_ataque, "Bocina de aire que sube y se sostiene (5 s)"),
    ("🚢 Barco", _barco, "Bocina grave de barco (2,4 s)"),
    ("🚂 Tren", _tren, "Silbato de tren (2,6 s)"),
    ("🔔 Silbato", _silbato, "Silbato de árbitro (0,9 s)"),
    # — subidas, caídas y tensión —
    ("🚀 Subida (riser)", _subida, "Barrido que va subiendo y se abre: para anunciar un drop (3,2 s)"),
    ("🌀 Tensión", _tension, "Acordes y ruido que crecen: antes del drop (4 s)"),
    ("⬇ Caída", _caida, "Barrido que baja y se apaga (1,6 s)"),
    ("🌫 Barrido de ruido", _barrido_ruido, "Ruido que se va cerrando (2,2 s)"),
    ("⏪ Rebobinado", _rebobinado, "Cinta que se rebobina rápido (1,3 s)"),
    ("🛑 Freno de disco", _freno_disco, "El disco se frena de golpe (1,5 s)"),
    ("💿 Scratch", _scratch, "Vaivén de disco de DJ (1,2 s)"),
    # — golpes y percusión —
    ("💥 Impacto", _impacto, "Golpe grave tipo explosión: para marcar el drop (1,7 s)"),
    ("🔊 Sub drop", _sub_drop, "Bajo muy grave que cae (2,4 s)"),
    ("💣 Explosión", _explosion, "Explosión con cola grave (2,6 s)"),
    ("⛈ Trueno", _trueno, "Trueno lejano (3,5 s)"),
    ("🥁 Redoble", _redoble, "Redoble de caja que se acelera y cierra con un golpe (2,6 s)"),
    ("🥁 Caja (snare)", _snare_unica, "Un golpe de caja (0,5 s)"),
    ("👏 Clap", _clap_drop, "Palmada de sintetizador (1 s)"),
    ("🎼 Timbales", _timbal, "Cuatro toms que van bajando (1,4 s)"),
    ("🎩 Charles", _charles, "Ráfaga de hi-hat (1,6 s)"),
    ("🥏 Platillo", _platillo, "Crash de platillo (3 s)"),
    ("◀🥏 Platillo inverso", _platillo_inv, "Platillo al revés: sube hasta el golpe (3 s)"),
    ("🔱 Gong", _gong, "Gong profundo (4 s)"),
    # — campanas y melodías —
    ("🔔 Campana", _campana, "Campana brillante (2,2 s)"),
    ("🛎 Ding ding", _ding_ding, "Dos timbres de recepción (2 s)"),
    ("🎺 Fanfarria", _fanfarria, "Fanfarria de trompetas (2,4 s)"),
    ("🪙 Moneda (8 bits)", _moneda, "Moneda de videojuego (0,6 s)"),
    ("⭐ Power-up", _power_up, "Subida de notas estilo videojuego (1 s)"),
    ("☠ Game over", _game_over, "Fin de juego descendente (1,5 s)"),
    # — láser y ciencia ficción —
    ("🔫 Láser", _laser, "Disparo láser descendente (0,5 s)"),
    ("⚡ Descarga eléctrica", _descarga, "Chisporroteo eléctrico (1 s)"),
    ("🛸 OVNI", _ovni, "Vibrato espacial (2,2 s)"),
    ("🚁 Helicóptero", _helicoptero, "Aspas de helicóptero que pasa (3 s)"),
    ("💧 Gotas", _gotas, "Cuatro gotas de agua (2,4 s)"),
)


def generar(indice, sr):
    """Devuelve el efecto como array estéreo float32 ya normalizado (sin pasarse de nivel)."""
    y = np.asarray(EFECTOS[indice][1](sr), dtype=np.float64)
    rms = float(np.sqrt(np.mean(y * y))) + 1e-9
    y = y * (RMS_OBJETIVO / rms)
    y = np.tanh(y / PICO_MAX) * PICO_MAX                                    # recorte suave: ningún pico se escapa
    return np.stack([y, y], axis=1).astype(np.float32)


class EfectoSalida:
    """Reproduce un efecto encima de la mezcla (lo suma antes del limitador)."""
    def __init__(self, sr):
        self.sr = sr
        self.buf = None
        self.pos = 0
        self.vol = 0.6                  # 0..1 (se aplica al cuadrado: 60 % queda unos 5 dB por debajo de la música, 100 % unos 3 dB por encima)
        self._cache = {}

    @property
    def ganancia(self):
        return float(self.vol) ** 2 * 2.6

    def lanzar(self, indice):
        b = self._cache.get(indice)
        if b is None:
            b = self._cache[indice] = generar(indice, self.sr)
        self.pos = 0
        self.buf = b

    def detener(self):
        self.buf = None

    @property
    def sonando(self):
        return self.buf is not None

    def sumar(self, mix):
        """Lo llama el callback de audio: suma el trozo que toca a `mix`."""
        b = self.buf
        if b is None:
            return mix
        n = len(mix); p = self.pos
        seg = b[p:p + n]
        if len(seg) == 0:
            self.buf = None
            return mix
        if len(seg) < n:
            seg = np.vstack([seg, np.zeros((n - len(seg), 2), dtype=np.float32)])
            self.buf = None
        else:
            self.pos = p + n
        return mix + seg * self.ganancia
