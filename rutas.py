"""Lógica de consulta y cálculo de rutas, separada de la interfaz (RNF-005)."""
import heapq
import unicodedata

# Criterio de cálculo (RF-006 usa distancia; RF-015 permite tiempo o costo)
CRITERIOS = {"distancia": "distancia_km", "tiempo": "tiempo_min", "costo": "costo_usd"}
CAMPOS = ("distancia_km", "tiempo_min", "costo_usd")


def normalizar(texto):
    """Quita tildes y mayúsculas para comparar textos (RF-002)."""
    descompuesto = unicodedata.normalize("NFD", str(texto))
    sin_tildes = "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")
    return sin_tildes.casefold().strip()


def filtrar_lugares(lugares, texto="", canton=None, categoria=None):
    """Búsqueda parcial por nombre combinada con filtros de cantón y categoría (RF-002, RF-003)."""
    buscado = normalizar(texto)
    resultado = [
        l for l in lugares
        if buscado in normalizar(l["nombre"])
        and (not canton or l["canton"] == canton)
        and (not categoria or l["categoria"] == categoria)
    ]
    return sorted(resultado, key=lambda l: normalizar(l["nombre"]))


def conexiones_de(conexiones, id_lugar):
    """Conexiones directas de un lugar como pares (id_vecino, conexión) (RF-008)."""
    vecinos = []
    for c in conexiones:
        if c["origen"] == id_lugar:
            vecinos.append((c["destino"], c))
        elif c["destino"] == id_lugar:
            vecinos.append((c["origen"], c))
    return vecinos


def sumar(valores):
    """Total de una columna; None ("no disponible") si falta algún valor (CA-007-3)."""
    if any(v is None for v in valores):
        return None
    return round(sum(valores), 2)


def calcular_ruta(conexiones, id_origen, id_destino, criterio="distancia"):
    """Ruta óptima con Dijkstra. Las conexiones valen en ambos sentidos (S-07).

    Devuelve None si no existe ruta (RF-014). Con los mismos datos el resultado
    es siempre el mismo (RNF-004).
    """
    if id_origen == id_destino:
        raise ValueError("El origen y el destino final deben ser distintos.")
    campo = CRITERIOS[criterio]

    grafo = {}
    for c in conexiones:
        # Una conexión sin el dato del criterio elegido no se puede usar para ese criterio
        if c.get(campo) is None:
            continue
        grafo.setdefault(c["origen"], []).append((c["destino"], c))
        grafo.setdefault(c["destino"], []).append((c["origen"], c))

    mejor = {id_origen: 0}
    previo = {}
    cola = [(0, id_origen)]
    visitados = set()
    while cola:
        peso, actual = heapq.heappop(cola)
        if actual in visitados:
            continue
        visitados.add(actual)
        if actual == id_destino:
            break
        for vecino, c in grafo.get(actual, []):
            nuevo = peso + c[campo]
            if vecino not in visitados and nuevo < mejor.get(vecino, float("inf")):
                mejor[vecino] = nuevo
                previo[vecino] = (actual, c)
                heapq.heappush(cola, (nuevo, vecino))

    if id_destino not in visitados:
        return None

    ids = [id_destino]
    tramos = []
    while ids[-1] != id_origen:
        anterior, c = previo[ids[-1]]
        tramos.append({"desde": anterior, "hasta": ids[-1], **{k: c.get(k) for k in CAMPOS}})
        ids.append(anterior)
    ids.reverse()
    tramos.reverse()

    totales = {k: sumar([t[k] for t in tramos]) for k in CAMPOS}
    return {"criterio": criterio, "lugares": ids, "tramos": tramos, "totales": totales}
