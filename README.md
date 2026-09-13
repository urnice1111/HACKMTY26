# Courier Decision Agent — HACKMTY 2026

Sistema inteligente para optimizar rutas de repartidores mediante un agente de IA.

El proyecto analiza tiempos de traslado, demanda estimada, capacidad del courier y restricciones de recolección/entrega para seleccionar una ruta viable y explicar la decisión en lenguaje natural.

## Características

- Generación de rutas candidatas.
- Respeto de paradas obligatorias y capacidad máxima.
- Validación de que cada recolección ocurra antes de su entrega.
- Estimación de demanda según destino y hora de llegada.
- Comparación y puntuación de rutas.
- Explicación de la decisión para el repartidor.
- API REST con FastAPI.
- Integración con un simulador externo.
- Dashboard para observar decisiones y herramientas ejecutadas en tiempo real.
- Modo de prueba sin utilizar un modelo de IA.

## Arquitectura

```text
Simulador
    │
    │ POST /decision
    ▼
FastAPI
    │
    ├── Adapta y valida la solicitud
    ├── Ejecuta el Decision Agent
    └── Guarda temporalmente cada decisión
             │
             ▼
      OpenAI Agents SDK
             │
             ├── Generación de rutas
             ├── Contexto del destino
             ├── Predicción de demanda
             ├── Puntuación
             └── Selección final
             │
             ▼
       Dashboard React
```

## Tecnologías

### Backend

- Python 3.11+
- FastAPI
- Pydantic
- OpenAI Agents SDK
- Uvicorn

### Frontend

- React
- TypeScript
- Vite
- Oxc

## Estructura del proyecto

```text
HACKMTY26/
├── API/
│   ├── main.py                 # Endpoints de FastAPI
│   ├── models.py               # Contratos de entrada y salida
│   ├── simulator_adapter.py    # Adaptador para el simulador
│   └── run_store.py            # Historial temporal de decisiones
├── DecisionAgent/
│   ├── Context/                # Coordenadas, matrices y restricciones
│   ├── Models/                 # Salidas estructuradas
│   ├── Tools/                  # Herramientas utilizadas por el agente
│   ├── agent.py                # Configuración del agente
│   ├── runner.py               # Ejecución y seguimiento
│   └── __main__.py             # CLI
├── dashboard/
│   ├── src/                    # Aplicación React
│   └── package.json
├── .env.example
├── pyproject.toml
└── requirements.txt
```

## Requisitos

- Python 3.11 o superior
- Node.js 20 o superior
- npm
- Una API key de OpenAI para ejecutar el agente

## Instalación

Clona el repositorio:

```bash
git clone https://github.com/urnice1111/HACKMTY26.git
cd HACKMTY26
```

Crea y activa un entorno virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

En Windows:

```powershell
.venv\Scripts\activate
```

Instala las dependencias:

```bash
pip install -r requirements.txt
```

Crea el archivo de configuración:

```bash
cp .env.example .env
```

Agrega tus credenciales:

```env
OPENAI_API_KEY=tu_api_key
OPENAI_MODEL=gpt-4o
```

No publiques el archivo `.env` ni compartas tu API key.

## Ejecución

### Prueba local sin IA

Este modo genera y puntúa rutas localmente sin realizar llamadas a OpenAI:

```bash
python -m DecisionAgent --dry-run
```

### Ejecución del agente

```bash
python -m DecisionAgent
```

### Iniciar la API

```bash
uvicorn API.main:app --reload
```

La API estará disponible en:

- API: http://localhost:8000
- Documentación Swagger: http://localhost:8000/docs
- OpenAPI: http://localhost:8000/openapi.json

Puedes comprobar que funciona con:

```bash
curl http://localhost:8000/
```

## Probar la optimización sin IA

El endpoint anterior del proyecto incluye un modo `mock` que ordena los puntos mediante una estrategia de vecino más cercano:

```bash
curl -X POST "http://localhost:8000/optimize-route?mock=true" \
  -H "Content-Type: application/json" \
  -d '{
    "estadoCourier": "wait",
    "current_pos": [-100.2895, 25.6514],
    "pedidosActivos": 0,
    "puntosVisitar": [
      {
        "state": "pick",
        "order_pos": [-100.3090, 25.6690]
      },
      {
        "state": "drop",
        "order_pos": [-100.3184, 25.6782]
      }
    ],
    "matrix": [
      [0, 8, 12],
      [8, 0, 5],
      [12, 5, 0]
    ]
  }'
```

> En este endpoint, las posiciones utilizan el orden `[longitud, latitud]`.

## Dashboard

Abre otra terminal y ejecuta:

```bash
cd dashboard
cp .env.example .env
npm install
npm run dev
```

Configuración del dashboard:

```env
VITE_API_BASE=http://localhost:8000/v1
VITE_SHIFT_ID=shift-abc
VITE_USE_MOCK=0
```

Después abre:

```text
http://localhost:5173
```

Para utilizar datos locales de demostración:

```env
VITE_USE_MOCK=1
```

## Endpoints principales

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/` | Estado de la API |
| `POST` | `/decision` | Procesa una decisión enviada por el simulador |
| `POST` | `/optimize-route` | Compatibilidad con el cliente original |
| `POST` | `/v1/runs` | Registra una ejecución |
| `GET` | `/v1/runs/{run_id}` | Obtiene el detalle de una decisión |
| `GET` | `/v1/shifts/{shift_id}/runs` | Lista decisiones de un turno |
| `GET` | `/v1/shifts/{shift_id}/stats` | Obtiene estadísticas del turno |

## Cómo se selecciona una ruta

El agente sigue este flujo:

1. Analiza la matriz de costos y las restricciones.
2. Genera rutas completas y viables.
3. Consulta el contexto de los destinos.
4. Estima la demanda al momento de llegada.
5. Puntúa cada ruta.
6. Selecciona entre una y tres alternativas.
7. Devuelve la ruta elegida y una explicación para el repartidor.

La puntuación actual utiliza:

```text
score = demanda_estimada / (1 + costo_total)
```

Un valor mayor representa una combinación más favorable entre demanda y costo de traslado.

## Consideraciones actuales

Este repositorio es un prototipo:

- Las señales de demanda, congestión y contexto geográfico son simuladas.
- El historial del dashboard se guarda en memoria.
- Reiniciar la API elimina las ejecuciones almacenadas.
- La integración de rutas reales debe conectarse a una fuente externa.
- Las decisiones deben validarse antes de utilizarse en producción.

## Equipo

Proyecto desarrollado para HACKMTY 2026.

## Licencia

Actualmente el repositorio no incluye una licencia. Agrega un archivo `LICENSE` antes de distribuir o reutilizar públicamente el proyecto.
