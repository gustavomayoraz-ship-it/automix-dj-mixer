"""AutoMix — modo Auto del cruce A/B: diseña el cruce de CADA par de temas.

Mantiene lo que funciona del cruce manual (el que viene entra al principio y se queda a pleno, el que sale baja de forma
progresiva, el bajo se traspasa en la pausa de 3 s del medio) pero con valores propios para cada mezcla, según lo que midió
del par de temas (dónde hay voz o melodía, dónde hay bombo y bajo, los compases y las frases):
  · DURACIÓN: en compases, nunca menos de 12 s (más los 3 s de pausa al 50 %), la que menos choque de voces tenga y que quepa
    en lo que le queda al que sale,
  · ENTRADA de B: siempre al principio (5-20 % de la mezcla, en una línea de compás de B); cuanto más choque de voces haya,
    un poco más tarde y con una subida más larga,
  · SALIDA de A: baja progresivamente; cuanto más choque de voces, antes se achican sus medios y agudos,
  · BAJO: se traspasa en una línea de compás del que sale, de preferencia durante la pausa del medio y al inicio de una frase.
  · RITMO: la primera mitad del fundido frena al acercarse al cruce de las dos líneas, sale lento y acelera hasta el 50 % (ver `pos_cruce`), ahí espera 3 s y sigue parejo.
El resultado es un dict para `perfil_cruce_bandas`. Este módulo solo calcula (no toca la interfaz ni el audio)."""
import math
import numpy as np
from setup.config import (DEF_FIN_A, DEF_GAMMA_A, DEF_PUNTO_A, DEF_PUNTO_B, DEF_PUNTO_S, DEF_RAMPA_B, perfil_cruce_bandas, perfil_cruce_ab)

