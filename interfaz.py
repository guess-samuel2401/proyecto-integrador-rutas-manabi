"""Interfaz gráfica en Tkinter (RES-002). No contiene lógica de cálculo (RNF-005)."""
import os
import sys
import tkinter as tk
import traceback
from tkinter import messagebox, simpledialog, ttk

from datos import CATEGORIAS, ErrorValidacion, Repositorio, cargar_mapa_base
from mapa import MapaManabi
from red_vial import RedVial
from rutas import conexiones_de, calcular_ruta, filtrar_lugares, normalizar

TODOS = "Todos"
CRITERIOS_UI = {"Menor distancia": "distancia", "Menor tiempo": "tiempo", "Menor costo": "costo"}
NOMBRE_CRITERIO = {v: k for k, v in CRITERIOS_UI.items()}
MENSAJE_SIN_RUTA = "No existe una ruta registrada entre estos lugares"
NO_DISPONIBLE = "no disponible"


def ruta_recurso(nombre):
    """Ruta a un archivo de recursos, tanto desde el código como desde el .exe."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "recursos", nombre)


def fmt_km(valor):
    return NO_DISPONIBLE if valor is None else f"{valor:g} km"


def fmt_min(valor):
    return NO_DISPONIBLE if valor is None else f"{valor:g} min"


def fmt_usd(valor):
    return NO_DISPONIBLE if valor is None else f"${valor:.2f}"


def fmt_totales(totales):
    return (f"Total: {fmt_km(totales['distancia_km'])} · {fmt_min(totales['tiempo_min'])}"
            f" · {fmt_usd(totales['costo_usd'])}")


def crear_tabla(padre, columnas, altura):
    """Treeview con encabezados. columnas = [(clave, título, ancho), ...]"""
    tabla = ttk.Treeview(padre, columns=[c[0] for c in columnas], show="headings",
                         height=altura, selectmode="browse")
    for clave, titulo, ancho in columnas:
        tabla.heading(clave, text=titulo)
        tabla.column(clave, width=ancho, stretch=True)
    return tabla


class App(tk.Tk):
    def __init__(self, repo=None):
        super().__init__()
        self.title("Rutas turísticas de Manabí")
        self.geometry("1280x720")
        self.minsize(1000, 600)
        try:
            self.state("zoomed")  # maximizada: en pantallas de 1366x768 no cabría completa
        except tk.TclError:
            pass
        try:
            # default= aplica el icono también a las ventanas secundarias
            self.iconbitmap(default=ruta_recurso("icono.ico"))
        except tk.TclError:
            pass

        self.repo = repo or Repositorio()
        self.lugar_seleccionado = None
        self.ids_ruta_mostrada = []
        self.ventana_admin = None

        self._crear_interfaz()
        self.refrescar()

    def report_callback_exception(self, tipo, valor, rastro):
        # El .exe no tiene consola: los errores se muestran en una ventana
        traceback.print_exception(tipo, valor, rastro)
        messagebox.showerror("Error inesperado", f"{tipo.__name__}: {valor}")

    # ======================= Construcción =======================

    def _crear_interfaz(self):
        panel = ttk.Frame(self, width=420, padding=6)
        panel.pack(side=tk.LEFT, fill=tk.Y)
        panel.pack_propagate(False)

        self.pestanas = ttk.Notebook(panel)
        self.pestanas.pack(fill=tk.BOTH, expand=True)
        self._crear_pestana_lugares()
        self._crear_pestana_ruta()
        self._crear_pestana_historial()

        derecha = ttk.Frame(self)
        derecha.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        barra = ttk.Frame(derecha, padding=(6, 6, 6, 4))
        barra.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(barra, text="Ver todo Manabí", command=lambda: self.mapa.reiniciar_vista()).pack(side=tk.LEFT)
        ttk.Button(barra, text="Administración", command=self.abrir_administracion).pack(side=tk.RIGHT)

        mapa_base = cargar_mapa_base(self.repo.carpeta)
        self.red_vial = RedVial.desde_mapa_base(mapa_base)
        self.mapa = MapaManabi(derecha, mapa_base=mapa_base, red_vial=self.red_vial,
                               al_seleccionar=self.seleccionar_lugar,
                               al_clic_vacio=self._clic_vacio_mapa)
        self.mapa.pack(fill=tk.BOTH, expand=True)

    def _crear_pestana_lugares(self):
        f = ttk.Frame(self.pestanas, padding=6)
        self.pestanas.add(f, text="Lugares")

        ttk.Label(f, text="Buscar por nombre:").pack(anchor="w")
        self.var_busqueda = tk.StringVar()
        self.var_busqueda.trace_add("write", lambda *_: self.actualizar_listado())
        ttk.Entry(f, textvariable=self.var_busqueda).pack(fill=tk.X)

        filtros = ttk.Frame(f)
        filtros.pack(fill=tk.X, pady=6)
        ttk.Label(filtros, text="Cantón:").grid(row=0, column=0, sticky="w")
        self.cb_canton = ttk.Combobox(filtros, state="readonly", width=18)
        self.cb_canton.grid(row=0, column=1, padx=4, pady=2)
        ttk.Label(filtros, text="Categoría:").grid(row=1, column=0, sticky="w")
        self.cb_categoria = ttk.Combobox(filtros, state="readonly", width=18, values=[TODOS] + CATEGORIAS)
        self.cb_categoria.set(TODOS)
        self.cb_categoria.grid(row=1, column=1, padx=4, pady=2)
        ttk.Button(filtros, text="Quitar filtros", command=self.quitar_filtros).grid(
            row=0, column=2, rowspan=2, padx=4)
        for combo in (self.cb_canton, self.cb_categoria):
            combo.bind("<<ComboboxSelected>>", lambda _e: self.actualizar_listado())

        self.lbl_listado = ttk.Label(f, foreground="gray")
        self.lbl_listado.pack(anchor="w")
        self.tabla_lugares = crear_tabla(
            f, [("nombre", "Nombre", 170), ("canton", "Cantón", 100), ("categoria", "Categoría", 90)], 10)
        self.tabla_lugares.pack(fill=tk.BOTH, expand=True)
        self.tabla_lugares.bind("<<TreeviewSelect>>", self._lugar_elegido_en_tabla)

        ttk.Label(f, text="Ficha del lugar", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(8, 0))
        self.txt_ficha = tk.Text(f, height=12, wrap="word", state="disabled", relief="flat",
                                 background="#f7f7f7", font=("Segoe UI", 9))
        self.txt_ficha.tag_configure("titulo", font=("Segoe UI", 12, "bold"))
        self.txt_ficha.tag_configure("negrita", font=("Segoe UI", 9, "bold"))
        self.txt_ficha.pack(fill=tk.X)

        botones = ttk.Frame(f)
        botones.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(botones, text="Usar como origen",
                   command=lambda: self._usar_en_ruta(self.cb_origen)).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(botones, text="Usar como destino final",
                   command=lambda: self._usar_en_ruta(self.cb_destino)).pack(side=tk.LEFT, expand=True, fill=tk.X)

    def _crear_pestana_ruta(self):
        f = ttk.Frame(self.pestanas, padding=6)
        self.pestanas.add(f, text="Ruta")

        seleccion = ttk.Frame(f)
        seleccion.pack(fill=tk.X)
        ttk.Label(seleccion, text="Origen:").grid(row=0, column=0, sticky="w", pady=2)
        self.cb_origen = ttk.Combobox(seleccion, state="readonly", width=32)
        self.cb_origen.grid(row=0, column=1, pady=2)
        ttk.Label(seleccion, text="Destino final:").grid(row=1, column=0, sticky="w", pady=2)
        self.cb_destino = ttk.Combobox(seleccion, state="readonly", width=32)
        self.cb_destino.grid(row=1, column=1, pady=2)
        ttk.Label(seleccion, text="Criterio:").grid(row=2, column=0, sticky="w", pady=2)
        self.cb_criterio = ttk.Combobox(seleccion, state="readonly", width=32, values=list(CRITERIOS_UI))
        self.cb_criterio.set("Menor distancia")
        self.cb_criterio.grid(row=2, column=1, pady=2)
        for combo in (self.cb_origen, self.cb_destino):
            combo.bind("<<ComboboxSelected>>", lambda _e: self.validar_seleccion_ruta())

        self.lbl_aviso_ruta = ttk.Label(f, foreground="#b00020")
        self.lbl_aviso_ruta.pack(anchor="w", pady=(4, 0))
        self.btn_calcular = ttk.Button(f, text="Calcular ruta", command=self.calcular, state="disabled")
        self.btn_calcular.pack(fill=tk.X, pady=6)

        ttk.Label(f, text="Recorrido", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.lbl_recorrido = ttk.Label(f, wraplength=390, justify="left")
        self.lbl_recorrido.pack(anchor="w", pady=(0, 6))
        self.tabla_tramos = crear_tabla(
            f, [("tramo", "Conexión", 190), ("distancia", "Distancia", 70),
                ("tiempo", "Tiempo", 60), ("costo", "Costo", 75)], 12)
        self.tabla_tramos.pack(fill=tk.BOTH, expand=True)
        self.lbl_totales = ttk.Label(f, font=("Segoe UI", 10, "bold"))
        self.lbl_totales.pack(anchor="w", pady=6)

    def _crear_pestana_historial(self):
        f = ttk.Frame(self.pestanas, padding=6)
        self.pestanas.add(f, text="Historial")

        ttk.Label(f, text="Rutas calculadas, de la más reciente a la más antigua").pack(anchor="w")
        self.tabla_historial = crear_tabla(
            f, [("fecha", "Fecha y hora", 125), ("ruta", "Origen → destino final", 200),
                ("distancia", "Distancia", 70)], 12)
        self.tabla_historial.pack(fill=tk.BOTH, expand=True, pady=4)
        self.tabla_historial.bind("<<TreeviewSelect>>", self._historial_elegido)

        self.txt_historial = tk.Text(f, height=12, wrap="word", state="disabled", relief="flat",
                                     background="#f7f7f7", font=("Segoe UI", 9))
        self.txt_historial.pack(fill=tk.X)

    # ======================= Actualización general =======================

    def refrescar(self):
        """Vuelve a cargar listas, combos y mapa después de un cambio en los datos."""
        nombres = sorted((l["nombre"] for l in self.repo.lugares), key=normalizar)
        for combo in (self.cb_origen, self.cb_destino):
            combo["values"] = nombres
            if combo.get() not in nombres:
                combo.set("")
        cantones = [TODOS] + self.repo.cantones()
        self.cb_canton["values"] = cantones
        if self.cb_canton.get() not in cantones:
            self.cb_canton.set(TODOS)

        self.mapa.cargar(self.repo.lugares, self.repo.conexiones)
        if self.repo.lugar(self.lugar_seleccionado) is None:
            self.lugar_seleccionado = None
            self.mapa.seleccionar(None)
        self.actualizar_listado()
        self.mostrar_ficha()
        self.validar_seleccion_ruta()
        self.actualizar_historial()

    # ======================= Lugares (RF-001 a RF-004, RF-008) =======================

    def actualizar_listado(self):
        canton = self.cb_canton.get()
        categoria = self.cb_categoria.get()
        lugares = filtrar_lugares(
            self.repo.lugares, self.var_busqueda.get(),
            canton=None if canton in ("", TODOS) else canton,
            categoria=None if categoria in ("", TODOS) else categoria,
        )
        self.tabla_lugares.delete(*self.tabla_lugares.get_children())
        for l in lugares:
            self.tabla_lugares.insert("", tk.END, iid=str(l["id"]),
                                      values=(l["nombre"], l["canton"], l["categoria"]))
        if self.lugar_seleccionado is not None and self.tabla_lugares.exists(str(self.lugar_seleccionado)):
            self.tabla_lugares.selection_set(str(self.lugar_seleccionado))

        if not self.repo.lugares:
            self.lbl_listado.config(text="No hay lugares registrados")
        elif not lugares:
            self.lbl_listado.config(text="Sin resultados")
        else:
            self.lbl_listado.config(text=f"{len(lugares)} de {len(self.repo.lugares)} lugares")

        filtrado = len(lugares) != len(self.repo.lugares)
        self.mapa.filtrar({l["id"] for l in lugares} if filtrado else None)

    def quitar_filtros(self):
        self.var_busqueda.set("")
        self.cb_canton.set(TODOS)
        self.cb_categoria.set(TODOS)
        self.actualizar_listado()

    def _lugar_elegido_en_tabla(self, _evento=None):
        seleccion = self.tabla_lugares.selection()
        if seleccion and int(seleccion[0]) != self.lugar_seleccionado:
            self.seleccionar_lugar(int(seleccion[0]))

    def seleccionar_lugar(self, id_lugar):
        self.lugar_seleccionado = id_lugar
        self.pestanas.select(0)
        if self.tabla_lugares.exists(str(id_lugar)):
            self.tabla_lugares.selection_set(str(id_lugar))
            self.tabla_lugares.see(str(id_lugar))
        self.mapa.seleccionar(id_lugar)
        self.mostrar_ficha()

    def mostrar_ficha(self):
        lugar = self.repo.lugar(self.lugar_seleccionado)
        t = self.txt_ficha
        t.config(state="normal")
        t.delete("1.0", tk.END)
        if lugar is None:
            t.insert(tk.END, "Selecciona un lugar en la lista o en el mapa.")
        else:
            t.insert(tk.END, lugar["nombre"] + "\n", "titulo")
            t.insert(tk.END, "Cantón: ", "negrita")
            t.insert(tk.END, lugar["canton"] + "\n")
            t.insert(tk.END, "Categoría: ", "negrita")
            t.insert(tk.END, lugar["categoria"] + "\n\n")
            t.insert(tk.END, lugar["descripcion"] + "\n\n")
            t.insert(tk.END, "Conexiones directas:\n", "negrita")
            vecinos = [(self.repo.lugar(i), c) for i, c in conexiones_de(self.repo.conexiones, lugar["id"])]
            vecinos.sort(key=lambda par: normalizar(par[0]["nombre"]))
            for vecino, c in vecinos:
                t.insert(tk.END, f"• {vecino['nombre']}: {fmt_km(c['distancia_km'])} · "
                                 f"{fmt_min(c['tiempo_min'])} · {fmt_usd(c['costo_usd'])}\n")
            if not vecinos:
                t.insert(tk.END, "  (sin conexiones registradas)\n")
        t.config(state="disabled")

    def _usar_en_ruta(self, combo):
        lugar = self.repo.lugar(self.lugar_seleccionado)
        if lugar is None:
            messagebox.showinfo("Ruta", "Primero selecciona un lugar.")
            return
        combo.set(lugar["nombre"])
        self.validar_seleccion_ruta()
        self.pestanas.select(1)

    # ======================= Ruta (RF-005 a RF-007, RF-014, RF-015) =======================

    def validar_seleccion_ruta(self):
        origen, destino = self.cb_origen.get(), self.cb_destino.get()
        if origen and destino and origen == destino:
            self.lbl_aviso_ruta.config(text="El origen y el destino final deben ser lugares distintos.")
            self.btn_calcular.config(state="disabled")
        elif origen and destino:
            self.lbl_aviso_ruta.config(text="")
            self.btn_calcular.config(state="normal")
        else:
            self.lbl_aviso_ruta.config(text="")
            self.btn_calcular.config(state="disabled")

    def calcular(self):
        origen = self.repo.lugar_por_nombre(self.cb_origen.get())
        destino = self.repo.lugar_por_nombre(self.cb_destino.get())
        if origen is None or destino is None or origen["id"] == destino["id"]:
            self.validar_seleccion_ruta()
            return
        criterio = CRITERIOS_UI[self.cb_criterio.get()]
        resultado = calcular_ruta(self.repo.conexiones, origen["id"], destino["id"], criterio)
        if resultado is None:
            # RF-014: se avisa y no se guarda nada en el historial
            self.limpiar_resultado()
            messagebox.showwarning("Sin ruta", MENSAJE_SIN_RUTA)
            return
        entrada = self.repo.registrar_ruta(resultado)
        self.mostrar_resultado(entrada)
        self.actualizar_historial()

    def limpiar_resultado(self):
        self.lbl_recorrido.config(text="")
        self.lbl_totales.config(text="")
        self.tabla_tramos.delete(*self.tabla_tramos.get_children())
        self._mostrar_ruta_en_mapa([])

    def mostrar_resultado(self, entrada):
        criterio = NOMBRE_CRITERIO.get(entrada["criterio"], entrada["criterio"])
        self.lbl_recorrido.config(text=" → ".join(entrada["lugares"]) + f"\n({criterio.lower()})")
        self.tabla_tramos.delete(*self.tabla_tramos.get_children())
        for t in entrada["tramos"]:
            self.tabla_tramos.insert("", tk.END, values=(
                f"{t['desde']} → {t['hasta']}", fmt_km(t["distancia_km"]),
                fmt_min(t["tiempo_min"]), fmt_usd(t["costo_usd"])))
        self.lbl_totales.config(text=fmt_totales(entrada["totales"]))
        self._mostrar_ruta_en_mapa(entrada["lugares"])

    def _mostrar_ruta_en_mapa(self, nombres):
        lugares = [self.repo.lugar_por_nombre(n) for n in nombres]
        # Si un lugar del historial ya no existe, la ruta no se puede dibujar
        self.ids_ruta_mostrada = [l["id"] for l in lugares] if all(lugares) else []
        self.mapa.mostrar_ruta(self.ids_ruta_mostrada)

    # ======================= Historial (RF-010) =======================

    def actualizar_historial(self):
        self.tabla_historial.delete(*self.tabla_historial.get_children())
        for i, e in enumerate(self.repo.historial):
            self.tabla_historial.insert("", tk.END, iid=str(i), values=(
                e["fecha"], f"{e['origen']} → {e['destino']}", fmt_km(e["totales"]["distancia_km"])))

    def _historial_elegido(self, _evento=None):
        seleccion = self.tabla_historial.selection()
        if not seleccion:
            return
        e = self.repo.historial[int(seleccion[0])]
        t = self.txt_historial
        t.config(state="normal")
        t.delete("1.0", tk.END)
        t.insert(tk.END, f"{e['fecha']} · {NOMBRE_CRITERIO.get(e['criterio'], e['criterio'])}\n")
        t.insert(tk.END, " → ".join(e["lugares"]) + "\n\n")
        for tramo in e["tramos"]:
            t.insert(tk.END, f"• {tramo['desde']} → {tramo['hasta']}: {fmt_km(tramo['distancia_km'])} · "
                             f"{fmt_min(tramo['tiempo_min'])} · {fmt_usd(tramo['costo_usd'])}\n")
        t.insert(tk.END, "\n" + fmt_totales(e["totales"]))
        t.config(state="disabled")
        self._mostrar_ruta_en_mapa(e["lugares"])

    # ======================= Administración (RNF-003, RF-011 a RF-013) =======================

    def abrir_administracion(self):
        if self.ventana_admin is not None and self.ventana_admin.winfo_exists():
            self.ventana_admin.lift()
            return
        clave = simpledialog.askstring("Administración", "Contraseña del administrador:",
                                       show="*", parent=self)
        if clave is None:
            return
        if not self.repo.verificar_contrasena(clave):
            messagebox.showerror("Administración", "Contraseña incorrecta.")
            return
        self.ventana_admin = VentanaAdministracion(self)

    def _clic_vacio_mapa(self, lat, lon):
        if self.ventana_admin is not None and self.ventana_admin.winfo_exists():
            self.ventana_admin.poner_coordenadas(lat, lon)

class VentanaAdministracion(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.repo = app.repo
        self.title("Administración")
        self.geometry("820x540")
        self.id_lugar_edicion = None
        self.id_conexion_edicion = None

        pestanas = ttk.Notebook(self)
        pestanas.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self._crear_lugares(pestanas)
        self._crear_conexiones(pestanas)
        self._crear_contrasena(pestanas)
        self.actualizar_listas()

    # ---------- Lugares ----------

    def _crear_lugares(self, pestanas):
        f = ttk.Frame(pestanas, padding=6)
        pestanas.add(f, text="Lugares")
        self.tabla_lugares = crear_tabla(f, [("nombre", "Nombre", 180), ("canton", "Cantón", 110)], 18)
        self.tabla_lugares.pack(side=tk.LEFT, fill=tk.Y)
        self.tabla_lugares.bind("<<TreeviewSelect>>", self._cargar_lugar)

        form = ttk.Frame(f, padding=(12, 0))
        form.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Label(form, text="Nombre:").grid(row=0, column=0, sticky="w", pady=3)
        self.e_nombre = ttk.Entry(form, width=40)
        self.e_nombre.grid(row=0, column=1, sticky="we")
        ttk.Label(form, text="Cantón:").grid(row=1, column=0, sticky="w", pady=3)
        self.cb_canton = ttk.Combobox(form, width=38)
        self.cb_canton.grid(row=1, column=1, sticky="we")
        ttk.Label(form, text="Categoría:").grid(row=2, column=0, sticky="w", pady=3)
        self.cb_categoria = ttk.Combobox(form, state="readonly", values=CATEGORIAS, width=38)
        self.cb_categoria.grid(row=2, column=1, sticky="we")
        ttk.Label(form, text="Descripción:").grid(row=3, column=0, sticky="nw", pady=3)
        self.txt_descripcion = tk.Text(form, height=5, width=40, wrap="word", font=("Segoe UI", 9))
        self.txt_descripcion.grid(row=3, column=1, sticky="we", pady=3)
        ttk.Label(form, text="Latitud:").grid(row=4, column=0, sticky="w", pady=3)
        self.e_lat = ttk.Entry(form, width=40)
        self.e_lat.grid(row=4, column=1, sticky="we")
        ttk.Label(form, text="Longitud:").grid(row=5, column=0, sticky="w", pady=3)
        self.e_lon = ttk.Entry(form, width=40)
        self.e_lon.grid(row=5, column=1, sticky="we")
        ttk.Label(form, foreground="gray", wraplength=380, justify="left",
                  text="Consejo: con esta ventana abierta, haz clic en un punto vacío del mapa "
                       "principal para copiar sus coordenadas.").grid(row=6, column=0, columnspan=2,
                                                                      sticky="w", pady=6)
        botones = ttk.Frame(form)
        botones.grid(row=7, column=0, columnspan=2, sticky="we", pady=6)
        ttk.Button(botones, text="Nuevo", command=self._limpiar_lugar).pack(side=tk.LEFT)
        ttk.Button(botones, text="Guardar", command=self._guardar_lugar).pack(side=tk.LEFT, padx=6)
        ttk.Button(botones, text="Eliminar", command=self._eliminar_lugar).pack(side=tk.LEFT)

    def _limpiar_lugar(self):
        self.id_lugar_edicion = None
        self.tabla_lugares.selection_remove(*self.tabla_lugares.selection())
        for entrada in (self.e_nombre, self.e_lat, self.e_lon):
            entrada.delete(0, tk.END)
        self.cb_canton.set("")
        self.cb_categoria.set("")
        self.txt_descripcion.delete("1.0", tk.END)

    def _cargar_lugar(self, _evento=None):
        seleccion = self.tabla_lugares.selection()
        if not seleccion:
            return
        lugar = self.repo.lugar(int(seleccion[0]))
        self._limpiar_lugar()
        self.id_lugar_edicion = lugar["id"]
        self.e_nombre.insert(0, lugar["nombre"])
        self.cb_canton.set(lugar["canton"])
        self.cb_categoria.set(lugar["categoria"])
        self.txt_descripcion.insert("1.0", lugar["descripcion"])
        self.e_lat.insert(0, str(lugar["lat"]))
        self.e_lon.insert(0, str(lugar["lon"]))

    def poner_coordenadas(self, lat, lon):
        self.e_lat.delete(0, tk.END)
        self.e_lat.insert(0, str(lat))
        self.e_lon.delete(0, tk.END)
        self.e_lon.insert(0, str(lon))
        self.lift()

    def _guardar_lugar(self):
        datos = {
            "nombre": self.e_nombre.get(), "canton": self.cb_canton.get(),
            "categoria": self.cb_categoria.get(), "descripcion": self.txt_descripcion.get("1.0", tk.END),
            "lat": self.e_lat.get(), "lon": self.e_lon.get(),
        }
        try:
            if self.id_lugar_edicion is None:
                self.id_lugar_edicion = self.repo.agregar_lugar(datos)["id"]
            else:
                self.repo.editar_lugar(self.id_lugar_edicion, datos)
        except ErrorValidacion as error:
            messagebox.showerror("Datos no válidos", str(error), parent=self)
            return
        self._despues_de_cambio()
        messagebox.showinfo("Lugares", "Lugar guardado.", parent=self)

    def _eliminar_lugar(self):
        lugar = self.repo.lugar(self.id_lugar_edicion)
        if lugar is None:
            messagebox.showinfo("Eliminar", "Selecciona un lugar de la lista.", parent=self)
            return
        cantidad = len(conexiones_de(self.repo.conexiones, lugar["id"]))
        if messagebox.askyesno("Eliminar", f"¿Eliminar «{lugar['nombre']}»?\n"
                                           f"También se eliminarán sus {cantidad} conexiones.", parent=self):
            self.repo.eliminar_lugar(lugar["id"])
            self._limpiar_lugar()
            self._despues_de_cambio()

    # ---------- Conexiones ----------

    def _crear_conexiones(self, pestanas):
        f = ttk.Frame(pestanas, padding=6)
        pestanas.add(f, text="Conexiones")
        self.tabla_conexiones = crear_tabla(
            f, [("a", "Lugar A", 150), ("b", "Lugar B", 150), ("km", "Km", 50),
                ("min", "Min", 50), ("usd", "Costo", 60)], 18)
        self.tabla_conexiones.pack(side=tk.LEFT, fill=tk.Y)
        self.tabla_conexiones.bind("<<TreeviewSelect>>", self._cargar_conexion)

        form = ttk.Frame(f, padding=(12, 0))
        form.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Label(form, text="Lugar A:").grid(row=0, column=0, sticky="w", pady=3)
        self.cb_a = ttk.Combobox(form, state="readonly", width=28)
        self.cb_a.grid(row=0, column=1, sticky="we")
        ttk.Label(form, text="Lugar B:").grid(row=1, column=0, sticky="w", pady=3)
        self.cb_b = ttk.Combobox(form, state="readonly", width=28)
        self.cb_b.grid(row=1, column=1, sticky="we")
        ttk.Label(form, text="Distancia (km):").grid(row=2, column=0, sticky="w", pady=3)
        self.e_distancia = ttk.Entry(form, width=30)
        self.e_distancia.grid(row=2, column=1, sticky="we")
        ttk.Button(form, text="Medir por carretera", command=self._medir_por_carretera,
                   state="normal" if self.app.red_vial else "disabled").grid(row=2, column=2, padx=4)
        ttk.Label(form, text="Tiempo (min):").grid(row=3, column=0, sticky="w", pady=3)
        self.e_tiempo = ttk.Entry(form, width=30)
        self.e_tiempo.grid(row=3, column=1, sticky="we")
        ttk.Label(form, text="Costo (USD):").grid(row=4, column=0, sticky="w", pady=3)
        self.e_costo = ttk.Entry(form, width=30)
        self.e_costo.grid(row=4, column=1, sticky="we")
        ttk.Label(form, foreground="gray", wraplength=260, justify="left",
                  text="La conexión vale en ambos sentidos. Tiempo y costo son opcionales: si se dejan "
                       "vacíos se mostrarán como «no disponible».").grid(row=5, column=0, columnspan=2,
                                                                         sticky="w", pady=6)
        botones = ttk.Frame(form)
        botones.grid(row=6, column=0, columnspan=2, sticky="we", pady=6)
        ttk.Button(botones, text="Nueva", command=self._limpiar_conexion).pack(side=tk.LEFT)
        ttk.Button(botones, text="Guardar", command=self._guardar_conexion).pack(side=tk.LEFT, padx=6)
        ttk.Button(botones, text="Eliminar", command=self._eliminar_conexion).pack(side=tk.LEFT)

    def _limpiar_conexion(self):
        self.id_conexion_edicion = None
        self.tabla_conexiones.selection_remove(*self.tabla_conexiones.selection())
        self.cb_a.set("")
        self.cb_b.set("")
        for entrada in (self.e_distancia, self.e_tiempo, self.e_costo):
            entrada.delete(0, tk.END)

    def _cargar_conexion(self, _evento=None):
        seleccion = self.tabla_conexiones.selection()
        if not seleccion:
            return
        c = self.repo.conexion(int(seleccion[0]))
        self._limpiar_conexion()
        self.id_conexion_edicion = c["id"]
        self.cb_a.set(self.repo.lugar(c["origen"])["nombre"])
        self.cb_b.set(self.repo.lugar(c["destino"])["nombre"])
        for entrada, valor in ((self.e_distancia, c["distancia_km"]), (self.e_tiempo, c["tiempo_min"]),
                               (self.e_costo, c["costo_usd"])):
            if valor is not None:
                entrada.insert(0, f"{valor:g}")

    def _medir_por_carretera(self):
        a = self.repo.lugar_por_nombre(self.cb_a.get())
        b = self.repo.lugar_por_nombre(self.cb_b.get())
        if a is None or b is None or a["id"] == b["id"]:
            messagebox.showinfo("Medir", "Elige dos lugares distintos.", parent=self)
            return
        trazado = self.app.red_vial.trazar((a["lat"], a["lon"]), (b["lat"], b["lon"]))
        self.e_distancia.delete(0, tk.END)
        self.e_distancia.insert(0, f"{trazado['km']:g}")
        if trazado["acceso_km"] > 3:
            messagebox.showinfo("Medir", f"Incluye {trazado['acceso_km']:g} km en línea recta entre los "
                                         "lugares y la carretera principal más cercana.", parent=self)

    def _guardar_conexion(self):
        a = self.repo.lugar_por_nombre(self.cb_a.get())
        b = self.repo.lugar_por_nombre(self.cb_b.get())
        datos = {
            "origen": a["id"] if a else None, "destino": b["id"] if b else None,
            "distancia_km": self.e_distancia.get(), "tiempo_min": self.e_tiempo.get(),
            "costo_usd": self.e_costo.get(),
        }
        try:
            if self.id_conexion_edicion is None:
                self.id_conexion_edicion = self.repo.agregar_conexion(datos)["id"]
            else:
                self.repo.editar_conexion(self.id_conexion_edicion, datos)
        except ErrorValidacion as error:
            messagebox.showerror("Datos no válidos", str(error), parent=self)
            return
        self._despues_de_cambio()
        messagebox.showinfo("Conexiones", "Conexión guardada.", parent=self)

    def _eliminar_conexion(self):
        if self.repo.conexion(self.id_conexion_edicion) is None:
            messagebox.showinfo("Eliminar", "Selecciona una conexión de la lista.", parent=self)
            return
        if messagebox.askyesno("Eliminar", "¿Eliminar la conexión seleccionada?", parent=self):
            self.repo.eliminar_conexion(self.id_conexion_edicion)
            self._limpiar_conexion()
            self._despues_de_cambio()

    # ---------- Contraseña ----------

    def _crear_contrasena(self, pestanas):
        f = ttk.Frame(pestanas, padding=12)
        pestanas.add(f, text="Contraseña")
        ttk.Label(f, text="Nueva contraseña:").grid(row=0, column=0, sticky="w", pady=4)
        self.e_nueva = ttk.Entry(f, show="*", width=30)
        self.e_nueva.grid(row=0, column=1)
        ttk.Label(f, text="Repetir contraseña:").grid(row=1, column=0, sticky="w", pady=4)
        self.e_repetir = ttk.Entry(f, show="*", width=30)
        self.e_repetir.grid(row=1, column=1)
        ttk.Button(f, text="Cambiar contraseña", command=self._cambiar_contrasena).grid(
            row=2, column=1, sticky="e", pady=8)

    def _cambiar_contrasena(self):
        if self.e_nueva.get() != self.e_repetir.get():
            messagebox.showerror("Contraseña", "Las contraseñas no coinciden.", parent=self)
            return
        try:
            self.repo.cambiar_contrasena(self.e_nueva.get())
        except ErrorValidacion as error:
            messagebox.showerror("Contraseña", str(error), parent=self)
            return
        self.e_nueva.delete(0, tk.END)
        self.e_repetir.delete(0, tk.END)
        messagebox.showinfo("Contraseña", "Contraseña actualizada.", parent=self)

    # ---------- Común ----------

    def actualizar_listas(self):
        self.tabla_lugares.delete(*self.tabla_lugares.get_children())
        for l in sorted(self.repo.lugares, key=lambda l: normalizar(l["nombre"])):
            self.tabla_lugares.insert("", tk.END, iid=str(l["id"]), values=(l["nombre"], l["canton"]))
        self.cb_canton["values"] = self.repo.cantones()

        nombres = sorted((l["nombre"] for l in self.repo.lugares), key=normalizar)
        self.cb_a["values"] = nombres
        self.cb_b["values"] = nombres
        self.tabla_conexiones.delete(*self.tabla_conexiones.get_children())
        for c in self.repo.conexiones:
            self.tabla_conexiones.insert("", tk.END, iid=str(c["id"]), values=(
                self.repo.lugar(c["origen"])["nombre"], self.repo.lugar(c["destino"])["nombre"],
                f"{c['distancia_km']:g}",
                "—" if c["tiempo_min"] is None else f"{c['tiempo_min']:g}",
                "—" if c["costo_usd"] is None else f"{c['costo_usd']:.2f}"))

    def _despues_de_cambio(self):
        self.actualizar_listas()
        self.app.refrescar()
