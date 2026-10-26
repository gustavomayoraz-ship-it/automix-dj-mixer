"""AutoMix — historial de temas dañados (archivos que no se pueden cargar o analizar). Se guarda en cache/temas_danados.json."""
import json
import os
import time
from pathlib import Path
from setup.base import CACHE_DIR, log

ARCHIVO = CACHE_DIR / "temas_danados.json"


def _clave(ruta):
    return os.path.normcase(os.path.abspath(ruta))


class HistorialDanados:
    """Lista persistente de temas dañados: clave (ruta normalizada) -> {ruta, nombre, motivo, fecha, veces, tam}."""

    def __init__(self):
        self.datos = {}
        self._leer()

    def _leer(self):
        try:
            with open(ARCHIVO, encoding="utf-8") as f:
                d = json.load(f)
        except FileNotFoundError:
            return
        except (OSError, ValueError) as e:
            log("dañados", f"no se pudo leer el historial: {e}")
            return
        if not isinstance(d, dict):
            return
        for k, v in d.items():
            if not isinstance(v, dict) or not v.get("ruta"):
                continue
            try:                                          # si el archivo cambió de tamaño (lo reemplazaron o lo arreglaron), ya no se lo da por dañado
                if v.get("tam") is not None and os.path.getsize(v["ruta"]) != v["tam"]:
                    continue
            except OSError:
                pass                                      # no existe ahora (disco desconectado, etc.): se conserva en el historial
            self.datos[k] = v

    def _guardar(self):
        tmp = ARCHIVO.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.datos, f, ensure_ascii=False, indent=1)
            os.replace(tmp, ARCHIVO)
        except OSError as e:
            log("dañados", f"no se pudo guardar el historial: {e}")

    def claves(self):
        return set(self.datos)

    def registrar(self, ruta, motivo):
        """Anota un tema dañado (o suma una vez más si ya estaba). Devuelve su clave."""
        k = _clave(ruta)
        try:
            tam = os.path.getsize(ruta)
        except OSError:
            tam = None
        prev = self.datos.get(k, {})
        self.datos[k] = {"ruta": str(ruta), "nombre": os.path.basename(str(ruta)), "motivo": str(motivo)[:200],
                         "fecha": time.strftime("%d/%m/%Y %H:%M"), "veces": int(prev.get("veces", 0)) + 1, "tam": tam}
        self._guardar()
        return k

    def quitar(self, claves):
        for k in claves:
            self.datos.pop(k, None)
        self._guardar()

    def vaciar(self):
        self.datos.clear()
        self._guardar()

    def lista(self):
        """Los más recientes primero."""
        return sorted(self.datos.items(), key=lambda kv: kv[1].get("fecha", ""), reverse=True)
