"""AutoMix — modo Auto del cruce A/B: diseña el cruce de CADA par de temas.

Mantiene lo que funciona del cruce manual (el que viene entra al principio y se queda a pleno, el que sale baja de forma
progresiva, el bajo se traspasa en la pausa de 3 s del medio) pero con valores propios para cada mezcla, según lo que midió
del par de temas (dónde hay voz o melodía, dónde hay bombo y bajo, los compases y las frases):
  · DURACIÓN: en compases, nunca menos de 8 s (más los 3 s de pausa al 50 %), la que menos choque de voces tenga y que quepa
    en lo que le queda al que sale,
  · ENTRADA de B: siempre al principio (5-20 % de la mezcla, en una línea de compás de B); cuanto más choque de voces haya,
    un poco más tarde y con una subida más larga,
  · SALIDA de A: baja progresivamente; cuanto más choque de voces, antes se achican sus medios y agudos,
  · BAJO: se traspasa en una línea de compás del que sale, de preferencia durante la pausa del medio y al inicio de una frase.
El resultado es un dict para `perfil_cruce_bandas`. Este módulo solo calcula (no toca la interfaz ni el audio)."""
import math
import numpy as np
from setup.config import perfil_cruce_bandas

UMBRAL_VOZ = 0.45        # desde este valor (0..1) se considera que hay voz/melodía
PASO = 0.25              # resolución (s) con que se miran los temas
PAUSA = 3.0              # pausa del crossfader al 50 % (s)
MIN_DUR = 8.0            # el fundido dura al menos esto (sin contar la pausa)
DUR_IDEAL = 12.0         # a igualdad de choque, la que más se acerque a esto
MAX_DUR = 28.0
COMPASES = (2, 3, 4, 5, 6, 8, 10, 12, 16)


def _serie(valores, dt, pos, rate, largo):
    """Curva (cada PASO s reales desde ahora) de un dato del análisis. Fuera del tema vale 0."""
    n = int(largo / PASO) + 1
    out = np.zeros(n)
    if not valores:
        return out, False
    arr = np.asarray(valores, dtype=np.float64)
    k = ((pos + np.arange(n) * PASO * rate) / max(1e-6, dt)).astype(int)
    ok = (k >= 0) & (k < len(arr))
    out[ok] = arr[k[ok]]
    return out, True


def _compases_en(db, pos, rate, largo):
    """Instantes (s reales desde ahora) y números de orden de las líneas de compás que caen dentro de la mezcla."""
    if db is None or len(db) == 0:
        return np.array([]), np.array([], dtype=int)
    T = (np.asarray(db, dtype=np.float64) - pos) / max(1e-6, rate)
    idx = np.nonzero((T >= 0.0) & (T <= largo))[0]
    return T[idx], idx


def _t_de_T(T, D, pausa):
    """Posición del crossfader (0..1) a los T segundos de empezar, contando la pausa de 3 s al 50 %."""
    if not pausa:
        return min(1.0, max(0.0, T / D))
    m = 0.5 * D
    if T <= m:
        return max(0.0, T / D)
    if T <= m + PAUSA:
        return 0.5
    return min(1.0, (T - PAUSA) / D)


