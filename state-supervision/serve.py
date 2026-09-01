#!/usr/bin/env python3
"""Launch the local Human interface and shared HTTP/SSE backend."""

from __future__ import annotations

import argparse
from pathlib import Path

from supervision.http_server import serve


def main() -> int:
    parser = argparse.ArgumentParser(description="Lecture state supervision Web service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4321)
    parser.add_argument("--data-root", default=".lecture-state")
    parser.add_argument("--repo-root", default=".")
    arguments = parser.parse_args()
    here = Path(__file__).resolve().parent
    serve(
        host=arguments.host,
        port=arguments.port,
        data_root=Path(arguments.data_root),
        repo_root=Path(arguments.repo_root),
        static_root=here / "static",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
