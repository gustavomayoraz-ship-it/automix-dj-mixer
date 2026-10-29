"""AutoMix — el Auto aprende de tus votos (👍 / 👎) después de cada mezcla.
Guarda cada voto con las características del par de temas (armonía, diferencia de tempo, choque de voces) y, para los pares parecidos,
corre un poco la duración (en compases) hacia lo que te gustó. Todo queda en un archivo de texto de la carpeta cache: se puede borrar."""
import json
import time
from setup.config import CACHE_DIR

ARCHIVO = CACHE_DIR / "valoraciones_cruce.json"
MAX_ENTRADAS = 400                 # se guardan las últimas
MIN_PARA_APRENDER = 2              # con menos votos parecidos no se corre nada
MAX_SESGO = 3                      # como mucho ±3 compases
MOTIVOS = {"corto": "Fue muy corto", "largo": "Fue muy largo", "voces": "Chocaron las voces", "bajo": "El bajo se notó", "otro": "Otra cosa"}


def clave_par(compat, dif_tempo, voces):
    """Grupo de pares parecidos: armonía (0 chocan · 1 vecinas · 2 compatibles), tempo (parejo / algo distinto / muy distinto) y voces juntas (pocas / muchas)."""
    c = "?" if compat is None else str(int(compat))
    d = float(dif_tempo or 0.0)
    t = "p" if d < 0.03 else ("m" if d < 0.08 else "g")
    v = "-" if voces is None else ("v" if voces >= 0.25 else "s")
    return f"{c}{t}{v}"


def _leer():
    try:
        d = json.loads(ARCHIVO.read_text(encoding="utf-8"))
        return d if isinstance(d, list) else []
    except (OSError, ValueError):
        return []


def registrar(plan, voto, motivo=None):
    """Guarda el voto (+1 / -1) del último cruce Auto. Devuelve True si se guardó."""
    if not plan or plan.get("estrategia") != "manual" or "clave_par" not in plan:
        return False
    delta = int(plan.get("n", 0)) - int(plan.get("n_base", plan.get("n", 0)))       # cuántos compases se apartó de la plantilla
    if voto > 0:
        deseado = delta                                                              # le gustó: se queda por ahí
    elif motivo == "corto":
        deseado = delta + 1
    elif motivo in ("largo", "voces"):
        deseado = delta - 1
    else:
        deseado = None                                                               # (bajo / otra cosa: se anota pero no mueve la duración)
    entradas = _leer()
    entradas.append({"t": int(time.time()), "par": plan["clave_par"], "n": int(plan.get("n", 0)), "n_base": int(plan.get("n_base", 0)),
                     "voto": int(voto), "motivo": motivo, "deseado": deseado, "ps": plan.get("ps")})
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        ARCHIVO.write_text(json.dumps(entradas[-MAX_ENTRADAS:]), encoding="utf-8")
        return True
    except OSError:
        return False


def sesgo_compases(par):
    """Cuántos compases correr la plantilla para este tipo de par (promedio de lo que te gustó, los más recientes pesan más)."""
    util = [e for e in _leer() if e.get("par") == par and e.get("deseado") is not None][-20:]
    if len(util) < MIN_PARA_APRENDER:
        return 0
    pesos = [1.0 + i / max(1, len(util)) for i in range(len(util))]
    media = sum(p * e["deseado"] for p, e in zip(pesos, util)) / sum(pesos)
    return int(max(-MAX_SESGO, min(MAX_SESGO, round(media))))


def resumen():
    e = _leer()
    return f"{len(e)} votos guardados ({sum(1 for x in e if x.get('voto', 0) > 0)} 👍 · {sum(1 for x in e if x.get('voto', 0) < 0)} 👎)"


def olvidar():
    try:
        ARCHIVO.unlink()
    except OSError:
        pass
