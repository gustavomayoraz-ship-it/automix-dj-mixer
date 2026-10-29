"""AutoMix — estructura de un tema (intro, primera sección fuerte) a partir de lo que ya guarda el análisis: curvas de voz y de energía y la grilla de compases.
No vuelve a analizar el audio: trabaja por frases (cada 8 compases desde el primer compás, igual que el resto del programa)."""
import numpy as np

FRASE = 8                    # compases por frase
UMBRAL_VOZ_FRASE = 0.30      # voz promedio de una frase a partir de la cual cuenta como «ya canta»
SUBE_ENERGIA = 1.30          # una frase con esta energía respecto del promedio de las anteriores cuenta como «entra la sección fuerte»
MAX_FRASES_BUSCA = 24        # hasta qué frase se busca la primera sección fuerte


def _media_por_frase(valores, dt, inicios, fin_total):
    """Promedio de una curva del análisis (un valor cada `dt` s) dentro de cada frase [inicios[j], inicios[j+1])."""
    arr = np.asarray(valores, dtype=np.float64)
    if arr.size == 0 or dt <= 0:
        return None
    out = []
    for j in range(len(inicios)):
        a = inicios[j]; b = inicios[j + 1] if j + 1 < len(inicios) else fin_total
        k0 = max(0, int(a / dt)); k1 = min(arr.size, max(k0 + 1, int(b / dt)))
        out.append(float(arr[k0:k1].mean()) if k1 > k0 else 0.0)
    return np.asarray(out)


def primera_seccion_fuerte(analisis, downbeats):
    """(índice de frase, segundo del tema) donde entra la primera sección fuerte (empieza la voz o sube la energía); None si no se puede saber
    o si el tema ya arranca fuerte (no hay intro que saltear)."""
    db = np.asarray(downbeats, dtype=np.float64)
    if len(db) < FRASE * 3:
        return None
    inicios = db[::FRASE]
    dur = float(analisis.get("duration", 0.0)) or float(db[-1])
    voz = _media_por_frase(analisis.get("voz") or [], float(analisis.get("voz_dt", 0.5) or 0.5), inicios, dur)
    wf = analisis.get("waveform") or []
    ene = _media_por_frase(wf, dur / max(1, len(wf)), inicios, dur) if wf else None
    if voz is None and ene is None:
        return None
    if voz is not None and voz[0] >= UMBRAL_VOZ_FRASE:
        return None                                              # canta desde el principio: no hay intro
    for j in range(1, min(len(inicios) - 1, MAX_FRASES_BUSCA)):
        canta = voz is not None and voz[j] >= UMBRAL_VOZ_FRASE
        sube = ene is not None and ene[:j].mean() > 1e-6 and ene[j] >= SUBE_ENERGIA * ene[:j].mean()
        if canta or sube:
            return j, float(inicios[j])
    return None


def entrada_alineada(analisis, downbeats, T_real, rate):
    """Dónde hacer arrancar al tema que entra para que su primera sección fuerte caiga justo cuando termina el cruce.
    T_real = duración del cruce en segundos reales (con la pausa) · rate = velocidad con que va a sonar.
    Devuelve (segundo del tema donde arrancar, número de frases salteadas, segundo de la sección fuerte) o None si conviene arrancar de siempre."""
    r = primera_seccion_fuerte(analisis, downbeats)
    if r is None:
        return None
    j_fb, t_fb = r
    db = np.asarray(downbeats, dtype=np.float64)
    inicios = db[::FRASE]
    frase_s = float(np.median(np.diff(inicios))) if len(inicios) > 2 else 0.0
    if frase_s <= 0:
        return None
    m = int(round(T_real * max(0.3, float(rate)) / frase_s))      # cuántas frases del tema entran en el cruce
    k = j_fb - max(1, m)
    if k <= 0:
        return None                                                # la intro es más corta que el cruce: se arranca de siempre
    return float(inicios[k]), int(k), float(t_fb)
