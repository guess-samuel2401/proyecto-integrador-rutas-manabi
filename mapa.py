"""Mapa de Manabí dibujado en un Canvas de Tkinter, sin internet (RES-003).

El fondo (costa, bordes, ríos, carreteras y poblaciones) viene de datos/mapa_base.json,
generado una sola vez con descargar_mapa.py a partir de OpenStreetMap.
"""
import tkinter as tk

COLORES_CATEGORIA = {
    "playa": "#1f77b4",
    "naturaleza": "#2ca02c",
    "cultural": "#9467bd",
    "gastronómico": "#ff7f0e",
    "aventura": "#8c564b",
}
COLOR_RUTA = "#d62728"
COLOR_CONEXION = "#7d8790"
COLOR_INACTIVO = "#cfcfcf"
MARGEN = 40
CENTRO_MANABI = (-0.95, -80.25)

# Colores parecidos a los de openstreetmap.org
COLOR_MAR = "#aad3df"
COLOR_TIERRA = "#f2efe9"
COLOR_SIN_MAPA = "#eef4f7"
COLOR_RIO = "#8cbfdc"
ESTILO_BORDE = {4: ("#9e7fb8", 2, (8, 4)), 6: ("#c4b3d4", 1, (3, 3))}
# tipo: (ancho, relleno, contorno)
ESTILO_CARRETERA = {
    "trunk": (4, "#e8838a", "#b85a60"),
    "primary": (3, "#f5bd7a", "#c48a45"),
    "secondary": (2, "#f2e6a0", "#b8a959"),
}


def _preparar_capa(elementos):
    """Calcula el recuadro de cada línea para saltarse las que no se ven en pantalla."""
    preparados = []
    for e in elementos:
        puntos = e["puntos"] if isinstance(e, dict) else e
        lats = [p[0] for p in puntos]
        lons = [p[1] for p in puntos]
        preparados.append((min(lats), min(lons), max(lats), max(lons), puntos, e))
    return preparados


