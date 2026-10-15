"""Lectura y escritura de los archivos de datos JSON (S-09, RNF-005, RNF-006)."""
import hashlib
import json
import os
import secrets
import shutil
import sys
from datetime import datetime

from rutas import CAMPOS, normalizar

# Como ejecutable (.exe) los datos van junto al .exe, no en la carpeta temporal
# donde PyInstaller descomprime el programa; así se conservan al cerrarlo (RNF-006).
if getattr(sys, "frozen", False):
    CARPETA_DATOS = os.path.join(os.path.dirname(sys.executable), "datos")
else:
    CARPETA_DATOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos")
CARPETA_DATOS_INICIALES = os.path.join(getattr(sys, "_MEIPASS", ""), "datos_iniciales")
CATEGORIAS = ["playa", "naturaleza", "cultural", "gastronómico", "aventura"]
CONTRASENA_INICIAL = "admin123"

# Rango de coordenadas aceptado: la provincia de Manabí con algo de margen
LAT_MIN, LAT_MAX = -2.0, 0.6
LON_MIN, LON_MAX = -81.2, -79.0


class ErrorValidacion(Exception):
    """Dato rechazado al guardar (RF-013). El mensaje empieza por el campo afectado."""


def _leer_json(ruta, por_defecto):
    if not os.path.exists(ruta):
        return por_defecto
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def _escribir_json(ruta, datos):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    # Se escribe en un temporal y se reemplaza, para no dejar el archivo a medias
    temporal = ruta + ".tmp"
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=4)
    os.replace(temporal, ruta)


def preparar_datos_iniciales():
    """En el ejecutable, copia los lugares y conexiones de ejemplo junto al .exe la primera vez."""
    if not getattr(sys, "frozen", False) or not os.path.isdir(CARPETA_DATOS_INICIALES):
        return
    os.makedirs(CARPETA_DATOS, exist_ok=True)
    for archivo in ("lugares.json", "conexiones.json", "mapa_base.json"):
        destino = os.path.join(CARPETA_DATOS, archivo)
        if not os.path.exists(destino):
            shutil.copy(os.path.join(CARPETA_DATOS_INICIALES, archivo), destino)


def cargar_mapa_base(carpeta=CARPETA_DATOS):
    """Capas de OpenStreetMap ya descargadas (descargar_mapa.py). None si no existe el archivo."""
    return _leer_json(os.path.join(carpeta, "mapa_base.json"), None)


def _texto_obligatorio(datos, campo, etiqueta):
    valor = str(datos.get(campo) or "").strip()
    if not valor:
        raise ErrorValidacion(f"{etiqueta}: el campo es obligatorio.")
    return valor


def _numero(datos, campo, etiqueta, obligatorio):
    crudo = datos.get(campo)
    if crudo is None or str(crudo).strip() == "":
        if obligatorio:
            raise ErrorValidacion(f"{etiqueta}: el campo es obligatorio.")
        return None
    try:
        return float(str(crudo).strip().replace(",", "."))
    except ValueError:
        raise ErrorValidacion(f"{etiqueta}: debe ser un número.") from None


def _positivo(datos, campo, etiqueta, obligatorio):
    valor = _numero(datos, campo, etiqueta, obligatorio)
    if valor is not None and valor <= 0:
        raise ErrorValidacion(f"{etiqueta}: debe ser mayor que cero.")
    return valor


