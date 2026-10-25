"""Agente archivero: gestiona el ciclo de vida de las ofertas.

  descubierta  un precio con puntuación >= UMBRAL_ALTA entra en el catálogo como activa
  activa       se vuelve a comprobar en cada ejecución (por el explorador o el verificador)
  caducada     si la puntuación baja de UMBRAL_BAJA, desaparece FALLOS_PARA_CADUCAR veces
               seguidas, o la fecha de ida ya está demasiado cerca. Queda en el histórico.

Una oferta se identifica por perfil + destino + fecha de ida + fecha de vuelta.
"""

import json
from datetime import date, timedelta

import config
from agentes import tasador


def _id(r):
    return f"{r['perfil']}|{r['destino']}|{r['ida']}|{r['vuelta']}"


def _tasar(r):
    largo = config.PERFILES[r["perfil"]].get("largo_radio", False)
    puntos, desglose, refs = tasador.puntuar(r, largo_radio=largo)
    return puntos, desglose, refs


def registrar(db, resultados, ts):
    """Guarda cada precio visto como observación y actualiza/crea ofertas. Devuelve las nuevas."""
    nuevas = []
    for r in resultados:
        puntos, desglose, refs = _tasar(r)
        db.execute(
            "INSERT INTO observaciones (ts, perfil, destino, ida, vuelta, precio, tipico, rango_bajo,"
            " rango_alto, min60, escalas, aerolineas, puntuacion) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ts, r["perfil"], r["destino"], r["ida"], r["vuelta"], r["precio_persona"], refs["tipico"],
             refs["rango_bajo"], refs["rango_alto"], refs["min60"], r["escalas"],
             json.dumps(r["aerolineas"], ensure_ascii=False), puntos),
        )
        existente = db.execute("SELECT * FROM ofertas WHERE id = ?", (_id(r),)).fetchone()
        if existente and existente["estado"] == "activa":
            _actualizar(db, existente, r, puntos, desglose, refs, ts)
        elif puntos >= config.UMBRAL_ALTA:
            _crear(db, r, puntos, desglose, refs, ts, reabrir=existente is not None)
            nuevas.append(_id(r))
    return nuevas


def _campos_vuelo(r, puntos, desglose, refs):
    return {
        "precio_actual": r["precio_persona"], "puntuacion": puntos,
        "valoracion": tasador.valoracion(puntos), "desglose": json.dumps(desglose),
        "tipico": refs["tipico"], "rango_bajo": refs["rango_bajo"], "rango_alto": refs["rango_alto"],
        "min60": refs["min60"], "base_comparacion": refs["base_comparacion"],
        "escalas": r["escalas"], "aerolineas": json.dumps(r["aerolineas"], ensure_ascii=False),
        "minutos_vuelo": r["minutos_vuelo"], "hora_salida": r["hora_salida"], "enlace": r["enlace"],
    }


def _crear(db, r, puntos, desglose, refs, ts, reabrir):
    campos = _campos_vuelo(r, puntos, desglose, refs)
    campos.update(
        id=_id(r), perfil=r["perfil"], destino=r["destino"], ciudad=r["ciudad"], ida=r["ida"],
        vuelta=r["vuelta"], estado="activa", motivo_cierre=None, descubierta=ts,
        ultima_verificacion=ts, cerrada=None, precio_inicial=r["precio_persona"],
        precio_minimo=r["precio_persona"], puntuacion_max=puntos, verificaciones=0,
        fallos_seguidos=0, avisada_precio=None, avisada_ts=None,
    )
    if reabrir:
        db.execute("DELETE FROM ofertas WHERE id = ?", (campos["id"],))
    columnas = ", ".join(campos)
    db.execute(f"INSERT INTO ofertas ({columnas}) VALUES ({', '.join('?' * len(campos))})", list(campos.values()))
    db.execute("INSERT INTO precios_oferta VALUES (?,?,?,?)", (campos["id"], ts, r["precio_persona"], puntos))