class MapaManabi(tk.Canvas):
    """Dibuja el mapa base, los lugares (puntos), las conexiones (líneas) y la ruta.

    Rueda del ratón: zoom. Arrastrar: mover. Clic en un punto: seleccionarlo.
    """

    def __init__(self, master, mapa_base=None, red_vial=None, al_seleccionar=None, al_clic_vacio=None):
        super().__init__(master, bg=COLOR_MAR if mapa_base else COLOR_SIN_MAPA, highlightthickness=0)
        self.red_vial = red_vial
        self.al_seleccionar = al_seleccionar
        self.al_clic_vacio = al_clic_vacio
        self.lugares = []
        self.conexiones = []
        self.ruta = []
        self.seleccionado = None
        self.visibles = None
        self.centro = CENTRO_MANABI
        self.extension = (1.5, 1.5)
        self.zoom = 1.0
        self.desplazamiento = [0.0, 0.0]
        self._ultimo = None
        self._movido = False

        self.base = None
        if mapa_base:
            self.base = {
                "tierra": _preparar_capa(mapa_base["tierra"]),
                "agua": _preparar_capa(mapa_base.get("agua", [])),
                "islas_agua": _preparar_capa(mapa_base.get("islas_agua", [])),
                "rios": _preparar_capa(mapa_base["rios"]),
                "bordes": _preparar_capa(mapa_base["bordes"]),
                # Las vías menores primero para que las principales queden encima
                "carreteras": _preparar_capa(sorted(
                    mapa_base["carreteras"], key=lambda c: ESTILO_CARRETERA.get(c["tipo"], (1,))[0])),
                "poblados": mapa_base["poblados"],
                "fuente": mapa_base["fuente"],
            }
            # Vista inicial: Manabí completo
            r = mapa_base["recuadro"]
            self.centro = ((r["norte"] + r["sur"]) / 2, (r["este"] + r["oeste"]) / 2)
            self.extension = (r["norte"] - r["sur"] - 0.2, r["este"] - r["oeste"] - 0.2)

        self.bind("<Configure>", self.dibujar)
        self.bind("<ButtonPress-1>", self._presionar)
        self.bind("<B1-Motion>", self._arrastrar)
        self.bind("<ButtonRelease-1>", self._soltar)
        self.bind("<MouseWheel>", self._rueda)

    # ---------- Datos que se muestran ----------

    def cargar(self, lugares, conexiones):
        self.lugares = lugares
        self.conexiones = conexiones
        if lugares and self.base is None:
            lats = [l["lat"] for l in lugares]
            lons = [l["lon"] for l in lugares]
            self.centro = ((max(lats) + min(lats)) / 2, (max(lons) + min(lons)) / 2)
            self.extension = (max(max(lats) - min(lats), 0.1), max(max(lons) - min(lons), 0.1))
        self.dibujar()

    def mostrar_ruta(self, ids):
        self.ruta = list(ids or [])
        self.dibujar()

    def seleccionar(self, id_lugar):
        self.seleccionado = id_lugar
        self.dibujar()

    def filtrar(self, ids_visibles):
        """Atenúa los lugares que no están en el listado filtrado (None = todos)."""
        self.visibles = ids_visibles
        self.dibujar()

    def reiniciar_vista(self):
        self.zoom = 1.0
        self.desplazamiento = [0.0, 0.0]
        self.dibujar()

    # ---------- Conversión de coordenadas ----------

    def _escala(self):
        ancho = max(self.winfo_width() - 2 * MARGEN, 50)
        alto = max(self.winfo_height() - 2 * MARGEN, 50)
        return min(ancho / self.extension[1], alto / self.extension[0]) * self.zoom

    def _origen(self):
        return (self.winfo_width() / 2 + self.desplazamiento[0],
                self.winfo_height() / 2 + self.desplazamiento[1])

    def a_pantalla(self, lat, lon):
        escala = self._escala()
        ox, oy = self._origen()
        return ox + (lon - self.centro[1]) * escala, oy - (lat - self.centro[0]) * escala

    def a_coordenadas(self, x, y):
        escala = self._escala()
        ox, oy = self._origen()
        return round(self.centro[0] - (y - oy) / escala, 5), round(self.centro[1] + (x - ox) / escala, 5)

    def _proyectar(self, puntos, escala, ox, oy):
        c0, c1 = self.centro
        plano = []
        for lat, lon in puntos:
            plano.append(ox + (lon - c1) * escala)
            plano.append(oy - (lat - c0) * escala)
        return plano

    # ---------- Dibujo ----------

    def dibujar(self, _evento=None):
        self.delete("all")
        ancho, alto = self.winfo_width(), self.winfo_height()
        if self.base:
            self._dibujar_base(ancho, alto)
        elif self.lugares:
            self.create_text(28, alto / 2, text="Océano Pacífico", angle=90, tags="mapa",
                             fill="#8fb3c9", font=("Segoe UI", 14, "italic"))

        if not self.lugares:
            self.create_text(ancho / 2, alto / 2, text="No hay lugares registrados", tags="fijo",
                             fill="#666", font=("Segoe UI", 14))
        else:
            self._dibujar_lugares()
            self._dibujar_leyenda()
        self.create_text(ancho - 10, alto - 10, anchor="se", fill="#555", font=("Segoe UI", 9), tags="fijo",
                         text="Rueda: zoom · Arrastrar: mover · Clic en un punto: ver ficha")

    def _dibujar_base(self, ancho, alto):
        escala = self._escala()
        ox, oy = self._origen()
        # Recuadro visible en grados, para no dibujar lo que queda fuera de la pantalla
        norte, oeste = self.a_coordenadas(0, 0)
        sur, este = self.a_coordenadas(ancho, alto)

        def visibles(capa):
            for min_lat, min_lon, max_lat, max_lon, puntos, elemento in capa:
                if max_lat >= sur and min_lat <= norte and max_lon >= oeste and min_lon <= este:
                    yield self._proyectar(puntos, escala, ox, oy), elemento

        for plano, _ in visibles(self.base["tierra"]):
            self.create_polygon(plano, fill=COLOR_TIERRA, outline="#b5d0d0", tags="mapa")
        # Estuarios, embalses y lagunas; las islas dentro del agua se vuelven a pintar como tierra
        for plano, _ in visibles(self.base["agua"]):
            self.create_polygon(plano, fill=COLOR_MAR, outline="", tags="mapa")
        for plano, _ in visibles(self.base["islas_agua"]):
            self.create_polygon(plano, fill=COLOR_TIERRA, outline="", tags="mapa")
        lat_mar, lon_mar = -1.15, -81.0
        self.create_text(*self.a_pantalla(lat_mar, lon_mar), text="Océano Pacífico", tags="mapa",
                         fill="#5d8fa8", font=("Segoe UI", 13, "italic"))

        for plano, _ in visibles(self.base["rios"]):
            self.create_line(plano, fill=COLOR_RIO, width=1.5, tags="mapa")
        for plano, borde in visibles(self.base["bordes"]):
            color, grosor, guiones = ESTILO_BORDE.get(borde["nivel"], ESTILO_BORDE[6])
            self.create_line(plano, fill=color, width=grosor, dash=guiones, tags="mapa")

        carreteras = list(visibles(self.base["carreteras"]))
        for plano, via in carreteras:  # contorno
            grosor, _, contorno = ESTILO_CARRETERA.get(via["tipo"], ESTILO_CARRETERA["secondary"])
            self.create_line(plano, fill=contorno, width=grosor + 2, capstyle=tk.ROUND, tags="mapa")
        for plano, via in carreteras:  # relleno
            grosor, relleno, _ = ESTILO_CARRETERA.get(via["tipo"], ESTILO_CARRETERA["secondary"])
            self.create_line(plano, fill=relleno, width=grosor, capstyle=tk.ROUND, tags="mapa")

        for p in self.base["poblados"]:
            ciudad = p["tipo"] == "city"
            # Con poco zoom solo se rotulan las ciudades, para que no se amontonen
            if not ciudad and self.zoom < 2:
                continue
            x, y = self.a_pantalla(p["lat"], p["lon"])
            if -50 <= x <= ancho + 50 and -50 <= y <= alto + 50:
                self.create_oval(x - 2, y - 2, x + 2, y + 2, fill="#555", outline="", tags="mapa")
                self.create_text(x, y - 4, text=p["nombre"], anchor="s", tags="mapa", fill="#333",
                                 font=("Segoe UI", 10 if ciudad else 8, "bold" if ciudad else "normal"))

        # Atribución obligatoria por la licencia de OpenStreetMap (ODbL)
        texto = self.create_text(6, alto - 6, anchor="sw", text=self.base["fuente"], tags="fijo",
                                 fill="#333", font=("Segoe UI", 8))
        x1, y1, x2, y2 = self.bbox(texto)
        self.tag_lower(self.create_rectangle(x1 - 3, y1 - 1, x2 + 3, y2 + 1, fill="white",
                                             outline="", stipple="gray75", tags="fijo"), texto)

    def _dibujar_lugares(self):
        posiciones = {l["id"]: self.a_pantalla(l["lat"], l["lon"]) for l in self.lugares}

        for c in self.conexiones:
            if c["origen"] in posiciones and c["destino"] in posiciones:
                self.create_line(*posiciones[c["origen"]], *posiciones[c["destino"]],
                                 fill=COLOR_CONEXION, width=1.5, dash=(6, 3), tags="mapa")

        lugares = {l["id"]: l for l in self.lugares}
        escala = self._escala()
        ox, oy = self._origen()
        for a, b in zip(self.ruta, self.ruta[1:]):
            if a not in posiciones or b not in posiciones:
                continue
            if self.red_vial is None:
                self.create_line(*posiciones[a], *posiciones[b], fill=COLOR_RUTA,
                                 width=5, capstyle=tk.ROUND, tags="mapa")
                continue
            # La ruta sigue las carreteras; el acceso entre el lugar y la vía se dibuja punteado
            puntos = self.red_vial.trazar((lugares[a]["lat"], lugares[a]["lon"]),
                                          (lugares[b]["lat"], lugares[b]["lon"]))["puntos"]
            plano = self._proyectar(puntos, escala, ox, oy)
            if len(plano) >= 8:  # hay al menos un tramo de carretera (dos puntos)
                self.create_line(plano[2:-2], fill=COLOR_RUTA, width=5, capstyle=tk.ROUND,
                                 joinstyle=tk.ROUND, tags="mapa")
            for acceso in (plano[:4], plano[-4:]):
                self.create_line(acceso, fill=COLOR_RUTA, width=2, dash=(4, 3), tags="mapa")

        extremos = (self.ruta[0], self.ruta[-1]) if self.ruta else ()
        for l in self.lugares:
            x, y = posiciones[l["id"]]
            activo = self.visibles is None or l["id"] in self.visibles or l["id"] in self.ruta
            color = COLORES_CATEGORIA.get(l["categoria"], "#555") if activo else COLOR_INACTIVO
            radio = 9 if l["id"] in extremos else 6
            if l["id"] == self.seleccionado:
                self.create_oval(x - radio - 5, y - radio - 5, x + radio + 5, y + radio + 5,
                                 outline="#222", width=2, tags="mapa")
            self.create_oval(x - radio, y - radio, x + radio, y + radio,
                             fill=color, outline="white", width=2, tags="mapa")
            self.create_text(x + radio + 4, y, text=l["nombre"], anchor="w", tags="mapa",
                             fill="#222" if activo else "#999", font=("Segoe UI", 9))

    def _dibujar_leyenda(self):
        x, y = 12, 12
        filas = len(COLORES_CATEGORIA) + 2
        self.create_rectangle(x, y, x + 150, y + 12 + filas * 20, fill="white", outline="#ccc", tags="fijo")
        for i, (categoria, color) in enumerate(COLORES_CATEGORIA.items()):
            cy = y + 16 + i * 20
            self.create_oval(x + 10, cy - 6, x + 22, cy + 6, fill=color, outline="", tags="fijo")
            self.create_text(x + 30, cy, text=categoria.capitalize(), anchor="w",
                             font=("Segoe UI", 9), tags="fijo")
        cy = y + 16 + len(COLORES_CATEGORIA) * 20
        self.create_line(x + 8, cy, x + 24, cy, fill=COLOR_CONEXION, width=1.5, dash=(6, 3), tags="fijo")
        self.create_text(x + 30, cy, text="Conexión registrada", anchor="w", font=("Segoe UI", 9), tags="fijo")
        cy += 20
        self.create_line(x + 8, cy, x + 24, cy, fill=COLOR_RUTA, width=4, tags="fijo")
        texto = "Ruta por carretera" if self.red_vial else "Ruta calculada"
        self.create_text(x + 30, cy, text=texto, anchor="w", font=("Segoe UI", 9), tags="fijo")

    # ---------- Ratón ----------

    def _presionar(self, evento):
        self._ultimo = (evento.x, evento.y)
        self._movido = False

    def _arrastrar(self, evento):
        if self._ultimo is None:
            return
        dx, dy = evento.x - self._ultimo[0], evento.y - self._ultimo[1]
        if self._movido or abs(dx) + abs(dy) > 3:
            self._movido = True
            self.desplazamiento[0] += dx
            self.desplazamiento[1] += dy
            self._ultimo = (evento.x, evento.y)
            # Mover lo ya dibujado es mucho más rápido que redibujar el mapa base
            self.move("mapa", dx, dy)

    def _soltar(self, evento):
        if self._movido:
            # Al soltar se redibuja para mostrar lo que entró en pantalla
            self.dibujar()
            return
        id_lugar = self._lugar_cercano(evento.x, evento.y)
        if id_lugar is not None:
            if self.al_seleccionar:
                self.al_seleccionar(id_lugar)
        elif self.al_clic_vacio:
            self.al_clic_vacio(*self.a_coordenadas(evento.x, evento.y))

    def _lugar_cercano(self, x, y, radio=12):
        mejor, mejor_distancia = None, radio ** 2
        for l in self.lugares:
            px, py = self.a_pantalla(l["lat"], l["lon"])
            distancia = (px - x) ** 2 + (py - y) ** 2
            if distancia <= mejor_distancia:
                mejor, mejor_distancia = l["id"], distancia
        return mejor

    def _rueda(self, evento):
        factor = 1.25 if evento.delta > 0 else 1 / 1.25
        nuevo_zoom = min(max(self.zoom * factor, 0.5), 60)
        factor = nuevo_zoom / self.zoom
        # Mantiene fijo el punto que está bajo el cursor
        cx = evento.x - self.winfo_width() / 2
        cy = evento.y - self.winfo_height() / 2
        self.desplazamiento[0] = cx - (cx - self.desplazamiento[0]) * factor
        self.desplazamiento[1] = cy - (cy - self.desplazamiento[1]) * factor
        self.zoom = nuevo_zoom
        self.dibujar()
