"""Configuración de búsquedas: origen, perfiles de viaje y destinos."""

ORIGEN = "MAD"
PERSONAS = 4  # el precio se muestra siempre por persona; esto es para el total de grupo

# Puntuaciones (0-100) del ciclo de vida de una oferta; ver agentes/tasador.py
UMBRAL_ALTA = 65       # entra en el catálogo de ofertas activas ("muy buen precio" o mejor)
UMBRAL_AVISO = 80      # se notifica ("precio excelente"), solo tras confirmarla
UMBRAL_BAJA = 45       # si baja de aquí al revisarla, caduca
FALLOS_PARA_CADUCAR = 2          # veces seguidas sin encontrarla para darla por desaparecida
DIAS_MINIMOS_ANTELACION = 2      # caduca cuando falta menos que esto para la salida
REBAJA_PARA_REAVISAR_PCT = 5     # volver a avisar de una oferta ya avisada solo si baja este %

# Pausa entre búsquedas (segundos) para no saturar Google Flights
PAUSA_ENTRE_BUSQUEDAS = 3

PERFILES = {
    "escapada": {
        "nombre": "Escapadas",
        "descripcion": "3 a 5 noches, cualquier fecha del año",
        "noches": 3,             # duración que prueba el explorador de Google (una sola por búsqueda)
        "noches_rango": (3, 5),  # duraciones aceptadas por las fuentes que buscan por mes
        # días de salida aceptados (0=lunes ... 6=domingo): cualquiera, las vacaciones se adaptan al chollo
        "dias_salida": [0, 1, 2, 3, 4, 5, 6],
        "semanas_vista": 48,
        "fechas_por_destino": 2,  # fechas distintas que se prueban por destino en cada ejecución
        "max_escalas": 1,
        # código: (ciudad, precio de referencia por persona ida y vuelta en €)
        "destinos": {
            "LIS": ("Lisboa", 90), "OPO": ("Oporto", 90), "FCO": ("Roma", 110),
            "MXP": ("Milán", 100), "VCE": ("Venecia", 120), "NAP": ("Nápoles", 120),
            "BLQ": ("Bolonia", 120), "FLR": ("Florencia", 160), "CDG": ("París", 120),
            "AMS": ("Ámsterdam", 150), "BRU": ("Bruselas", 110), "LHR": ("Londres", 120),
            "DUB": ("Dublín", 110), "EDI": ("Edimburgo", 150), "BER": ("Berlín", 130),
            "MUC": ("Múnich", 160), "PRG": ("Praga", 160), "VIE": ("Viena", 160),
            "BUD": ("Budapest", 150), "KRK": ("Cracovia", 140), "ATH": ("Atenas", 170),
            "MLA": ("Malta", 150), "IST": ("Estambul", 200), "CPH": ("Copenhague", 160),
            "RAK": ("Marrakech", 120), "PMI": ("Palma de Mallorca", 80), "TFN": ("Tenerife", 110),
            "LPA": ("Gran Canaria", 110), "AGP": ("Málaga", 90), "SVQ": ("Sevilla", 90),
        },
    },
    "granviaje": {
        "nombre": "Gran viaje de verano",
        "descripcion": "Sudeste asiático en julio y agosto",
        "noches": 15,
        "noches_rango": (12, 21),
        "largo_radio": True,  # el tasador penaliza menos las escalas
        "rango_salida": ("2027-07-01", "2027-08-31"),
        "fechas_por_destino": 2,
        "max_escalas": 2,
        "destinos": {
            "DPS": ("Bali", 1100), "CGK": ("Yakarta", 1000), "KUL": ("Kuala Lumpur", 850),
            "SIN": ("Singapur", 950), "BKK": ("Bangkok", 850), "HKT": ("Phuket", 950),
            "SGN": ("Ho Chi Minh", 900), "HAN": ("Hanói", 900), "MNL": ("Manila", 1000),
            "CMB": ("Sri Lanka (Colombo)", 900), "MLE": ("Maldivas", 1100),
        },
    },
}
