"""Pruebas de la lógica de puntuación y del ciclo de vida de las ofertas (sin red)."""

from datetime import date

import pytest

import config
from agentes import almacen, archivero, tasador


def resultado(destino="FCO", precio=72, ida="2026-12-11", vuelta="2026-12-14", tipico=148,
              rango=(105, 240), min60=44, escalas=0, perfil="escapada"):
    ciudad, ref = config.PERFILES[perfil]["destinos"][destino]
    return {
        "perfil": perfil, "destino": destino, "ciudad": ciudad, "precio_ref": ref,
        "ida": ida, "vuelta": vuelta, "precio_persona": precio, "aerolineas": ["Wizz Air"],
        "escalas": escalas, "minutos_vuelo": 150, "hora_salida": "20:40", "enlace": "https://x",
        "google_tipico": tipico, "google_rango": list(rango), "google_min_60d": min60,
    }


# --- tasador ---

def test_precio_muy_por_debajo_de_lo_habitual_es_excelente():
    puntos, desglose, _ = tasador.puntuar(resultado(precio=72))
    assert puntos >= config.UMBRAL_AVISO
    assert tasador.valoracion(puntos) == "excelente"


def test_precio_tipico_es_normal():
    puntos, _, _ = tasador.puntuar(resultado(destino="PMI", precio=37, tipico=37, rango=(30, 45), min60=34))
    assert tasador.valoracion(puntos) == "normal"


def test_precio_por_encima_del_rango_es_caro():
    puntos, _, _ = tasador.puntuar(resultado(precio=260, escalas=1))
    assert tasador.valoracion(puntos) == "caro"


def test_sin_datos_de_google_usa_precio_de_referencia():
    r = resultado(precio=60)
    del r["google_tipico"], r["google_rango"], r["google_min_60d"]
    _, _, refs = tasador.puntuar(r)
    assert refs["base_comparacion"] == "referencia"
    assert refs["tipico"] == config.PERFILES["escapada"]["destinos"]["FCO"][1]


def test_escalas_penalizan_menos_en_largo_radio():
    corto, _, _ = tasador.puntuar(resultado(escalas=1))
    largo, _, _ = tasador.puntuar(resultado(escalas=1), largo_radio=True)
    assert largo > corto


# --- ciclo de vida ---

class BuscadorFalso:
    """Devuelve el precio configurado para cada destino, o None si 'desaparece'."""

    def __init__(self, precios):
        self.precios = precios
        self.log = lambda m: None

    def buscar(self, perfil, destino, ida, vuelta):
        precio = self.precios.get(destino)
        if precio is None:
            return None
        return resultado(destino=destino, precio=precio, ida=ida.isoformat(), vuelta=vuelta.isoformat())


@pytest.fixture
def db(tmp_path):
    return almacen.conectar(tmp_path / "test.db")


def test_oferta_excelente_se_confirma_y_se_avisa_una_sola_vez(db):
    nuevas = archivero.registrar(db, [resultado(precio=72)], "t1")
    assert len(nuevas) == 1
    # recién descubierta: aún no se avisa hasta confirmarla
    assert archivero.para_avisar(db) == []
    archivero.verificar(db, BuscadorFalso({"FCO": 72}), "t1")
    pendientes = archivero.para_avisar(db)
    assert len(pendientes) == 1
    archivero.marcar_avisadas(db, pendientes, "t1")
    # al día siguiente sigue igual: no se repite el aviso
    archivero.registrar(db, [resultado(precio=72)], "t2")
    assert archivero.para_avisar(db) == []
    # pero si baja más, se vuelve a avisar
    archivero.registrar(db, [resultado(precio=60)], "t3")
    assert len(archivero.para_avisar(db)) == 1


def test_precio_normal_no_entra_en_el_catalogo(db):
    assert archivero.registrar(db, [resultado(precio=150)], "t1") == []
    assert db.execute("SELECT COUNT(*) FROM ofertas").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM observaciones").fetchone()[0] == 1


def test_oferta_caduca_si_sube_de_precio(db):
    archivero.registrar(db, [resultado(precio=72)], "t1")
    archivero.verificar(db, BuscadorFalso({"FCO": 200}), "t2")
    o = db.execute("SELECT * FROM ofertas").fetchone()
    assert o["estado"] == "caducada" and o["motivo_cierre"] == "Ha subido de precio"
    assert o["precio_minimo"] == 72


def test_oferta_caduca_si_desaparece_varias_veces(db):
    archivero.registrar(db, [resultado(precio=72)], "t1")
    archivero.verificar(db, BuscadorFalso({}), "t2")
    assert db.execute("SELECT estado FROM ofertas").fetchone()[0] == "activa"
    archivero.verificar(db, BuscadorFalso({}), "t3")
    assert db.execute("SELECT estado FROM ofertas").fetchone()[0] == "caducada"


def test_oferta_caduca_cuando_se_acerca_la_fecha(db):
    archivero.registrar(db, [resultado(precio=72, ida="2026-12-11")], "t1")
    archivero.caducar_por_fecha(db, date(2026, 12, 10), "t2")
    assert db.execute("SELECT motivo_cierre FROM ofertas").fetchone()[0] == "Fecha de salida demasiado cercana"