def _actualizar(db, oferta, r, puntos, desglose, refs, ts):
    campos = _campos_vuelo(r, puntos, desglose, refs)
    campos.update(
        ultima_verificacion=ts, verificaciones=oferta["verificaciones"] + 1, fallos_seguidos=0,
        precio_minimo=min(oferta["precio_minimo"], r["precio_persona"]),
        puntuacion_max=max(oferta["puntuacion_max"], puntos),
    )
    asignaciones = ", ".join(f"{k} = ?" for k in campos)
    db.execute(f"UPDATE ofertas SET {asignaciones} WHERE id = ?", [*campos.values(), oferta["id"]])
    db.execute("INSERT INTO precios_oferta VALUES (?,?,?,?)", (oferta["id"], ts, r["precio_persona"], puntos))
    if puntos < config.UMBRAL_BAJA:
        _caducar(db, oferta["id"], ts, "Ha subido de precio")


def _caducar(db, oferta_id, ts, motivo):
    db.execute(
        "UPDATE ofertas SET estado = 'caducada', motivo_cierre = ?, cerrada = ? WHERE id = ?",
        (motivo, ts, oferta_id),
    )


def pendientes_de_verificar(db, ts):
    """Activas que el explorador no ha vuelto a ver en esta ejecución, y las recién
    descubiertas que merecen aviso (hay que confirmarlas antes de avisar)."""
    return db.execute(
        "SELECT * FROM ofertas WHERE estado = 'activa' AND"
        " (ultima_verificacion != ? OR (verificaciones = 0 AND puntuacion >= ?))",
        (ts, config.UMBRAL_AVISO),
    ).fetchall()


def verificar(db, buscador, ts):
    """Agente verificador: vuelve a buscar cada oferta activa pendiente."""
    for o in pendientes_de_verificar(db, ts):
        r = buscador.buscar(o["perfil"], o["destino"], date.fromisoformat(o["ida"]), date.fromisoformat(o["vuelta"]))
        if r:
            puntos, desglose, refs = _tasar(r)
            _actualizar(db, o, r, puntos, desglose, refs, ts)
            buscador.log(f"  {o['ciudad']} {o['ida']}: {o['precio_actual']} € -> {r['precio_persona']} € ({puntos} pts)")
        else:
            fallos = o["fallos_seguidos"] + 1
            db.execute("UPDATE ofertas SET fallos_seguidos = ? WHERE id = ?", (fallos, o["id"]))
            buscador.log(f"  {o['ciudad']} {o['ida']}: no encontrada ({fallos})")
            if fallos >= config.FALLOS_PARA_CADUCAR:
                _caducar(db, o["id"], ts, "Ya no está disponible")


def caducar_por_fecha(db, hoy, ts):
    limite = (hoy + timedelta(days=config.DIAS_MINIMOS_ANTELACION)).isoformat()
    filas = db.execute("SELECT id FROM ofertas WHERE estado = 'activa' AND ida < ?", (limite,)).fetchall()
    for f in filas:
        _caducar(db, f["id"], ts, "Fecha de salida demasiado cercana")
    return len(filas)


def para_avisar(db):
    """Ofertas excelentes, confirmadas al menos una vez y no avisadas (o que han bajado más)."""
    filas = db.execute(
        "SELECT * FROM ofertas WHERE estado = 'activa' AND puntuacion >= ? AND verificaciones >= 1",
        (config.UMBRAL_AVISO,),
    ).fetchall()
    return [
        o for o in filas
        if o["avisada_precio"] is None
        or o["precio_actual"] <= o["avisada_precio"] * (1 - config.REBAJA_PARA_REAVISAR_PCT / 100)
    ]


def marcar_avisadas(db, ofertas, ts):
    for o in ofertas:
        db.execute("UPDATE ofertas SET avisada_precio = ?, avisada_ts = ? WHERE id = ?", (o["precio_actual"], ts, o["id"]))
