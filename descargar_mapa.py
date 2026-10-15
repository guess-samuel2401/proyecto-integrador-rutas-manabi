"""Descarga UNA SOLA VEZ los datos de OpenStreetMap de Manabí y genera datos/mapa_base.json.

Es una herramienta de desarrollo: el programa no la usa al ejecutarse, solo lee el
JSON generado, por lo que sigue funcionando sin internet (RES-003).
Datos © OpenStreetMap contributors, licencia ODbL.

Uso:  python descargar_mapa.py
"""
import json
import math
import os
import tempfile
import time
from collections import Counter
from datetime import date

import requests

# Recuadro que cubre Manabí con margen (sur, oeste, norte, este)
SUR, OESTE, NORTE, ESTE = -1.95, -81.15, 0.45, -79.25
# Servidores públicos de Overpass; si uno está saturado se prueba el siguiente
SERVIDORES = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
AGENTE = {"User-Agent": "RutasManabi-proyecto-academico/1.0"}
TOLERANCIA = 0.0003  # grados (~33 m): detalle que se descarta al simplificar líneas
AREA_MINIMA = 0.00003  # grados² (~0.4 km²): lagunas y estanques más pequeños no se dibujan
SALIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos", "mapa_base.json")
# Borrar esta carpeta para forzar una descarga nueva
CARPETA_CACHE = os.path.join(tempfile.gettempdir(), "rutas_manabi_osm")

CAPAS = {
    "costa": 'way["natural"="coastline"]',
    "agua_vias": 'way["natural"="water"]',
    "agua_relaciones": 'relation["natural"="water"]',
    "bordes": 'way["boundary"="administrative"]["admin_level"~"^(4|6)$"]',
    "carreteras": 'way["highway"~"^(trunk|primary|secondary)$"]',
    "rios": 'way["waterway"="river"]',
    "poblados": 'node["place"~"^(city|town)$"]',
}


def consultar(capa, filtro):
    """Descarga una capa; la guarda en un caché temporal para no repetir la consulta si algo falla."""
    cache = os.path.join(CARPETA_CACHE, f"{capa}.json")
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            return json.load(f)
    consulta = f"[out:json][timeout:180];{filtro}({SUR},{OESTE},{NORTE},{ESTE});out geom;"
    for intento in range(1, 6):
        servidor = SERVIDORES[(intento - 1) % len(SERVIDORES)]
        try:
            respuesta = requests.post(servidor, data={"data": consulta}, headers=AGENTE, timeout=300)
        except requests.RequestException as error:
            print(f"  {servidor}: {error}; reintento {intento} de 5...")
            time.sleep(30 * intento)
            continue
        if respuesta.ok and "elements" in respuesta.text[:2000]:
            elementos = respuesta.json()["elements"]
            os.makedirs(CARPETA_CACHE, exist_ok=True)
            with open(cache, "w", encoding="utf-8") as f:
                json.dump(elementos, f)
            time.sleep(10)  # no saturar el servidor público
            return elementos
        # 429 = demasiadas consultas; 504 = servidor ocupado. Se espera cada vez más.
        print(f"  {servidor} respondió {respuesta.status_code}; reintento {intento} de 5...")
        time.sleep(30 * intento)
    raise SystemExit(f"No se pudo descargar la capa «{capa}». Inténtalo más tarde; "
                     "las capas ya descargadas quedan guardadas en el caché.")


