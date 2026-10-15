# Rutas turísticas de Manabí

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
