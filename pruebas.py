"""Pruebas de los criterios de aceptación (sección 8) y RNF verificables (sección 6).

Ejecutar con:  python -m unittest pruebas -v
"""
import random
import tempfile
import time
import unittest

from datos import CARPETA_DATOS, ErrorValidacion, Repositorio, cargar_mapa_base
from red_vial import RedVial, distancia_km
from rutas import calcular_ruta, filtrar_lugares


def lugar(nombre, canton="Manta", categoria="playa"):
    return {"nombre": nombre, "canton": canton, "categoria": categoria,
            "descripcion": "Descripción de prueba", "lat": -1.0, "lon": -80.5}


class ConRepositorioTemporal(unittest.TestCase):
    def setUp(self):
        self.carpeta = tempfile.TemporaryDirectory()
        self.repo = Repositorio(self.carpeta.name)

    def tearDown(self):
        self.carpeta.cleanup()

    def conectar(self, a, b, km, minutos=10, costo=1.0):
        return self.repo.agregar_conexion({"origen": a["id"], "destino": b["id"], "distancia_km": km,
                                           "tiempo_min": minutos, "costo_usd": costo})


class PruebasConsulta(ConRepositorioTemporal):
    def test_ca_001_1_lista_todos(self):
        for i in range(20):
            self.repo.agregar_lugar(lugar(f"Lugar {i}"))
        self.assertEqual(len(filtrar_lugares(self.repo.lugares)), 20)

    def test_ca_002_1_busqueda_sin_tildes_ni_mayusculas(self):
        self.repo.agregar_lugar(lugar("Playa Murciélago"))
        nombres = [l["nombre"] for l in filtrar_lugares(self.repo.lugares, "murcielago")]
        self.assertEqual(nombres, ["Playa Murciélago"])

    def test_ca_002_2_sin_resultados(self):
        self.repo.agregar_lugar(lugar("Playa Murciélago"))
        self.assertEqual(filtrar_lugares(self.repo.lugares, "xyz"), [])

    def test_ca_003_filtros(self):
        self.repo.agregar_lugar(lugar("A", "Manta", "playa"))
        self.repo.agregar_lugar(lugar("B", "Manta", "cultural"))
        self.repo.agregar_lugar(lugar("C", "Portoviejo", "playa"))
        self.assertEqual({l["nombre"] for l in filtrar_lugares(self.repo.lugares, canton="Manta")}, {"A", "B"})
        self.assertEqual([l["nombre"] for l in filtrar_lugares(self.repo.lugares, canton="Manta",
                                                               categoria="playa")], ["A"])
        self.assertEqual(len(filtrar_lugares(self.repo.lugares)), 3)


