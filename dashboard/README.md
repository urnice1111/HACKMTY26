# Shift console

React dashboard for agent decisions. No map.

```bash
cd dashboard
cp .env.example .env   # VITE_USE_MOCK=1 until the API is up
npm install
npm run dev
```

Polls `VITE_API_BASE` (`/shifts/:id/runs`, `/runs/:id`, `/shifts/:id/stats`). Mock mode injects a second run after ~4s.

Live mode (after FastAPI is running):

```
VITE_API_BASE=http://localhost:8000/v1
VITE_SHIFT_ID=shift-abc
VITE_USE_MOCK=0
```

The Go simulator calls `POST /decision` with its native payload (`puntos_ruta`,
`matriz`, pending/available orders, and pickup/drop constraints). FastAPI
normalizes unreachable matrix hops, runs the DecisionAgent, stores each tool
event in memory, and returns `{ aceptar_pedidos, paradas_ordenadas,
ruta_propuesta }` to the simulator. This dashboard polls that in-memory
history from `/v1`; restarting the API clears it.

The older `POST /optimize-route` endpoint remains available only for its
original standalone client. Do not point the Go simulator at it.
