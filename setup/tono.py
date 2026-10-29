"""AutoMix — ajuste de tonalidad de ±1 semitono del tema que entra (rueda de Camelot)."""
from setup.analisis import _camelot_tuple, compat_armonica

CONF_MIN = 0.03          # confianza mínima de la tonalidad detectada (diferencia entre las dos mejores) para fiarse de ella


def desplazar(camelot, semitonos):
    """Clave Camelot que tendría el tema si se sube `semitonos` (negativo = baja). Un semitono = 7 pasos en la rueda, mismo modo."""
    t = _camelot_tuple(camelot) if camelot else None
    if not t:
        return None
    num = ((t[0] - 1 + 7 * int(semitonos)) % 12) + 1
    return f"{num}{t[1]}"


def mejor_desplazamiento(c_sale, c_entra, max_s=1):
    """Si las claves chocan (compat 0), ¿qué desplazamiento del que entra (hasta ±max_s semitonos) las hace compatibles?
    Devuelve (semitonos, compat_nueva, clave_nueva); (0, compat_actual, c_entra) si no hace falta o no sirve."""
    c0 = compat_armonica(c_sale, c_entra)
    if c0 != 0:
        return 0, c0, c_entra
    mejor = (0, c0, c_entra)
    for s in range(1, int(max_s) + 1):
        for sg in (1, -1):
            k = desplazar(c_entra, sg * s)
            c = compat_armonica(c_sale, k)
            if c is not None and c > mejor[1]:
                mejor = (sg * s, c, k)
        if mejor[1] == 2:
            break
    return mejor
