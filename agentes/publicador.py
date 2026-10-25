"""Agente publicador: vuelca el catálogo a web/datos.js para la web."""

import json
from pathlib import Path

import config
from agentes import tasador
from agentes.almacen import fila_a_dict

DATOS_WEB = Path(__file__).resolve().parent.parent / "web" / "datos.js"
MAX_HISTORICO = 150


def publicar(db, ofertas_web, actualizado):
    precios = {}
    for f in db.execute("SELECT oferta_id, ts, precio FROM precios_oferta ORDER BY ts"):
        precios.setdefault(f["oferta_id"], []).append([f["ts"][:10], f["precio"]])

    def con_precios(filas):
        out = []
        for f in filas:
            d = fila_a_dict(f)
            d["evolucion"] = precios.get(d["id"], [])
            out.append(d)
        return out

    activas = con_precios(db.execute("SELECT * FROM ofertas WHERE estado = 'activa' ORDER BY puntuacion DESC, precio_actual"))
    historico = con_precios(db.execute(
        "SELECT * FROM ofertas WHERE estado = 'caducada' ORDER BY cerrada DESC LIMIT ?", (MAX_HISTORICO,)
    ))
    ultima = db.execute("SELECT * FROM ejecuciones WHERE fin IS NOT NULL ORDER BY id DESC LIMIT 1").fetchone()
    totales = db.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(avisada_ts IS NOT NULL), 0) AS avisadas FROM ofertas"
    ).fetchone()
    observaciones = db.execute("SELECT COUNT(*) FROM observaciones").fetchone()[0]

    datos = {
        "actualizado": actualizado,
        "origen": config.ORIGEN,
        "personas": config.PERSONAS,
        "umbral_aviso": config.UMBRAL_AVISO,
        "valoraciones": [[m, k, t] for m, k, t in tasador.VALORACIONES],
        "perfiles": {k: {"nombre": v["nombre"], "descripcion": v["descripcion"]} for k, v in config.PERFILES.items()},
        "activas": activas,
        "historico": historico,
        "ofertas_web": ofertas_web,
        "estadisticas": {
            "ofertas_totales": totales["n"], "avisadas": totales["avisadas"],
            "precios_analizados": observaciones,
            "estado_sistema": ultima["estado"] if ultima else None,
        },
    }
    DATOS_WEB.parent.mkdir(exist_ok=True)
    DATOS_WEB.write_text("window.DATOS = " + json.dumps(datos, ensure_ascii=False) + ";\n", encoding="utf-8")
    return datos