UMBRAL_VOZ = 0.45        # desde este valor (0..1) se considera que hay voz/melodía
PASO = 0.25              # resolución (s) con que se miran los temas
PAUSA = 3.0              # pausa del crossfader al 50 % (s)
PAUSA_POS = 0.5          # dónde se queda la pausa, en posición del crossfader (0.5 = en el medio; entre 0.25 y 0.75)
MIN_DUR = 12.0           # el fundido dura al menos esto (sin contar la pausa)
DUR_IDEAL = 15.0         # a igualdad de choque, la que más se acerque a esto
# RITMO de la primera mitad del fundido: avanza parejo hasta que EMPIEZA la rampa de B (la línea violeta); desde ahí el crossfader va
# frenando hasta moverse muy suavecito en el CRUCE de las dos líneas, sigue igual de lento al salir y después va acelerando de a poco
# hasta llegar al 50 %. Ver `pos_cruce`.
ZONA_K = 10.0             # cuánto se frena en el cruce (5 = a ~1/6 de la velocidad de afuera)
ZONA_MIN = 0.25          # la frenada antes del cruce dura como mínimo esto (en posición del crossfader, 0..1)
RB_MIN = 0.12            # la subida de B abarca como mínimo esto del recorrido del crossfader
MAX_DUR = 18.0
ENT_MIN = 0.01          # B empieza a entrar como muy pronto a este punto del tiempo del fundido (fracción)
ENT_MAX = 0.04          # ... y como muy tarde a este (con más choque de voces entra más tarde)
ZONA_ACEL = 0.10         # 1 = después del cruce acelera de a poco hasta el 50 % · menos = recupera la velocidad antes de la mitad
ESTRATEGIA = 2.0         # 2 = como tu cruce MANUAL (tu forma, tu duración, la pausa y el frenado de ⚙), con la duración en compases enteros · 1 = Pro (mezcla larga en frase, sin pausa ni frenado) · 0 = la clásica
ESPERA_FRASE = 8.0       # al llegar a la marca del auto-enganche, espera hasta este máximo (s) al próximo inicio de frase (8 compases) del tema que sale · 0 = arranca justo en la marca
PAUSA_EN_LINEA = 1.0     # 1 = la pausa del 50 % termina en una línea de compás del que sale (después del cambio de bajo) · 0 = dura siempre lo mismo
ADAPTA_DUR = 1.0         # 1 = el Auto 'como mi manual' acorta el fundido (¾) si chocan la tonalidad o el tempo · 0 = siempre el mismo largo
# --- CONFIGURACIÓN PROPIA DEL AUTO «como mi manual» (estrategia 2): no toca los deslizadores ni el ritmo del cruce MANUAL ---
AUTO_PA = DEF_PUNTO_A     # A (sale)
AUTO_PB = DEF_PUNTO_B     # B (entra)
AUTO_RB = DEF_RAMPA_B     # B sube en
AUTO_FA = DEF_FIN_A       # A termina en
AUTO_G = DEF_GAMMA_A      # forma de A
AUTO_PS = DEF_PUNTO_S     # bajo (cambia)
AUTO_PAUSA = 3.0          # pausa del Auto (s)
AUTO_PAUSA_POS = 0.5      # dónde se queda la pausa del Auto (posición del crossfader)
ACEL_POS = 0.0           # estrategia 2: hasta dónde ACELERA el crossfader desde el inicio (posición 0..1); 0 = automático: hasta el cruce de las dos curvas
S2_FRENO = 3.0           # estrategia 2: cuánto frena desde ahí hasta la pausa (× : 1 = no frena · la velocidad en la pausa es 1/× de la máxima)
START_V = 0.35           # estrategia 2: velocidad con que arranca el crossfader (× la máxima)
MAX_SEG_MANUAL = 30.0    # estrategia 2: el cruce no dura más de esto (s)
MAN_COMPASES = 8.0       # estrategia 2: largo del fundido en compases (así dura lo mismo, en compases, a cualquier tempo) · 0 = usar los segundos del deslizador «Duración»
PRO_COMPASES = 16.0      # largo de la mezcla Pro en compases (4, 8, 16 o 32: se toma el más cercano que quepa en lo que le queda al que sale)
ZONA_V = 1.5             # tope: fuera del frenado el crossfader nunca va a más de esta velocidad (× la velocidad media de la primera mitad)
INC_ACTIVO = 1.0         # 1 = con temas incompatibles (BPM muy distintos) el que suena baja de volumen en INC_DUR s y el nuevo entra a su tempo natural antes de que llegue a cero · 0 = el cruce simple de siempre
INC_DUR = 10.0           # duración de la rampa de bajada del tema que suena (s)
INC_ENTRA = 0.15         # el tema nuevo entra cuando al que sale le queda este volumen (fracción: 0.15 = 15 %)
INC_SUBE = 0.4           # el tema nuevo sube a volumen pleno en tantos segundos (0 = entra de golpe)
INC_BPM = 0.22           # diferencia máxima de BPM (fracción: 0.22 = 22 %) para mezclar emparejando; más que esto = temas incompatibles
BREAK_ACTIVO = 0.0        # 1 = antes de la marca roja se vigila un «break» del tema que suena (un tramo donde baja la energía) y se mezcla ahí · 0 = solo la marca
BREAK_VENTANA = 0.15      # cuánto antes de la marca se empieza a vigilar (fracción de la duración del tema: 0.15 = 15 %)
BREAK_NIVEL = 0.55        # un compás cuenta como break si su energía es menor que esta fracción de la energía normal del tema
BREAK_COMPASES = 2.0      # el break tiene que durar al menos tantos compases seguidos
DEFECTOS = {k: v for k, v in dict(AUTO_PA=AUTO_PA, AUTO_PB=AUTO_PB, AUTO_RB=AUTO_RB, AUTO_FA=AUTO_FA, AUTO_G=AUTO_G, AUTO_PS=AUTO_PS, AUTO_PAUSA=AUTO_PAUSA, AUTO_PAUSA_POS=AUTO_PAUSA_POS, ACEL_POS=ACEL_POS, S2_FRENO=S2_FRENO, INC_ACTIVO=INC_ACTIVO, INC_DUR=INC_DUR, INC_ENTRA=INC_ENTRA, INC_SUBE=INC_SUBE, INC_BPM=INC_BPM, BREAK_ACTIVO=BREAK_ACTIVO, BREAK_VENTANA=BREAK_VENTANA, BREAK_NIVEL=BREAK_NIVEL, BREAK_COMPASES=BREAK_COMPASES, PAUSA=PAUSA, PAUSA_POS=PAUSA_POS, MIN_DUR=MIN_DUR, DUR_IDEAL=DUR_IDEAL, MAX_DUR=MAX_DUR, ENT_MIN=ENT_MIN, ENT_MAX=ENT_MAX,
            ZONA_K=ZONA_K, ZONA_MIN=ZONA_MIN, ZONA_ACEL=ZONA_ACEL, ZONA_V=ZONA_V, RB_MIN=RB_MIN, ESTRATEGIA=ESTRATEGIA, PRO_COMPASES=PRO_COMPASES, MAN_COMPASES=MAN_COMPASES, ESPERA_FRASE=ESPERA_FRASE, PAUSA_EN_LINEA=PAUSA_EN_LINEA, ADAPTA_DUR=ADAPTA_DUR).items()}