class PruebasRutas(ConRepositorioTemporal):
    def setUp(self):
        super().setUp()
        self.a = self.repo.agregar_lugar(lugar("A"))
        self.b = self.repo.agregar_lugar(lugar("B"))
        self.c = self.repo.agregar_lugar(lugar("C"))

    def test_ca_006_1_ruta_mas_corta_con_intermedio(self):
        self.conectar(self.a, self.b, 10)
        self.conectar(self.b, self.c, 10)
        self.conectar(self.a, self.c, 30)
        r = calcular_ruta(self.repo.conexiones, self.a["id"], self.c["id"])
        self.assertEqual(r["lugares"], [self.a["id"], self.b["id"], self.c["id"]])
        self.assertEqual(r["totales"]["distancia_km"], 20)

    def test_ca_006_2_conexion_directa(self):
        self.conectar(self.a, self.b, 10)
        r = calcular_ruta(self.repo.conexiones, self.a["id"], self.b["id"])
        self.assertEqual(r["lugares"], [self.a["id"], self.b["id"]])

    def test_ca_007_2_totales_igual_a_suma(self):
        self.conectar(self.a, self.b, 12.5, 20, 0.75)
        self.conectar(self.b, self.c, 7.5, 15, 0.5)
        r = calcular_ruta(self.repo.conexiones, self.a["id"], self.c["id"])
        self.assertEqual(r["totales"], {"distancia_km": 20, "tiempo_min": 35, "costo_usd": 1.25})

    def test_ca_007_3_costo_no_disponible(self):
        self.conectar(self.a, self.b, 10, 10, None)
        self.conectar(self.b, self.c, 10, 10, 1.0)
        r = calcular_ruta(self.repo.conexiones, self.a["id"], self.c["id"])
        self.assertIsNone(r["tramos"][0]["costo_usd"])
        self.assertIsNone(r["totales"]["costo_usd"])

    def test_ca_011_1_conexion_en_ambos_sentidos(self):
        self.conectar(self.a, self.b, 10)
        self.assertIsNotNone(calcular_ruta(self.repo.conexiones, self.b["id"], self.a["id"]))

    def test_ca_013_1_no_existe_ruta(self):
        self.conectar(self.a, self.b, 10)
        self.assertIsNone(calcular_ruta(self.repo.conexiones, self.a["id"], self.c["id"]))

    def test_ca_005_2_mismo_origen_y_destino(self):
        with self.assertRaises(ValueError):
            calcular_ruta(self.repo.conexiones, self.a["id"], self.a["id"])

    def test_ca_014_1_menor_tiempo(self):
        self.conectar(self.a, self.c, 10, minutos=60)
        self.conectar(self.a, self.b, 20, minutos=10)
        self.conectar(self.b, self.c, 20, minutos=10)
        r = calcular_ruta(self.repo.conexiones, self.a["id"], self.c["id"], "tiempo")
        self.assertEqual(r["totales"]["tiempo_min"], 20)
        r = calcular_ruta(self.repo.conexiones, self.a["id"], self.c["id"], "distancia")
        self.assertEqual(r["totales"]["distancia_km"], 10)

    def test_rnf_004_resultado_repetible(self):
        self.conectar(self.a, self.b, 10)
        self.conectar(self.b, self.c, 10)
        self.conectar(self.a, self.c, 20)
        resultados = [calcular_ruta(self.repo.conexiones, self.a["id"], self.c["id"]) for _ in range(10)]
        self.assertTrue(all(r == resultados[0] for r in resultados))


class PruebasHistorialYAdministracion(ConRepositorioTemporal):
    def test_ca_009_historial_persistente_y_mas_reciente_primero(self):
        a = self.repo.agregar_lugar(lugar("A"))
        b = self.repo.agregar_lugar(lugar("B"))
        c = self.repo.agregar_lugar(lugar("C"))
        self.conectar(a, b, 10)
        self.conectar(b, c, 10)
        self.repo.registrar_ruta(calcular_ruta(self.repo.conexiones, a["id"], b["id"]))
        self.repo.registrar_ruta(calcular_ruta(self.repo.conexiones, a["id"], c["id"]))
        reabierto = Repositorio(self.carpeta.name)
        self.assertEqual(len(reabierto.historial), 2)
        self.assertEqual(reabierto.historial[0]["destino"], "C")

    def test_ca_010_2_eliminar_lugar_elimina_conexiones(self):
        a = self.repo.agregar_lugar(lugar("A"))
        b = self.repo.agregar_lugar(lugar("B"))
        self.conectar(a, b, 10)
        self.repo.eliminar_lugar(a["id"])
        self.assertIsNone(self.repo.lugar(a["id"]))
        self.assertEqual(self.repo.conexiones, [])

    def test_ca_012_1_nombre_vacio_o_duplicado(self):
        self.repo.agregar_lugar(lugar("Playa Murciélago"))
        with self.assertRaisesRegex(ErrorValidacion, "^Nombre"):
            self.repo.agregar_lugar(lugar(""))
        with self.assertRaisesRegex(ErrorValidacion, "^Nombre"):
            self.repo.agregar_lugar(lugar("playa murcielago"))

    def test_ca_012_2_distancia_cero_o_negativa(self):
        a = self.repo.agregar_lugar(lugar("A"))
        b = self.repo.agregar_lugar(lugar("B"))
        for distancia in (0, -5):
            with self.assertRaisesRegex(ErrorValidacion, "^Distancia"):
                self.conectar(a, b, distancia)

    def test_rnf_003_contrasena(self):
        self.assertTrue(self.repo.verificar_contrasena("admin123"))
        self.assertFalse(self.repo.verificar_contrasena("otra"))
        self.repo.cambiar_contrasena("nueva123")
        self.assertTrue(Repositorio(self.carpeta.name).verificar_contrasena("nueva123"))


