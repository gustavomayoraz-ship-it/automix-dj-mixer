"""AutoMix — constantes y ajustes generales de la interfaz."""


# =====================================================================
# 2) UTILIDADES Y ANÁLISIS
# =====================================================================
class _Ajustes:
    escala = 1.0          # escala actual de la interfaz (la cambia la ventana al redimensionarse)


AJ = _Ajustes()


ESC_MIN = 0.6         # escala más chica de la interfaz = ventana más chica posible (en pantallas normales)


ESC_PISO = 0.3        # en pantallas chicas (ej. 1366x768) la escala mínima baja sola hasta acá para que la ventana entre


ESC_COMPACTO = 0.55   # si para entrar en la pantalla hace falta una escala menor, se pasa al modo compacto (sin la tabla de bandas)


ESC_MIN_COMPACTO = 0.55  # en modo compacto la ventana mínima es más chica todavía (sin la tabla de bandas se puede bajar sin cortar controles); subilo para agrandarla


ANCHO_LISTA = 420     # ancho de la lista de temas (a escala 1.0): chico y fijo; al maximizar, el espacio que sobra va al resto


PANEL_CRUCE_MIN_W = 230   # el panel "Forma de cruce A/B" nunca baja de este ancho (a escala menor se cortaban sus controles)
PANEL_CRUCE_MAX_W = 300


FUENTE_BOOST = 1.3     # multiplicador SOLO de las letras (1.0 = tamaño original); subilo/bajalo a gusto


SUPPORTED = (".mp3", ".wav", ".flac", ".ogg", ".m4a")



CF_BAJA_DESDE = 0.75


TARGET_LUFS_RMS = 0.15


NIVEL_V2 = 1.35          # V2: más fuerza general (+2,6 dB) sobre el AutoGain; el limitador por ganancia cuida los picos




def fmt_time(s):
    m, sec = divmod(int(s), 60)
    return f"{m:02d}:{sec:02d}"