def aplicar(valores):
    """Cambia los tiempos y el ritmo del cruce (los del engranaje ⚙). `valores` = dict nombre → número (los que falten no cambian)."""
    g = globals()
    for k, v in (valores or {}).items():
        if k in DEFECTOS:
            g[k] = float(v)
    _MAPAS.clear()
    if g["ENT_MAX"] < g["ENT_MIN"]:
        g["ENT_MAX"] = g["ENT_MIN"]
    if g["MAX_DUR"] < g["MIN_DUR"]:
        g["MAX_DUR"] = g["MIN_DUR"]


def detectar_breaks(an):
    """Breaks de un tema: lista de (segundo de inicio, segundo de fin) de los tramos en que la energía cae (varios compases seguidos por
    debajo de BREAK_NIVEL × la energía normal del tema). Usa la forma de onda del análisis y la grilla de compases; [] si no hay grilla."""
    try:
        wf = np.asarray(an.get("waveform") or [], dtype=np.float64)
        dur = float(an.get("duration") or 0)
        db = np.asarray(an.get("downbeats_full") or an.get("downbeats") or [], dtype=np.float64)
        if len(wf) < 200 or dur <= 0 or len(db) < 16:
            return []
        paso = dur / len(wf)
        idx = np.clip((db / paso).astype(int), 0, len(wf))
        r = np.array([wf[a:b].mean() if b > a else np.nan for a, b in zip(idx[:-1], idx[1:])])     # energía de cada compás
        ok = ~np.isnan(r)
        if int(ok.sum()) < 8:
            return []
        ref = float(np.percentile(r[ok], 70))                  # la energía "normal" del tema (el tramo pleno, no el promedio con los huecos)
        if ref <= 1e-9:
            return []
        bajo = ok & (r < BREAK_NIVEL * ref)
        n_min = max(1, int(round(BREAK_COMPASES)))
        out, i, n = [], 0, len(bajo)
        while i < n:
            if bajo[i]:
                j = i
                while j + 1 < n and bajo[j + 1]:
                    j += 1
                if j - i + 1 >= n_min:
                    out.append((float(db[i]), float(db[j + 1])))
                i = j + 1
            else:
                i += 1
        return out
    except Exception:
        return []


def valores():
    g = globals()
    return {k: g[k] for k in DEFECTOS}


_CTX = [False]           # True mientras se trabaja con el cruce AUTO «como mi manual» (su pausa, su ritmo); False = el manual (y las demás estrategias)


class contexto:
    """with contexto(True): ... → pausa y ritmo del Auto «como mi manual»; with contexto(False): ... → los del cruce manual. Se puede anidar."""
    def __init__(self, auto=True):
        self.auto = bool(auto)
    def __enter__(self):
        self._ant = _CTX[0]; _CTX[0] = self.auto
        return self
    def __exit__(self, *exc):
        _CTX[0] = self._ant
        return False


def en_auto():
    """¿Se está trabajando con el Auto «como mi manual» (estrategia 2)?"""
    return bool(_CTX[0]) and ESTRATEGIA >= 1.5


def pausa_s():
    """Pausa (s): la del Auto «como mi manual» si el contexto es ese; si no, la del cruce manual."""
    return float(AUTO_PAUSA) if en_auto() else float(PAUSA)


def hay_pausa(auto=None):
    a = en_auto() if auto is None else (bool(auto) and ESTRATEGIA >= 1.5)
    return (AUTO_PAUSA if a else PAUSA) >= 0.1
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


_MAPAS = {}


