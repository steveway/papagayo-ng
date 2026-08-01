"""Entry point for the Nuitka-packaged UI build."""
import os
import sys

# Windows GUI apps have no console; uvicorn/asyncio logging crashes
# if stdout/stderr are None. Redirect them to devnull.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from phonemation_backend.ui import run_ui

if __name__ == "__main__":
    run_ui()
