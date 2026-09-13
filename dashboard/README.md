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

`POST /optimize-route` takes courier state from the simulator (`estadoCourier`, `current_pos`, `pedidosActivos`, `puntosVisitar`, `matrix`) and returns `{ puntosVisitar, description }`. Full tool-step history is stored in memory and served from `/v1`. Restarting the API clears it.