def _mapa(pc, pb=None):
    """Tabla (fracción de tiempo → posición) de la primera mitad: frena desde pb (empieza la rampa de B) hasta el cruce pc y
    acelera de nuevo hasta el 50 %."""
    k = (round(float(pc), 3), None if pb is None else round(float(pb), 3), round(float(ZONA_K), 3), round(float(ZONA_V), 3), round(float(ZONA_MIN), 3), round(float(ZONA_ACEL), 3))
    m = _MAPAS.get(k)
    if m is None:
        pcr = k[0]
        wa = max(ZONA_MIN, pcr - k[1]) if k[1] is not None else 0.10     # tramo de frenada antes del cruce
        wd = max(wa, (0.5 - pcr) * ZONA_ACEL)                                        # después del cruce la aceleración se extiende hasta el 50 %
        p = np.linspace(0.0, 0.5, 1001)
        d = p - pcr
        x = np.where(d < 0, d / wa, d / wd)
        bump = np.where(np.abs(x) < 1.0, 0.5 * (1.0 + np.cos(np.pi * np.clip(x, -1.0, 1.0))), 0.0)
        # El frenado no puede ser tan profundo que lo de afuera (el arranque hasta el frenado) pase de golpe: la velocidad de afuera
        # (= lentitud media de la primera mitad) se topa en ZONA_V veces la media. Así el arranque lleva un tiempo proporcional a su
        # recorrido y los deslizadores de entrada/salida (B entra, A sale…) se notan, en vez de quedar 'pasados' en 0,2 s.
        mb = max(1e-6, float(np.trapezoid(bump, p)) / 0.5)
        kef = min(ZONA_K, max(0.0, (ZONA_V - 1.0) / mb))
        sl = 1.0 + kef * bump                                      # lentitud: tiempo que lleva cada tramo de posición
        S = np.concatenate(([0.0], np.cumsum(0.5 * (sl[1:] + sl[:-1]) * np.diff(p))))
        F = 0.5 * S / S[-1]
        if len(_MAPAS) > 400:
            _MAPAS.clear()
        m = _MAPAS[k] = (F, p)
    return m


_MAPAS2 = {}


def _estrategia2():
    return en_auto()


def _mapa2(pc):
    """Estrategia 2 — tabla (fracción del tiempo de movimiento → posición del crossfader) en tres tramos:
    1) desde el inicio ACELERA (de START_V a la velocidad máxima) hasta la marca roja (ACEL_POS, o el cruce de las dos curvas si es 0);
    2) FRENA hasta la posición de la pausa (la velocidad baja a 1/S2_FRENO de la máxima);
    3) tras la pausa vuelve a acelerar de a poco (rampa) y llega al final justo en el tiempo estipulado."""
    q = pausa_pos()
    r = float(ACEL_POS) if ACEL_POS > 0 else (float(pc) if pc is not None else 0.3)
    r = min(max(r, 0.05), q - 0.03)
    fr = max(1.0, float(S2_FRENO)); v0 = min(1.0, max(0.05, float(START_V)))
    k = (round(r, 3), round(q, 3), round(fr, 2), round(v0, 2))
    m = _MAPAS2.get(k)
    if m is None:
        p = np.linspace(0.0, 1.0, 2001)
        v = np.interp(p, [0.0, r, q, 1.0], [v0, 1.0, 1.0 / fr, 1.0])           # velocidad en cada posición (lineal entre marcas)
        dt = np.diff(p) * 0.5 * (1.0 / v[1:] + 1.0 / v[:-1])
        S = np.concatenate(([0.0], np.cumsum(dt)))
        if len(_MAPAS2) > 400:
            _MAPAS2.clear()
        m = _MAPAS2[k] = (S / S[-1], p)
    return m


def pos_cruce(f, pc=None, pb=None):
    """Posición del crossfader (0..1) cuando ya pasó la fracción f (0..1) de la duración del fundido (sin contar la pausa).
    La primera mitad avanza parejo hasta que empieza a subir B (pb); desde ahí va frenando hasta moverse muy suavecito en el cruce
    de las dos líneas (pc), sale igual de lento y después acelera de a poco hasta llegar al 50 %, caiga donde caiga el cruce.
    La segunda mitad es pareja ('la rampa normal'). Sin pc todo es parejo."""
    f = min(1.0, max(0.0, f))
    if _estrategia2():
        F, p = _mapa2(pc)
        return float(np.interp(f, F, p))
    if f > 0.5 or pc is None:
        return f
    F, p = _mapa(pc, pb)
    return float(np.interp(f, F, p))


def punto_cruce_simple(pa, pb):
    """Lo mismo para el cruce simple (sin bandas): posición donde se cruzan las dos curvas, o None si no se cruzan."""
    for i in range(0, 1001):
        t = i / 1000.0
        h, e = perfil_cruce_ab(t, pa, pb)
        if e >= h and t > 0.0:
            return t
    return None


