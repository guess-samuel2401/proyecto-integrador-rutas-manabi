"""Trazado de rutas por las carreteras de OpenStreetMap, separado de la interfaz (RNF-005).

La red sale de datos/mapa_base.json: "nodos" son cruces [lat, lon] y "carreteras" son
tramos entre dos cruces con su longitud en km y su geometría.
"""
import heapq
import math


def distancia_km(a, b):
    """Distancia en línea recta entre dos puntos (lat, lon) (fórmula del haversine)."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


class RedVial:
    def __init__(self, nodos, tramos):
        self.nodos = nodos
        self.tramos = tramos
        self.vecinos = {}
        for i, t in enumerate(tramos):
            self.vecinos.setdefault(t["a"], []).append((t["b"], t["km"], i))
            self.vecinos.setdefault(t["b"], []).append((t["a"], t["km"], i))
        # Solo se usa la parte conectada más grande: tramos sueltos no llevan a ningún lado
        self.conectados = sorted(self._componente_mayor())
        self._trazados = {}

    @classmethod
    def desde_mapa_base(cls, mapa_base):
        if not mapa_base or "nodos" not in mapa_base:
            return None
        return cls(mapa_base["nodos"], mapa_base["carreteras"])

    def _componente_mayor(self):
        sin_visitar = set(self.vecinos)
        mayor = set()
        while sin_visitar:
            pila = [sin_visitar.pop()]
            componente = set(pila)
            while pila:
                for vecino, _, _ in self.vecinos[pila.pop()]:
                    if vecino in sin_visitar:
                        sin_visitar.discard(vecino)
                        componente.add(vecino)
                        pila.append(vecino)
            if len(componente) > len(mayor):
                mayor = componente
        return mayor

    def nodo_cercano(self, punto):
        """Cruce de la red más cercano a un punto (lat, lon)."""
        lat, lon = punto
        coseno = math.cos(math.radians(lat))
        return min(self.conectados, key=lambda n: (self.nodos[n][0] - lat) ** 2
                                                   + ((self.nodos[n][1] - lon) * coseno) ** 2)

    def trazar(self, origen, destino):
        """Camino por carretera entre dos puntos (lat, lon).

        Devuelve {"puntos": [[lat, lon], ...], "km": total, "acceso_km": tramo sin carretera}.
        "acceso_km" es la distancia en línea recta entre cada lugar y la carretera más
        cercana, que también se suma al total.
        """
        clave = (tuple(origen), tuple(destino))
        if clave not in self._trazados:
            self._trazados[clave] = self._calcular(origen, destino)
        return self._trazados[clave]

    def _calcular(self, origen, destino):
        inicio, fin = self.nodo_cercano(origen), self.nodo_cercano(destino)
        mejor = {inicio: 0.0}
        previo = {}
        cola = [(0.0, inicio)]
        while cola:
            km, actual = heapq.heappop(cola)
            if actual == fin:
                break
            if km > mejor[actual]:
                continue
            for vecino, largo, tramo in self.vecinos[actual]:
                nuevo = km + largo
                if nuevo < mejor.get(vecino, float("inf")):
                    mejor[vecino] = nuevo
                    previo[vecino] = (actual, tramo)
                    heapq.heappush(cola, (nuevo, vecino))

        # Se reconstruye la geometría de fin a inicio, orientando cada tramo en el sentido del viaje
        partes = []
        nodo = fin
        while nodo != inicio:
            anterior, i = previo[nodo]
            t = self.tramos[i]
            partes.append(t["puntos"] if t["a"] == anterior else t["puntos"][::-1])
            nodo = anterior
        camino = [list(self.nodos[inicio])]
        for parte in reversed(partes):
            camino.extend(parte[1:])

        acceso = distancia_km(origen, self.nodos[inicio]) + distancia_km(destino, self.nodos[fin])
        return {
            "puntos": [list(origen)] + camino + [list(destino)],
            "km": round(mejor[fin] + acceso, 1),
            "acceso_km": round(acceso, 1),
        }
