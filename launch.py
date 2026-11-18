"""Punto d'ingresso per lo sviluppo (python launch.py) e per il bundle PyInstaller."""

import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    # In sviluppo, rende importabile il pacchetto src/mdapp senza impostare PYTHONPATH
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from mdapp.gui import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