def punto_cruce(pa, fa, pb, rb, gamma):
    """Posición del crossfader donde se cruzan las dos líneas (sale y entra a igual nivel en medios/agudos)."""
    ant = None
    for i in range(0, 401):
        t = pb + rb * i / 400.0
        h, e, _l1, _l2 = perfil_cruce_bandas(t, pa, pb, 0.5, rampa=rb, fin_a=fa, gamma_a=gamma)
        if e >= h:
            return float(t)
    return float(pb + rb)


def pausa_pos():
    """Posición del crossfader (0..1) donde se queda la pausa, siempre entre 0.25 y 0.75 (0.5 = en el medio)."""
    return min(0.75, max(0.25, float(AUTO_PAUSA_POS if en_auto() else PAUSA_POS)))


def zona_auto():
    """(cruce de las dos líneas, inicio de la rampa de B) con la forma PROPIA del Auto; None si no se cruzan en el tramo útil."""
    try:
        fa = None if AUTO_FA >= 0.995 else float(AUTO_FA)
        pb = float(AUTO_PB)
        pc = punto_cruce(float(AUTO_PA), fa, pb, max(0.02, min(float(AUTO_RB), 1.0 - pb)), float(AUTO_G))
    except Exception:
        return None
    return (pc, pb) if 0.0 < pc <= 0.75 else None


def forma_auto(dur):
    """La forma que usa el Auto «como mi manual» (la de su panel en ⚙ Ajustes, no la de los deslizadores del manual)."""
    f = {"pa": float(AUTO_PA), "pb": float(AUTO_PB), "rb": float(AUTO_RB), "ps": float(AUTO_PS), "gamma": float(AUTO_G),
         "fa": (None if AUTO_FA >= 0.995 else float(AUTO_FA)), "dur": float(dur)}
    z = zona_auto()
    if z:
        f["pc"], f["zpb"] = z
    return f


def frac_pausa(pc=None, pb=None):
    """Fracción de la duración del fundido (sin contar la pausa) a la que el crossfader llega a la posición de la pausa.
    Hasta el 50 % el crossfader frena y acelera (ver `pos_cruce`); pasado el 50 % va parejo."""
    q = pausa_pos()
    if _estrategia2():
        F, p = _mapa2(pc)
        return float(np.interp(q, p, F))
    if q >= 0.5 or pc is None:
        return q
    F, p = _mapa(pc, pb)
    return float(np.interp(q, p, F))


def _t_de_T(T, D, pausa, pc=None, pb=None):
    """Posición del crossfader (0..1) a los T segundos de empezar, contando la pausa (por defecto 3 s al 50 %)."""
    if not pausa:
        return pos_cruce(T / D, pc, pb)
    m = frac_pausa(pc, pb) * D
    if T <= m:
        return pos_cruce(T / D, pc, pb)
    if T <= m + pausa_s():
        return pausa_pos()
    return pos_cruce((T - pausa_s()) / D, pc, pb)


def _forma1(D, pausa, compas, S, E, vs, ve, be, zona):
    """Diseña las rampas para un fundido de D segundos (+ la pausa). Devuelve el dict con los parámetros y su explicación."""
    total = D + (pausa_s() if pausa else 0.0)
    zpc, zpb = zona if zona else (None, None)
    n = min(len(vs), int(total / PASO) + 1)
    vs, ve, be = vs[:n], ve[:n], be[:n]
    fs, fe = vs >= UMBRAL_VOZ, ve >= UMBRAL_VOZ
    juntos = fs & fe
    conflicto = float(juntos.mean()) if n else 0.0                         # fracción de la mezcla con voz en los dos
    m_ini = max(1, int(0.4 * n))
    choque_ini = float(juntos[:m_ini].mean())                              # y lo mismo en el tramo en que entra B

    # --- entrada de B: siempre al principio, en una línea de compás de B ---
    ent = ENT_MIN + (ENT_MAX - ENT_MIN) * min(1.0, 2.5 * choque_ini)       # (por defecto 5 %..20 % del tiempo de la mezcla)
    tb = ent * D
    T_e, _ = _compases_en(E.get("db"), E["pos"], E["rate"], max(0.22, ENT_MAX + 0.03) * D)
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
        fa = max(0.65, min(1.0, _t_de_T(fin_s + compas, D, pausa, zpc, zpb)))
    pb = _t_de_T(tb, D, pausa, zpc, zpb)                                              # (la posición va a otro ritmo que el tiempo: se frena en el cruce)
    rb = max(0.01, _t_de_T(tb + rb_t, D, pausa, zpc, zpb) - pb)
    rb = min(max(rb, RB_MIN), max(0.01, 0.5 - pb))                          # el crossfader avanza de 1 % en 1 %: B sube en al menos ~8 pasos

    # --- bajo: una línea de compás del que sale, de preferencia en la pausa del medio y al inicio de una frase ---
    T_s, idx_s = _compases_en(S.get("db"), S["pos"], S["rate"], total)
    p0 = frac_pausa(zpc, zpb) * D
    p1 = p0 + (pausa_s() if pausa else 0.0)
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
        ps = pausa_pos()
    elif mejor[2]:
        ps = pausa_pos()                                                   # se pide al empezar la pausa; cae en la 1.ª línea
    else:
        T = mejor[1] - 0.4 * compas                                        # se pide antes de la línea (el mezclador espera a la línea)
        t = _t_de_T(T, D, pausa, zpc, zpb)
        ps = math.floor(max(0.05, min(0.95, t)) * 100.0) / 100.0           # el crossfader avanza de 1 % en 1 %
    return {"pa": float(pa), "fa": float(fa), "pb": float(pb), "rb": float(rb), "ps": float(ps), "gamma": float(gamma),
            "conflicto": conflicto, "choque_ini": choque_ini, "fin_voz_a": fin_s}


