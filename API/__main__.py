"""python -m API  ->  serve the decision API on the port the simulator expects."""

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "API.main:app",
        host=os.getenv("API_HOST", "127.0.0.1"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=bool(os.getenv("API_RELOAD")),
        timeout_graceful_shutdown=1,
    )


if __name__ == "__main__":
    main()
