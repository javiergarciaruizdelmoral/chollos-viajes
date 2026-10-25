"""Diagnóstico rápido del explorador: unas pocas búsquedas sin tocar la base de datos.

    python diagnostico.py
"""

import time
from datetime import date, timedelta

from agentes import vuelos

PRUEBAS = [("escapada", "FCO", 47), ("escapada", "DUB", 32), ("escapada", "SVQ", 39), ("granviaje", "BKK", 261)]

cliente = vuelos._cliente()
for perfil, destino, dias in PRUEBAS:
    ida = date.today() + timedelta(days=dias)
    noches = 15 if perfil == "granviaje" else 3
    r = vuelos.buscar(cliente, destino, ida, ida + timedelta(days=noches), 2)
    if r:
        print(f"OK  {destino} {ida}: {r['precio_persona']} € (típico {r.get('google_tipico')}, rango {r.get('google_rango')})")
    else:
        print(f"MAL {destino} {ida}: {vuelos.buscar.ultimo_motivo}")
    time.sleep(3)