def _forma(D, pausa, compas, S, E, vs, ve, be):
    """Diseña el fundido y ajusta el frenado a la rampa de B y al cruce de las dos líneas (el cruce depende de la forma y la forma
    depende del ritmo: se repite hasta que coinciden)."""
    zona = None
    for _ in range(6):
        p = _forma1(D, pausa, compas, S, E, vs, ve, be, zona)
        nuevo = (punto_cruce(p["pa"], p["fa"], p["pb"], p["rb"], p["gamma"]), p["pb"])
        if zona is not None and abs(nuevo[0] - zona[0]) < 0.004 and abs(nuevo[1] - zona[1]) < 0.004:
            break
        zona = nuevo
    p["pc"], p["zpb"] = float(zona[0]), float(zona[1])                     # con lo que se calculó todo (el mezclador usa lo mismo)
    return p


def _coste(p, D, pausa, vs, ve, compat_fac):
    """Cuánto 'choca' la mezcla: segundos con voz de los dos sonando juntas (+ un poco del tiempo en que suenan los dos
    si las tonalidades o los tempos chocan). La pausa del medio se cuenta (los dos siguen sonando 3 s con el mismo nivel)."""
    clash = 0.0
    juntos = 0.0
    for i in range(len(vs)):
        t = _t_de_T(i * PASO, D, pausa, p.get("pc"), p.get("zpb"))
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


def _n_pro(compas, resta):
    """Compases de la mezcla Pro: el pedido (4, 8, 16 o 32) y, si no cabe en lo que le queda al que sale, el siguiente más corto."""
    pref = min((4, 8, 16, 32), key=lambda c: abs(math.log2(c) - math.log2(max(2.0, PRO_COMPASES))))
    for n in (32, 16, 8, 4, 2):
        if n > pref:
            continue
        if resta is None or n * compas + 1.0 <= resta - 1.0:
            return n, n * compas
    if resta is None or resta - 1.5 < 2.0:
        return 0, max(1.5, (resta or 4.0) - 1.5)
    return 0, resta - 1.5


