"""Almacén: base de datos SQLite con el catálogo de ofertas y su historial.

Tablas:
  observaciones   cada precio visto en cada búsqueda (materia prima del análisis)
  ofertas         catálogo de ofertas buenas, con su estado (activa / caducada)
  precios_oferta  evolución del precio y la puntuación de cada oferta
  ejecuciones     registro de cada ejecución, para el vigilante
"""

import json
import sqlite3
from pathlib import Path

RUTA = Path(__file__).resolve().parent.parent / "data" / "chollos.db"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS observaciones (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    perfil TEXT NOT NULL, destino TEXT NOT NULL, ida TEXT NOT NULL, vuelta TEXT NOT NULL,
    precio INTEGER NOT NULL, tipico INTEGER, rango_bajo INTEGER, rango_alto INTEGER, min60 INTEGER,
    escalas INTEGER, aerolineas TEXT, puntuacion INTEGER
);
CREATE INDEX IF NOT EXISTS obs_ruta ON observaciones (perfil, destino, ida);

CREATE TABLE IF NOT EXISTS ofertas (
    id TEXT PRIMARY KEY,                 -- perfil|destino|ida|vuelta
    perfil TEXT NOT NULL, destino TEXT NOT NULL, ciudad TEXT NOT NULL,
    ida TEXT NOT NULL, vuelta TEXT NOT NULL,
    estado TEXT NOT NULL,                -- activa | caducada
    motivo_cierre TEXT,
    descubierta TEXT NOT NULL, ultima_verificacion TEXT, cerrada TEXT,
    precio_inicial INTEGER NOT NULL, precio_actual INTEGER NOT NULL, precio_minimo INTEGER NOT NULL,
    puntuacion INTEGER NOT NULL, puntuacion_max INTEGER NOT NULL, valoracion TEXT NOT NULL,
    desglose TEXT,                       -- JSON con los puntos de cada criterio
    tipico INTEGER, rango_bajo INTEGER, rango_alto INTEGER, min60 INTEGER, base_comparacion TEXT,
    escalas INTEGER, aerolineas TEXT, minutos_vuelo INTEGER, hora_salida TEXT, enlace TEXT,
    verificaciones INTEGER NOT NULL DEFAULT 0,
    fallos_seguidos INTEGER NOT NULL DEFAULT 0,
    avisada_precio INTEGER, avisada_ts TEXT
);
CREATE INDEX IF NOT EXISTS ofertas_estado ON ofertas (estado);

CREATE TABLE IF NOT EXISTS precios_oferta (
    oferta_id TEXT NOT NULL, ts TEXT NOT NULL, precio INTEGER NOT NULL, puntuacion INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS precios_oferta_id ON precios_oferta (oferta_id);

CREATE TABLE IF NOT EXISTS ejecuciones (
    id INTEGER PRIMARY KEY,
    inicio TEXT NOT NULL, fin TEXT,
    busquedas INTEGER, resultados INTEGER, errores INTEGER,
    nuevas INTEGER, caducadas INTEGER, avisos INTEGER,
    estado TEXT, notas TEXT
);
"""


def conectar(ruta=RUTA):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(ruta)
    db.row_factory = sqlite3.Row
    db.executescript(ESQUEMA)
    return db


def fila_a_dict(fila):
    d = dict(fila)
    for campo in ("aerolineas", "desglose"):
        if d.get(campo):
            d[campo] = json.loads(d[campo])
    return d
