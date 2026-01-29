"""Entrypoint for running the web server."""
from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run("app.web.server:app", host="127.0.0.1", port=8080, reload=False)


if __name__ == "__main__":
    main()
