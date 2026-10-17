"""TabScreen USB — Ana giriş noktası: `python main.py` (uygulama mantığı `src/app.py` içindedir)."""

from __future__ import annotations

from src.app import main, parse_args, run, run_cli  # noqa: F401 - testler ve dış çağrılar için dışa aktarılır

if __name__ == "__main__":
    run()