def distancia_km(a, b):
    """Distancia entre dos puntos [lat, lon] (fórmula del haversine)."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def puntos_de(via):
    return [[round(p["lat"], 5), round(p["lon"], 5)] for p in via["geometry"]]


def longitud_km(puntos):
    return sum(distancia_km(a, b) for a, b in zip(puntos, puntos[1:]))


def red_vial(vias):
    """Divide las carreteras en tramos entre cruces, para poder calcular rutas por ellas.

    Devuelve (nodos, tramos). Cada tramo une dos nodos (índices en la lista de nodos)
    y guarda su longitud real en km, medida antes de simplificar la línea.
    """
    usos = Counter(n for v in vias for n in v["nodes"])
    indices = {}
    nodos = []

    def nodo(id_osm, punto):
        if id_osm not in indices:
            indices[id_osm] = len(nodos)
            nodos.append(punto)
        return indices[id_osm]

    tramos = []
    for v in vias:
        ids, puntos = v["nodes"], puntos_de(v)
        inicio = 0
        for k in range(1, len(ids)):
            # Se corta la vía en cada cruce (nodo compartido con otra vía) y en su final
            if usos[ids[k]] > 1 or k == len(ids) - 1:
                segmento = puntos[inicio:k + 1]
                tramos.append({
                    "tipo": v["tags"]["highway"], "ref": v["tags"].get("ref", ""),
                    "a": nodo(ids[inicio], segmento[0]), "b": nodo(ids[k], segmento[-1]),
                    "km": round(longitud_km(segmento), 3), "puntos": simplificar(segmento),
                })
                inicio = k
    return nodos, tramos


def area(anillo):
    """Área aproximada en grados² (fórmula del polígono de Gauss)."""
    return abs(sum(a[1] * b[0] - b[1] * a[0] for a, b in zip(anillo, anillo[1:] + anillo[:1]))) / 2


def unir_anillos(tramos):
    """Une tramos de línea que comparten extremos hasta formar anillos cerrados."""
    pendientes = [list(t) for t in tramos if len(t) >= 2]
    anillos = []
    while pendientes:
        anillo = pendientes.pop()
        while anillo[0] != anillo[-1]:
            for i, t in enumerate(pendientes):
                if t[0] == anillo[-1]:
                    anillo = anillo + t[1:]
                elif t[-1] == anillo[-1]:
                    anillo = anillo + t[-2::-1]
                elif t[-1] == anillo[0]:
                    anillo = t[:-1] + anillo
                elif t[0] == anillo[0]:
                    anillo = t[:0:-1] + anillo
                else:
                    continue
                pendientes.pop(i)
                break
            else:
                break  # faltan tramos: el anillo no se puede cerrar
        if anillo[0] == anillo[-1]:
            anillos.append(anillo)
    return anillos


def areas_de_agua(vias, relaciones):
    """Estuarios, embalses y lagunas grandes. Devuelve (agua, islas dentro del agua)."""
    agua = [puntos_de(v) for v in vias if v["nodes"][0] == v["nodes"][-1]]
    islas = []
    for r in relaciones:
        for rol, destino in (("outer", agua), ("inner", islas)):
            tramos = [puntos_de(m) for m in r.get("members", [])
                      if m["type"] == "way" and m.get("role") == rol and "geometry" in m]
            destino.extend(unir_anillos(tramos))
    grandes = lambda anillos: [simplificar(a) for a in anillos if area(a) >= AREA_MINIMA]
    return grandes(agua), grandes(islas)


def simplificar(puntos, tolerancia=TOLERANCIA):
    """Douglas-Peucker: quita puntos que se desvían menos que la tolerancia."""
    if len(puntos) < 3:
        return puntos
    conservar = [False] * len(puntos)
    conservar[0] = conservar[-1] = True
    pendientes = [(0, len(puntos) - 1)]
    while pendientes:
        i, j = pendientes.pop()
        (y1, x1), (y2, x2) = puntos[i], puntos[j]
        dx, dy = x2 - x1, y2 - y1
        largo2 = dx * dx + dy * dy
        mayor, indice = 0.0, None
        for k in range(i + 1, j):
            y, x = puntos[k]
            t = 0.0 if largo2 == 0 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / largo2))
            d2 = (x - x1 - t * dx) ** 2 + (y - y1 - t * dy) ** 2
            if d2 > mayor:
                mayor, indice = d2, k
        if indice is not None and mayor > tolerancia ** 2:
            conservar[indice] = True
            pendientes += [(i, indice), (indice, j)]
    return [p for p, c in zip(puntos, conservar) if c]


def unir_costa(vias):
    """Une las vías de costa en cadenas. En OSM la tierra queda a la izquierda del sentido de la vía."""
    por_inicio = {v["nodes"][0]: v for v in vias}
    finales = {v["nodes"][-1] for v in vias}
    usadas = set()
    cadenas = []
    # Primero las cadenas abiertas (empiezan donde no termina otra vía), luego los anillos (islas)
    for inicio in [v for v in vias if v["nodes"][0] not in finales] + vias:
        if inicio["id"] in usadas:
            continue
        puntos = []
        actual = inicio
        while actual is not None and actual["id"] not in usadas:
            usadas.add(actual["id"])
            geometria = puntos_de(actual)
            puntos.extend(geometria if not puntos else geometria[1:])
            actual = por_inicio.get(actual["nodes"][-1])
        cadenas.append(puntos)
    return cadenas


def poligonos_de_tierra(cadenas):
    """Convierte la costa en polígonos de tierra para pintarlos sobre el fondo de mar."""
    poligonos = []
    for puntos in cadenas:
        if puntos[0] == puntos[-1]:
            poligonos.append(puntos)  # isla
        elif puntos[0][0] > puntos[-1][0]:
            # Costa continental recorrida de norte a sur: la tierra está al este, se cierra por ahí
            lejos = ESTE + 2
            poligonos.append(puntos + [[puntos[-1][0], lejos], [puntos[0][0], lejos]])
        else:
            print(f"  aviso: tramo de costa sin cerrar ignorado ({len(puntos)} puntos)")
    return [simplificar(p) for p in poligonos]


def main():
    crudo = {}
    for capa, filtro in CAPAS.items():
        print(f"Descargando {capa}...")
        crudo[capa] = consultar(capa, filtro)
        print(f"  {len(crudo[capa])} elementos")

    cadenas = unir_costa(crudo["costa"])
    print(f"Costa: {len(cadenas)} cadenas; abiertas: "
          f"{[(len(c), c[0], c[-1]) for c in cadenas if c[0] != c[-1]]}")
    agua, islas = areas_de_agua(crudo["agua_vias"], crudo["agua_relaciones"])
    print(f"Agua: {len(agua)} áreas grandes, {len(islas)} islas dentro del agua")
    nodos, tramos = red_vial(crudo["carreteras"])
    print(f"Red vial: {len(nodos)} cruces, {len(tramos)} tramos")

    mapa = {
        "fuente": "© OpenStreetMap contributors",
        "licencia": "ODbL - https://www.openstreetmap.org/copyright",
        "descargado": date.today().isoformat(),
        "recuadro": {"sur": SUR, "oeste": OESTE, "norte": NORTE, "este": ESTE},
        "tierra": poligonos_de_tierra(cadenas),
        "agua": agua,
        "islas_agua": islas,
        "bordes": [
            {"nivel": int(v["tags"]["admin_level"]), "puntos": simplificar(puntos_de(v))}
            for v in crudo["bordes"]
            # Se omiten límites marítimos y los que coinciden con la costa
            if v["tags"].get("maritime") != "yes" and "natural" not in v["tags"]
        ],
        # Las carreteras se guardan como tramos de la red vial: sirven para dibujar y para trazar rutas
        "nodos": nodos,
        "carreteras": tramos,
        "rios": [
            {"nombre": v["tags"].get("name", ""), "puntos": simplificar(puntos_de(v))}
            for v in crudo["rios"]
        ],
        "poblados": sorted(
            ({"nombre": n["tags"]["name"], "tipo": n["tags"]["place"],
              "lat": round(n["lat"], 5), "lon": round(n["lon"], 5)}
             for n in crudo["poblados"] if "name" in n.get("tags", {})),
            key=lambda p: p["nombre"]),
    }
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(mapa, f, ensure_ascii=False, separators=(",", ":"))

    total = sum(len(e["puntos"]) for capa in ("bordes", "carreteras", "rios") for e in mapa[capa])
    total += sum(len(p) for capa in ("tierra", "agua", "islas_agua") for p in mapa[capa])
    print(f"Guardado {SALIDA} ({os.path.getsize(SALIDA) / 1024:.0f} KB, {total} puntos)")


if __name__ == "__main__":
    main()
