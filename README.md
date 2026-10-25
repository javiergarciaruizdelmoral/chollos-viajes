# Chollos de viaje desde Madrid

Un equipo de agentes busca vuelos desde Madrid, puntúa cada precio de 0 a 100
y mantiene un catálogo vivo de ofertas: solo entran las realmente buenas, se
revisan a diario, caducan cuando dejan de serlo y quedan en el histórico.
Solo se notifican las excelentes, una vez confirmadas.

## Cómo funciona

```
Explorador ──▶ Tasador ──▶ Archivero ──▶ Verificador ──▶ Notificador
 (Google        (0-100)     (catálogo     (re-comprueba     (solo ≥ 80,
  Flights)                   y ciclo       las activas)      confirmadas)
                             de vida)
                                   │
      Lector de webs ──────────────┼──▶ Publicador ──▶ web/
      (RSS de chollos)             │
                               Vigilante (salud del sistema)
```

| Agente | Archivo | Qué hace |
|---|---|---|
| Explorador | `agentes/vuelos.py` | Busca en Google Flights, rotando destinos y fechas cada día |
| Tasador | `agentes/tasador.py` | Puntúa cada precio (descuento, rango habitual, mínimo de 60 días, escalas) |
| Archivero | `agentes/archivero.py` | Da de alta, actualiza y caduca ofertas |
| Verificador | `agentes/archivero.py` (`verificar`) | Vuelve a buscar las ofertas activas |
| Notificador | `agentes/notificador.py` | Telegram / WhatsApp, solo ofertas excelentes y fallos |
| Lector de webs | `agentes/ofertas_web.py` | Viajeros Piratas, Travelzoo, Fly4free |
| Vigilante | `agentes/vigilante.py` | Registra cada ejecución y detecta fallos |
| Publicador | `agentes/publicador.py` | Genera `web/datos.js` |
| Almacén | `agentes/almacen.py` | Base de datos SQLite en `data/chollos.db` |

### Puntuación

| Criterio | Puntos | Cómo |
|---|---|---|
| Descuento | 45 | % por debajo del precio típico (40 % o más = máximo) |
| Rango | 30 | Posición dentro del rango habitual; por debajo = 22-30 |
| Mínimo 60 días | 15 | Iguala o mejora el mínimo de los últimos 60 días |
| Vuelo | 10 | Directo = 10; en largo radio se penalizan menos las escalas |

El precio típico, el rango y el mínimo los calcula Google Flights para cada ruta
y fechas. Si no están disponibles se usa el precio de referencia de `config.py`.

| Puntuación | Valoración | Qué pasa |
|---|---|---|
| 80-100 | Precio excelente | Entra en el catálogo y se notifica tras confirmarla |
| 65-79 | Muy buen precio | Entra en el catálogo |
| 45-64 | Buen precio | No entra; si una oferta activa baja aquí, caduca |
| 20-44 | Precio normal | Solo se guarda como observación |
| 0-19 | Precio alto | Solo se guarda como observación |

### Ciclo de vida de una oferta

- **Activa** cuando un precio puntúa 65 o más.
- Se **revisa** en cada ejecución.
- **Caduca** si su puntuación baja de 45, si no aparece 2 veces seguidas o si faltan menos de 2 días para la salida.
- Se **notifica** una sola vez cuando llega a 80 o más y está confirmada. Se vuelve a notificar solo si baja otro 5 %.

Todos los umbrales se cambian en `config.py`.

## Uso

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt pytest

.venv\Scripts\python main.py              # ejecución completa
.venv\Scripts\python main.py --sin-avisos # sin notificaciones
.venv\Scripts\python main.py --solo-web   # regenerar la web
.venv\Scripts\python -m pytest -q tests   # pruebas
```

La web es `web/index.html`, que lee `web/datos.js`.

## Ejecución automática

`.github/workflows/diario.yml` se ejecuta cada día a las 5:00 (hora de Madrid):
pasa las pruebas, lanza a los agentes, guarda la base de datos en el repositorio
y publica la web.

Secretos opcionales del repositorio para las notificaciones:
`TELEGRAM_TOKEN`, `TELEGRAM_CHAT`, `WHATSAPP_TELEFONO`, `WHATSAPP_APIKEY`.

## Limitaciones

- Los precios se leen de Google Flights sin API oficial, así que si Google cambia su web
  el explorador puede dejar de funcionar. El vigilante lo detecta y avisa.
- Uso personal y moderado: no está pensado para un uso comercial.
- Las tarifas de bajo coste no incluyen maleta facturada.