def _forma(D, pausa, compas, S, E, vs, ve, be):
    """Diseña las rampas para un fundido de D segundos (+ la pausa). Devuelve el dict con los parámetros y su explicación."""
    total = D + (PAUSA if pausa else 0.0)
    n = min(len(vs), int(total / PASO) + 1)
    vs, ve, be = vs[:n], ve[:n], be[:n]
    fs, fe = vs >= UMBRAL_VOZ, ve >= UMBRAL_VOZ
    juntos = fs & fe
    conflicto = float(juntos.mean()) if n else 0.0                         # fracción de la mezcla con voz en los dos
    m_ini = max(1, int(0.4 * n))
    choque_ini = float(juntos[:m_ini].mean())                              # y lo mismo en el tramo en que entra B

    # --- entrada de B: siempre al principio, en una línea de compás de B ---
    ent = 0.05 + 0.15 * min(1.0, 2.5 * choque_ini)                          # 5 %..20 % de la mezcla
    tb = ent * D
    T_e, _ = _compases_en(E.get("db"), E["pos"], E["rate"], 0.22 * D)
    cand = [float(t) for t in T_e if t >= 0.03 * D]                          # (si no hay línea tan al principio, entra sin ajustar)
    if cand:
        tb = min(cand, key=lambda t: abs(t - ent * D))
    rb_t = compas * (0.5 + 0.5 * min(1.0, 2.0 * choque_ini))
    rb_t = max(0.8, min(rb_t, 0.3 * D))
    if tb + rb_t > 0.4 * D:                                                # B tiene que estar a pleno antes de la pausa
        tb = max(0.0, min(tb, 0.4 * D - 0.8))
        rb_t = max(0.6, 0.4 * D - tb)

    # --- salida de A: progresiva; con voces chocando, sus medios y agudos se achican antes ---
    gamma = 1.0 + 0.9 * min(1.0, 1.5 * conflicto)                          # 1 = coseno de siempre · 1,9 = cae antes
    pa = 0.10 * (1.0 - min(1.0, 2.0 * conflicto))                          # sin choque: conserva todo un poquito más
    fa = 1.0
    fin_s = None                                                           # cuándo se queda sin voz el que sale
    m = max(1, int(2.0 / PASO))
    for i in range(n):
        if not fs[i:i + m].any():
            fin_s = i * PASO
            break
    if fin_s is not None:
        fa = max(0.65, min(1.0, _t_de_T(fin_s + compas, D, pausa)))
    pb, rb = tb / D, rb_t / D

    # --- bajo: una línea de compás del que sale, de preferencia en la pausa del medio y al inicio de una frase ---
    T_s, idx_s = _compases_en(S.get("db"), S["pos"], S["rate"], total)
    p0, p1 = 0.5 * D, 0.5 * D + (PAUSA if pausa else 0.0)
    centro = 0.5 * (p0 + p1)
    mejor = None
    primera_en_pausa = True
    for T, i in zip(T_s, idx_s):
        T = float(T)
        en_pausa = pausa and p0 <= T <= p1
        if en_pausa:
            if not primera_en_pausa:
                continue                                                   # el cambio se pide al empezar la pausa: vale la 1.ª línea
            primera_en_pausa = False
        if T < max(0.3 * D, tb + rb_t) or T > 0.9 * total:
            continue
        c = abs(T - centro) / D
        k = int(T / PASO)
        if k < len(be) and be[k] < 0.25:
            c += 1.2                                                       # el bajo de B todavía no suena: se quedaría un hueco
        if i % 8 == 0:
            c -= 0.12                                                      # inicio de frase
        if en_pausa:
            c -= 0.10
        if mejor is None or c < mejor[0]:
            mejor = (c, T, en_pausa)
    if mejor is None:
        ps = 0.5
    elif mejor[2]:
        ps = 0.5                                                           # se pide al empezar la pausa; cae en la 1.ª línea
    else:
        T = mejor[1] - 0.4 * compas                                        # se pide antes de la línea (el mezclador espera a la línea)
        t = T / D if T <= p0 else (T - (PAUSA if pausa else 0.0)) / D
        ps = math.floor(max(0.05, min(0.95, t)) * 100.0) / 100.0           # el crossfader avanza de 1 % en 1 %
    return {"pa": float(pa), "fa": float(fa), "pb": float(pb), "rb": float(rb), "ps": float(ps), "gamma": float(gamma),
            "conflicto": conflicto, "choque_ini": choque_ini, "fin_voz_a": fin_s}


def _coste(p, D, pausa, vs, ve, compat_fac):
    """Cuánto 'choca' la mezcla: segundos con voz de los dos sonando juntas (+ un poco del tiempo en que suenan los dos
    si las tonalidades o los tempos chocan). La pausa del medio se cuenta (los dos siguen sonando 3 s con el mismo nivel)."""
    clash = 0.0
    juntos = 0.0
    for i in range(len(vs)):
        t = _t_de_T(i * PASO, D, pausa)
        ha, hb, _la, _lb = perfil_cruce_bandas(t, p["pa"], p["pb"], p["ps"], rampa=p["rb"], fin_a=p["fa"], gamma_a=p["gamma"])
        juntos += ha * hb * PASO
        if vs[i] >= UMBRAL_VOZ and ve[i] >= UMBRAL_VOZ:
            clash += ha * hb * PASO
    return clash + compat_fac * juntos