class PruebasRendimiento(unittest.TestCase):
    def test_rnf_002_100_lugares_500_conexiones(self):
        azar = random.Random(1)
        lugares = [{"id": i, "nombre": f"Lugar {i}", "canton": "Manta", "categoria": "playa"}
                   for i in range(1, 101)]
        conexiones = [{"id": i, "origen": azar.randint(1, 100), "destino": azar.randint(1, 100),
                       "distancia_km": azar.randint(1, 100), "tiempo_min": 10, "costo_usd": 1.0}
                      for i in range(500)]
        inicio = time.perf_counter()
        filtrar_lugares(lugares, "lugar 5", canton="Manta")
        self.assertLess(time.perf_counter() - inicio, 1)
        inicio = time.perf_counter()
        calcular_ruta(conexiones, 1, 100)
        self.assertLess(time.perf_counter() - inicio, 2)


class PruebasRedVial(unittest.TestCase):
    def setUp(self):
        # Dos caminos de A a C: directo (3 km) o pasando por B (1 + 1 km). Un tramo suelto D-E.
        nodos = [[0, 0], [0, 0.01], [0, 0.02], [1, 1], [1, 1.01]]
        tramos = [
            {"a": 0, "b": 2, "km": 3.0, "puntos": [[0, 0], [0.005, 0.01], [0, 0.02]]},
            {"a": 0, "b": 1, "km": 1.0, "puntos": [[0, 0], [0, 0.01]]},
            {"a": 2, "b": 1, "km": 1.0, "puntos": [[0, 0.02], [0, 0.01]]},
            {"a": 3, "b": 4, "km": 1.0, "puntos": [[1, 1], [1, 1.01]]},
        ]
        self.red = RedVial(nodos, tramos)

    def test_sigue_el_camino_mas_corto_por_carretera(self):
        r = self.red.trazar((0, 0), (0, 0.02))
        self.assertEqual(r["puntos"], [[0, 0], [0, 0], [0, 0.01], [0, 0.02], [0, 0.02]])
        self.assertEqual(r["km"], 2.0)

    def test_suma_el_acceso_hasta_la_carretera(self):
        r = self.red.trazar((0.01, 0), (0, 0.02))  # el origen está ~1,1 km al norte de la vía
        self.assertAlmostEqual(r["acceso_km"], 1.1, places=1)
        self.assertAlmostEqual(r["km"], 3.1, places=1)

    def test_ignora_tramos_desconectados(self):
        self.assertEqual(self.red.nodo_cercano((1, 1)), 2)


class PruebasDatosReales(unittest.TestCase):
    def test_conexiones_tienen_trazado_por_carretera(self):
        red = RedVial.desde_mapa_base(cargar_mapa_base(CARPETA_DATOS))
        repo = Repositorio(CARPETA_DATOS)
        for c in repo.conexiones:
            a, b = repo.lugar(c["origen"]), repo.lugar(c["destino"])
            trazado = red.trazar((a["lat"], a["lon"]), (b["lat"], b["lon"]))
            self.assertGreater(len(trazado["puntos"]), 2)
            self.assertGreaterEqual(trazado["km"], distancia_km((a["lat"], a["lon"]), (b["lat"], b["lon"])))

    def test_lugares_dentro_del_mapa_base(self):
        mapa = cargar_mapa_base(CARPETA_DATOS)
        self.assertIsNotNone(mapa, "Falta datos/mapa_base.json (ejecutar descargar_mapa.py)")
        r = mapa["recuadro"]
        for l in Repositorio(CARPETA_DATOS).lugares:
            self.assertTrue(r["sur"] <= l["lat"] <= r["norte"] and r["oeste"] <= l["lon"] <= r["este"],
                            f"{l['nombre']} queda fuera del mapa")

    def test_todos_los_lugares_estan_conectados(self):
        repo = Repositorio(CARPETA_DATOS)
        ids = [l["id"] for l in repo.lugares]
        for destino in ids[1:]:
            self.assertIsNotNone(calcular_ruta(repo.conexiones, ids[0], destino),
                                 f"Sin ruta hasta {repo.lugar(destino)['nombre']}")


if __name__ == "__main__":
    unittest.main()