def disenar_pro(sale, entra, compat=None, dif_tempo=0.0, forma=None):
    """ESTRATEGIA PRO — la mezcla larga "en frase" de los DJs, sin pausa ni frenado (el crossfader avanza parejo):
      · dura 8, 16 o 32 compases (por defecto 16 = una frase doble),
      · B entra SIN graves (el bajo es de uno solo) y va subiendo de a poco en la primera mitad,
      · a la mitad, en una línea de compás de A (de preferencia inicio de frase), el bajo pasa de A a B de un solo movimiento,
      · recién entonces A se va (medios y agudos), hasta quedar en cero justo al final.
    La FORMA (cuándo entra B, cuánto tarda en subir, cuándo se va A, dónde se cambia el bajo) es la de los deslizadores de
    "Forma de cruce A/B" (`forma`), así lo que se afina a mano vale también en el Auto; sin `forma` se usa un diseño propio
    (si los dos tienen voz casi todo el cruce, B sube más tarde y A empieza a irse antes, para que las voces no se pisen)."""
    bpm = float(sale.get("bpm", 0) or 0) * float(sale.get("rate", 1.0) or 1.0)
    compas = 240.0 / bpm if bpm > 20 else 2.0
    n, D = _n_pro(compas, sale.get("resta"))
    vs, _ = _serie(sale.get("voz"), sale.get("dt", 0.5), sale["pos"], sale["rate"], D)
    ve, _ = _serie(entra.get("voz"), entra.get("dt", 0.5), entra["pos"], entra["rate"], D)
    k = max(1, int(D / PASO) + 1)
    conflicto = float(((vs[:k] >= UMBRAL_VOZ) & (ve[:k] >= UMBRAL_VOZ)).mean())
    if forma:
        pb, rb, pa = float(forma["pb"]), float(forma["rb"]), float(forma["pa"])
        fa, gamma = float(forma.get("fa") or 1.0), float(forma.get("gamma") or 1.0)
        pb = max(0.0, min(0.9, pb)); rb = max(0.02, min(rb, 1.0 - pb))
        pa = max(0.0, min(0.9, pa)); fa = max(pa + 0.05, min(1.0, fa))
        ps_obj = max(0.3, min(0.7, float(forma.get("ps", 0.5))))
    else:
        ps_obj = 0.5
        if conflicto > 0.5:
            pb, rb, pa, fa, gamma = 0.25, 0.25, 0.35, 0.92, 1.5
        elif conflicto > 0.15:
            pb, rb, pa, fa, gamma = 0.18, 0.32, 0.42, 0.96, 1.2
        else:
            pb, rb, pa, fa, gamma = 0.12, 0.38, 0.50, 1.0, 1.0
    # cambio de bajo: la línea de compás de A más cercana a la mitad (con preferencia por el inicio de frase)
    T_s, idx_s = _compases_en(sale.get("db"), sale["pos"], sale["rate"], D)
    mejor = None
    for T, i in zip(T_s, idx_s):
        T = float(T)
        if not (ps_obj - 0.15) * D <= T <= (ps_obj + 0.15) * D:
            continue
        c = abs(T - ps_obj * D) / D - (0.04 if i % 8 == 0 else 0.0)
        if mejor is None or c < mejor[0]:
            mejor = (c, T)
    if mejor is None:
        ps = ps_obj
    else:
        t = (mejor[1] - 0.4 * compas) / D                             # se pide antes de la línea (el mezclador espera a la línea)
        ps = math.floor(max(0.05, min(0.95, t)) * 100.0) / 100.0      # el crossfader avanza de 1 % en 1 %
    razon = ("con la forma de tus deslizadores (Forma de cruce A/B)" if forma else
             "los dos tienen voz casi todo el cruce: B entra más tarde y A se va antes" if conflicto > 0.5 else
             "las voces se pisan en parte: A baja un poco antes" if conflicto > 0.15 else "sin choque de voces: blend largo parejo")
    if compat == 0 or dif_tempo > 0.08:
        razon += " · tonalidad/tempo chocan (para mezclas más cortas bajá 'Compases de la mezcla Pro' en ⚙)"
    return {"pa": float(pa), "fa": float(fa), "pb": float(pb), "rb": float(rb), "ps": float(ps), "gamma": float(gamma),
            "conflicto": conflicto, "choque_ini": 0.0, "fin_voz_a": None, "pc": None, "zpb": None,
            "dur": float(D), "pausa": False, "n": int(n), "estrategia": "pro",
            "nombre": (f"Pro · {n} compases · {D:.0f} s" if n else f"Pro · mezcla corta · {D:.0f} s") + " · sin pausa",
            "razon": razon}