def _razon(p, sale_con_voz, entra_con_voz):
    if p["conflicto"] > 0.5:
        return "los dos tienen voz casi todo el cruce: A achica sus medios antes y B entra con una subida más larga"
    if p["conflicto"] > 0.15:
        return "las voces se pisan en parte: A baja un poco antes"
    if sale_con_voz and not entra_con_voz:
        return "B es instrumental: entra enseguida bajo la voz de A"
    if entra_con_voz and not sale_con_voz:
        return "A ya está sin voz: B entra enseguida"
    return "sin choque de voces: cruce parejo"


def disenar(sale, entra, compat=None, dif_tempo=0.0):
    """Diseña el cruce de este par de temas.
    sale / entra: dict(voz, bajo, dt, pos, rate, bpm, db, resta)  · pos en s del tema, rate = velocidad real,
                  db = líneas de compás (s del tema), resta = segundos de música que le quedan.
    compat: 0/1/2 (armonía) o None · dif_tempo: diferencia relativa de BPM.
    Devuelve dict(dur, pausa, n, pa, fa, pb, rb, ps, gamma, nombre, razon).
    `dur` es el fundido (lo que recorre el crossfader); si `pausa` es True se le suman 3 s al 50 %."""
    bpm = float(sale.get("bpm", 0) or 0) * float(sale.get("rate", 1.0) or 1.0)
    compas = 240.0 / bpm if bpm > 20 else 2.0
    resta = sale.get("resta")
    cands = []
    for n in COMPASES:
        D = n * compas
        if D < MIN_DUR or D > MAX_DUR:
            continue
        if resta is not None and D + PAUSA > resta - 1.0:
            continue
        cands.append((n, D, True))
    if not cands:                                             # le queda poco al que sale: lo más largo que entre
        if resta is None:
            cands = [(0, MIN_DUR, True)]
        elif resta - 4.0 >= 5.0:
            cands = [(0, min(MIN_DUR, resta - 4.0), True)]
        else:
            cands = [(0, max(1.5, resta - 1.5), False)]       # tan poco que ni se hace la pausa
    largo = max(c[1] + (PAUSA if c[2] else 0.0) for c in cands)
    vs, vok_s = _serie(sale.get("voz"), sale.get("dt", 0.5), sale["pos"], sale["rate"], largo)
    ve, vok_e = _serie(entra.get("voz"), entra.get("dt", 0.5), entra["pos"], entra["rate"], largo)
    be, _ = _serie(entra.get("bajo"), entra.get("dt", 0.5), entra["pos"], entra["rate"], largo)
    compat_fac = 0.3 if (compat == 0 or dif_tempo > 0.08) else 0.0
    mejor = None
    for n, D, pausa in cands:
        k = int((D + (PAUSA if pausa else 0.0)) / PASO) + 1
        p = _forma(D, pausa, compas, sale, entra, vs, ve, be)
        c = _coste(p, D, pausa, vs[:k], ve[:k], compat_fac)
        c += 0.8 * abs(math.log2(D / DUR_IDEAL))
        if mejor is None or c < mejor[0]:
            mejor = (c, n, D, pausa, p)
    _c, n, D, pausa, p = mejor
    p = dict(p)
    p["dur"] = float(D)
    p["pausa"] = bool(pausa)
    p["n"] = int(n)
    con_voz = lambda v: bool((v >= UMBRAL_VOZ).any())
    p["razon"] = _razon(p, con_voz(vs), con_voz(ve))
    if not (vok_s and vok_e):
        p["razon"] += " (sin datos de voz de algún tema: se usó el diseño estándar)"
    if compat_fac:
        p["razon"] += " · tonalidad/tempo chocan"
    base = f"{n} compases · {D:.0f} s" if n else f"mezcla corta · {D:.0f} s"
    p["nombre"] = base + (" + pausa 3 s" if pausa else "")
    return p
