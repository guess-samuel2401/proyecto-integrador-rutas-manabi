<div align="center">

# 🗺️ Rutas turísticas de Manabí

**Planificador de rutas turísticas en Manabí, Ecuador: ruta más corta, rápida o barata con Dijkstra, sobre un mapa de OpenStreetMap y sin internet.**

[![Release](https://img.shields.io/github/v/release/guess-samuel2401/proyecto-integrador-rutas-manabi?style=flat-square&label=versi%C3%B3n&color=0b7285)](https://github.com/guess-samuel2401/proyecto-integrador-rutas-manabi/releases/latest)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![Tkinter](https://img.shields.io/badge/Tkinter-GUI-4B8BBE?style=flat-square)
![OpenStreetMap](https://img.shields.io/badge/OpenStreetMap-ODbL-7EBC6F?style=flat-square&logo=openstreetmap&logoColor=white)
![algoritmo](https://img.shields.io/badge/algoritmo-Dijkstra-6f42c1?style=flat-square)

</div>

Aplicación de escritorio para consultar lugares turísticos de la provincia de Manabí (Ecuador) y calcular la ruta de menor distancia, tiempo o costo entre dos de ellos. Funciona **sin conexión a internet**.

Proyecto integrador de la asignatura Ingeniería de Requisitos, Ingeniería en Software, Universidad Laica Eloy Alfaro de Manabí (periodo 2026-2).

## Descargar y usar

1. Ve a [**Releases**](../../releases/latest) y descarga `RutasManabi.exe`.
2. Ábrelo con doble clic. No necesita instalar Python ni nada más.

La primera vez, Windows puede mostrar "Windows protegió su PC" porque el programa no está firmado digitalmente. Pulsa **Más información → Ejecutar de todas formas**.

El programa crea una carpeta `datos/` junto al `.exe`, donde guarda los lugares, las conexiones, el historial y la contraseña del administrador.

**Contraseña inicial del administrador:** `admin123`. Cámbiala desde *Administración → Contraseña*.

## Funciones

| Pestaña o botón | Qué hace |
|---|---|
| Lugares | Lista, búsqueda (sin distinguir tildes ni mayúsculas), filtros por cantón y categoría, y la ficha de cada lugar con sus conexiones directas |
| Ruta | Elige origen y destino final, y calcula la ruta por menor distancia, tiempo o costo, con el detalle de cada tramo y los totales |
| Historial | Rutas calculadas, de la más reciente a la más antigua; se conservan al cerrar el programa |
| Mapa | Mapa de Manabí con costa, ríos, carreteras y poblados; la ruta se dibuja siguiendo las carreteras |
| Administración | Protegida con contraseña: agrega, edita y elimina lugares y conexiones, con validación de datos |

## Ejecutar desde el código fuente

Requiere Python 3.10 o superior (Tkinter viene incluido en el instalador de Windows).

En Windows basta con hacer doble clic en `ejecutar_codigo.bat`. Desde una terminal:

```
python main.py                       # abrir el programa
python -m unittest pruebas -v        # pruebas de los criterios de aceptación
construir.bat                        # generar dist\RutasManabi.exe (requiere: pip install pyinstaller)
```

## Estructura

| Archivo | Contenido |
|---|---|
| `main.py` | Punto de entrada |
| `interfaz.py`, `mapa.py` | Interfaz gráfica en Tkinter |
| `rutas.py` | Búsqueda, filtros y cálculo de la ruta (algoritmo de Dijkstra) |
| `red_vial.py` | Trazado de las rutas por carretera |
| `datos.py` | Lectura y escritura de los archivos JSON y validación de datos |
| `datos/lugares.json`, `datos/conexiones.json` | Lugares turísticos y conexiones entre ellos (editables sin tocar el código) |
| `datos/mapa_base.json` | Capas del mapa extraídas de OpenStreetMap |
| `descargar_mapa.py` | Herramienta que generó `mapa_base.json`; el programa no la usa al ejecutarse |
| `pruebas.py` | Pruebas automáticas |

## Sobre los datos

- Las coordenadas de los lugares se verificaron con OpenStreetMap. Las distancias de las conexiones se midieron por las carreteras principales. Los **tiempos y costos son estimaciones referenciales** del equipo y deben validarse con fuentes oficiales.
- Solo se incluyen carreteras troncales, primarias y secundarias, por lo que algunas distancias pueden ser mayores que por caminos locales.

## Atribución del mapa

Datos del mapa © [colaboradores de OpenStreetMap](https://www.openstreetmap.org/copyright), disponibles bajo la licencia [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/). El archivo `datos/mapa_base.json` es una base de datos derivada y se distribuye bajo la misma licencia ODbL.