def disenar_manual(sale, entra, compat=None, dif_tempo=0.0, forma=None):
    """ESTRATEGIA 2 — el Auto mezcla EXACTAMENTE como el cruce manual que ya te gusta: la forma de los deslizadores de
    "Forma de cruce A/B", la duración del deslizador «Duración», la pausa del 50 % y el frenado en el cruce de los ajustes de ⚙.
    La duración va en compases enteros: MAN_COMPASES (por defecto 8; a 96 BPM ≈ 20 s, a 136 BPM ≈ 14 s) o, con 0, los segundos de «Duración»
    redondeados a compases. El Auto la acorta si al
    tema que sale no le queda tiempo. El traspaso del bajo lo hace el mezclador en la línea de compás, igual que en el manual."""
    bpm = float(sale.get("bpm", 0) or 0) * float(sale.get("rate", 1.0) or 1.0)
    compas = 240.0 / bpm if bpm > 20 else 2.0
    resta = sale.get("resta")
    dur = float(forma.get("dur") or 10.0)
    pausa = hay_pausa()
    n = max(2, int(round(MAN_COMPASES))) if MAN_COMPASES >= 1 else max(2, int(round(dur / compas)))
    n = min(n, max(2, int(MAX_SEG_MANUAL // compas)))               # tope: el cruce nunca pasa de 30 s
    choque = (compat == 0) or dif_tempo > 0.08
    if choque and ADAPTA_DUR >= 0.5:                              # tonalidad o tempo que chocan: se pasa más rápido de un tema al otro
        n = max(4, int(round(n * 0.75)))
    total = n * compas                                            # el tiempo estipulado INCLUYE la pausa
    pa_s = pausa_s() if pausa else 0.0
    while resta is not None and n > 2 and total > resta - 1.0:
        n -= 1; total = n * compas
    if resta is not None and total > resta - 1.0:                  # no entra ni con 2 compases: lo que quede, sin pausa
        n, total, pausa, pa_s = 0, max(1.5, resta - 1.5), False, 0.0
    D = max(2.0, total - pa_s)                                     # lo que recorre el crossfader: el total menos lo que se queda quieto
    pb = max(0.0, min(0.9, float(forma["pb"]))); rb = max(0.02, min(float(forma["rb"]), 1.0 - pb))
    pa = max(0.0, min(0.9, float(forma["pa"]))); fa = max(pa + 0.05, min(1.0, float(forma.get("fa") or 1.0)))
    gamma = float(forma.get("gamma") or 1.0)
    ps = max(0.0, min(0.97, float(forma.get("ps", 0.5))))
    pc, zpb = forma.get("pc"), forma.get("zpb")
    razon = "como tu cruce manual (tu forma, tu duración, la pausa y el frenado)"
    if choque:
        razon += " · tonalidad/tempo chocan" + (": fundido más corto" if ADAPTA_DUR >= 0.5 else "")
    return {"pa": float(pa), "fa": float(fa), "pb": float(pb), "rb": float(rb), "ps": float(ps), "gamma": float(gamma),
            "conflicto": 0.0, "choque_ini": 0.0, "fin_voz_a": None,
            "pc": None if pc is None else float(pc), "zpb": None if zpb is None else float(zpb),
            "dur": float(D), "pausa": bool(pausa), "pausa_s": float(pa_s), "n": int(n), "estrategia": "manual",
            "nombre": (f"Como el manual · {n} compases · {D + pa_s:.0f} s" if n else f"Como el manual · corta · {D:.0f} s") + (f" (con pausa de {pausa_s():g} s)" if pausa else ""),
            "razon": razon}


def disenar(sale, entra, compat=None, dif_tempo=0.0, forma=None):
    """Diseña el cruce de este par de temas.
    sale / entra: dict(voz, bajo, dt, pos, rate, bpm, db, resta)  · pos en s del tema, rate = velocidad real,
                  db = líneas de compás (s del tema), resta = segundos de música que le quedan.
    compat: 0/1/2 (armonía) o None · dif_tempo: diferencia relativa de BPM.
    Devuelve dict(dur, pausa, n, pa, fa, pb, rb, ps, gamma, nombre, razon).
    `dur` es el fundido (lo que recorre el crossfader); si `pausa` es True se le suman 3 s al 50 %."""
    if ESTRATEGIA >= 1.5 and forma and forma.get("dur"):
        with contexto(True):                                      # el Auto «como mi manual» usa su propia pausa y su propio ritmo
            return disenar_manual(sale, entra, compat, dif_tempo, forma)
    if ESTRATEGIA >= 0.5:
        return disenar_pro(sale, entra, compat, dif_tempo, forma)
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
        cands.append((n, D, hay_pausa()))
    if not cands:                                             # le queda poco al que sale: lo más largo que entre
        if resta is None:
            cands = [(0, MIN_DUR, hay_pausa())]
        elif resta - 4.0 >= 5.0:
            cands = [(0, min(MIN_DUR, resta - 4.0), hay_pausa())]
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
    p["nombre"] = base + (f" + pausa {PAUSA:g} s" if pausa else "")
    return p
