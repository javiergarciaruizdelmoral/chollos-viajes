"""Agente vigilante: registra cada ejecución y detecta si el sistema está fallando
(por ejemplo, si Google cambia su web y las búsquedas dejan de dar resultados)."""

# por debajo de este % de búsquedas con resultado, algo va mal
MINIMO_OK_PCT = 50


def evaluar(buscador):
    """Devuelve (estado, nota): 'ok', 'degradado' o 'fallo'."""
    if buscador.busquedas == 0:
        return "ok", "Sin búsquedas"
    pct = buscador.resultados / buscador.busquedas * 100
    if buscador.resultados == 0:
        return "fallo", f"Ninguna de las {buscador.busquedas} búsquedas dio resultados"
    if pct < MINIMO_OK_PCT:
        return "degradado", f"Solo {pct:.0f} % de búsquedas con resultados"
    return "ok", f"{pct:.0f} % de búsquedas con resultados"


def iniciar(db, ts):
    cur = db.execute("INSERT INTO ejecuciones (inicio, estado) VALUES (?, 'en_curso')", (ts,))
    db.commit()
    return cur.lastrowid


def cerrar(db, ejecucion_id, fin, buscador, nuevas, caducadas, avisos, estado, nota):
    db.execute(
        "UPDATE ejecuciones SET fin = ?, busquedas = ?, resultados = ?, errores = ?, nuevas = ?,"
        " caducadas = ?, avisos = ?, estado = ?, notas = ? WHERE id = ?",
        (fin, buscador.busquedas, buscador.resultados, buscador.errores, nuevas, caducadas, avisos,
         estado, nota, ejecucion_id),
    )
    db.commit()
