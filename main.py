"""Coordinador del equipo de agentes.

Orden de trabajo en cada ejecución:
  1. Explorador   busca precios nuevos (rotando destinos y fechas)
  2. Archivero    registra cada precio, lo puntúa (tasador) y da de alta las ofertas buenas
  3. Verificador  vuelve a comprobar las ofertas activas y confirma las excelentes
  4. Archivero    caduca las ofertas cuya fecha ya está demasiado cerca
  5. Lector web   recoge ofertas de webs especializadas
  6. Vigilante    evalúa si la ejecución ha ido bien
  7. Notificador  avisa solo de ofertas excelentes confirmadas (o de fallos del sistema)
  8. Publicador   actualiza la web

Uso:
    python main.py                 # ejecución completa
    python main.py --perfil escapada
    python main.py --sin-avisos    # no mandar notificaciones
    python main.py --solo-web      # solo regenerar la web con lo que hay en la base de datos
"""

import argparse
from datetime import datetime
from zoneinfo import ZoneInfo

import config
from agentes import almacen, archivero, notificador, ofertas_web, publicador, vigilante, vuelos


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--perfil", choices=list(config.PERFILES))
    p.add_argument("--sin-avisos", action="store_true")
    p.add_argument("--solo-web", action="store_true")
    args = p.parse_args()

    ahora = datetime.now(ZoneInfo("Europe/Madrid"))
    ts = ahora.isoformat(timespec="seconds")
    db = almacen.conectar()
    print(f"== Chollos de viaje · {ahora:%d/%m/%Y %H:%M} ==")

    if args.solo_web:
        publicador.publicar(db, ofertas_web.recoger(), ts)
        print("Web regenerada.")
        return

    ejecucion = vigilante.iniciar(db, ts)
    buscador = vuelos.Buscador(log=lambda m: print(m, flush=True))

    print("[1/8] Explorador")
    resultados = vuelos.explorar(buscador, hoy=ahora.date(), solo_perfil=args.perfil)

    print("[2/8] Tasador + archivero")
    nuevas = archivero.registrar(db, resultados, ts)
    db.commit()
    print(f"  {len(nuevas)} ofertas nuevas en el catálogo")

    print("[3/8] Verificador")
    archivero.verificar(db, buscador, ts)
    db.commit()

    print("[4/8] Caducidad por fecha")
    archivero.caducar_por_fecha(db, ahora.date(), ts)
    caducadas = db.execute("SELECT COUNT(*) FROM ofertas WHERE cerrada = ?", (ts,)).fetchone()[0]
    db.commit()
    print(f"  {caducadas} ofertas caducadas hoy")

    print("[5/8] Lector de webs de ofertas")
    ofertas = ofertas_web.recoger()

    print("[6/8] Vigilante")
    estado, nota = vigilante.evaluar(buscador)
    print(f"  Estado: {estado} ({nota})")

    print("[7/8] Notificador")
    avisos = 0
    if not args.sin_avisos:
        if estado == "fallo":
            notificador.avisar_fallo(nota)
        a_avisar = archivero.para_avisar(db)
        if notificador.avisar_ofertas(a_avisar):
            archivero.marcar_avisadas(db, a_avisar, ts)
            avisos = len(a_avisar)

    vigilante.cerrar(db, ejecucion, datetime.now(ZoneInfo("Europe/Madrid")).isoformat(timespec="seconds"),
                     buscador, len(nuevas), caducadas, avisos, estado, nota)

    print("[8/8] Publicador")
    datos = publicador.publicar(db, ofertas, ts)
    print(f"Listo: {len(datos['activas'])} ofertas activas, {len(datos['historico'])} en el histórico.")


if __name__ == "__main__":
    main()
