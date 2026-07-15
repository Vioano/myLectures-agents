#!/usr/bin/env python3
"""Backward-compatible entrypoint for lecture-animation-pipeline-v2."""

from pipeline_v2_lib.engine import *  # noqa: F401,F403


if __name__ == "__main__":
    raise SystemExit(main())