class Repositorio:
    """Lugares, conexiones, historial y contraseña guardados en la carpeta de datos."""

    def __init__(self, carpeta=CARPETA_DATOS):
        self.carpeta = carpeta
        self.lugares = _leer_json(self._ruta("lugares.json"), [])
        self.conexiones = _leer_json(self._ruta("conexiones.json"), [])
        self.historial = _leer_json(self._ruta("historial.json"), [])
        self.config = _leer_json(self._ruta("config.json"), {})
        if "hash_contrasena" not in self.config:
            self.cambiar_contrasena(CONTRASENA_INICIAL)

    def _ruta(self, archivo):
        return os.path.join(self.carpeta, archivo)

    def _guardar_lugares(self):
        _escribir_json(self._ruta("lugares.json"), self.lugares)

    def _guardar_conexiones(self):
        _escribir_json(self._ruta("conexiones.json"), self.conexiones)

    @staticmethod
    def _siguiente_id(elementos):
        return max((e["id"] for e in elementos), default=0) + 1

    # ---------- Consultas ----------

    def lugar(self, id_lugar):
        return next((l for l in self.lugares if l["id"] == id_lugar), None)

    def lugar_por_nombre(self, nombre):
        buscado = normalizar(nombre)
        return next((l for l in self.lugares if normalizar(l["nombre"]) == buscado), None)

    def conexion(self, id_conexion):
        return next((c for c in self.conexiones if c["id"] == id_conexion), None)

    def cantones(self):
        return sorted({l["canton"] for l in self.lugares}, key=normalizar)

    # ---------- Lugares (RF-011, RF-013) ----------

    def validar_lugar(self, datos, id_actual=None):
        nombre = _texto_obligatorio(datos, "nombre", "Nombre")
        canton = _texto_obligatorio(datos, "canton", "Cantón")
        categoria = _texto_obligatorio(datos, "categoria", "Categoría")
        descripcion = _texto_obligatorio(datos, "descripcion", "Descripción")
        if categoria not in CATEGORIAS:
            raise ErrorValidacion("Categoría: elige una de la lista.")
        for otro in self.lugares:
            if otro["id"] != id_actual and normalizar(otro["nombre"]) == normalizar(nombre):
                raise ErrorValidacion("Nombre: ya existe un lugar con ese nombre.")
        lat = _numero(datos, "lat", "Latitud", True)
        lon = _numero(datos, "lon", "Longitud", True)
        if not LAT_MIN <= lat <= LAT_MAX:
            raise ErrorValidacion("Latitud: el punto queda fuera de Manabí.")
        if not LON_MIN <= lon <= LON_MAX:
            raise ErrorValidacion("Longitud: el punto queda fuera de Manabí.")
        return {"nombre": nombre, "canton": canton, "categoria": categoria,
                "descripcion": descripcion, "lat": lat, "lon": lon}

    def agregar_lugar(self, datos):
        lugar = {"id": self._siguiente_id(self.lugares), **self.validar_lugar(datos)}
        self.lugares.append(lugar)
        self._guardar_lugares()
        return lugar

    def editar_lugar(self, id_lugar, datos):
        lugar = self.lugar(id_lugar)
        if lugar is None:
            raise KeyError(id_lugar)
        lugar.update(self.validar_lugar(datos, id_actual=id_lugar))
        self._guardar_lugares()
        return lugar

    def eliminar_lugar(self, id_lugar):
        """Elimina el lugar y también sus conexiones (CA-010-2)."""
        self.lugares = [l for l in self.lugares if l["id"] != id_lugar]
        self.conexiones = [c for c in self.conexiones if id_lugar not in (c["origen"], c["destino"])]
        self._guardar_lugares()
        self._guardar_conexiones()

    # ---------- Conexiones (RF-012, RF-013) ----------

    def validar_conexion(self, datos, id_actual=None):
        origen = datos.get("origen")
        destino = datos.get("destino")
        if self.lugar(origen) is None:
            raise ErrorValidacion("Lugar A: elige un lugar registrado.")
        if self.lugar(destino) is None:
            raise ErrorValidacion("Lugar B: elige un lugar registrado.")
        if origen == destino:
            raise ErrorValidacion("Lugar B: debe ser distinto del lugar A.")
        for c in self.conexiones:
            if c["id"] != id_actual and {c["origen"], c["destino"]} == {origen, destino}:
                raise ErrorValidacion("Lugar B: ya existe una conexión entre estos lugares.")
        return {
            "origen": origen,
            "destino": destino,
            "distancia_km": _positivo(datos, "distancia_km", "Distancia", True),
            # Tiempo y costo pueden faltar: se muestran como "no disponible" (RF-007)
            "tiempo_min": _positivo(datos, "tiempo_min", "Tiempo", False),
            "costo_usd": _positivo(datos, "costo_usd", "Costo", False),
        }

    def agregar_conexion(self, datos):
        conexion = {"id": self._siguiente_id(self.conexiones), **self.validar_conexion(datos)}
        self.conexiones.append(conexion)
        self._guardar_conexiones()
        return conexion

    def editar_conexion(self, id_conexion, datos):
        conexion = self.conexion(id_conexion)
        if conexion is None:
            raise KeyError(id_conexion)
        conexion.update(self.validar_conexion(datos, id_actual=id_conexion))
        self._guardar_conexiones()
        return conexion

    def eliminar_conexion(self, id_conexion):
        self.conexiones = [c for c in self.conexiones if c["id"] != id_conexion]
        self._guardar_conexiones()

    # ---------- Historial (RF-010, RNF-006) ----------

    def registrar_ruta(self, resultado):
        """Guarda una ruta calculada al inicio del historial y devuelve la entrada.

        Se guardan los nombres, no los IDs, para que el historial siga siendo
        legible aunque después se edite o elimine un lugar.
        """
        nombre = lambda id_lugar: self.lugar(id_lugar)["nombre"]
        entrada = {
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "criterio": resultado["criterio"],
            "origen": nombre(resultado["lugares"][0]),
            "destino": nombre(resultado["lugares"][-1]),
            "lugares": [nombre(i) for i in resultado["lugares"]],
            "tramos": [
                {"desde": nombre(t["desde"]), "hasta": nombre(t["hasta"]), **{k: t[k] for k in CAMPOS}}
                for t in resultado["tramos"]
            ],
            "totales": resultado["totales"],
        }
        self.historial.insert(0, entrada)
        _escribir_json(self._ruta("historial.json"), self.historial)
        return entrada

    # ---------- Administrador (RNF-003) ----------

    @staticmethod
    def _hash(texto, sal):
        return hashlib.pbkdf2_hmac("sha256", texto.encode("utf-8"), sal, 100_000).hex()

    def verificar_contrasena(self, texto):
        sal = bytes.fromhex(self.config["sal"])
        return secrets.compare_digest(self._hash(texto, sal), self.config["hash_contrasena"])

    def cambiar_contrasena(self, nueva):
        if len(nueva) < 4:
            raise ErrorValidacion("Contraseña: debe tener al menos 4 caracteres.")
        sal = secrets.token_bytes(16)
        self.config["sal"] = sal.hex()
        self.config["hash_contrasena"] = self._hash(nueva, sal)
        _escribir_json(self._ruta("config.json"), self.config)
