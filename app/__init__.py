# app/__init__.py
from pathlib import Path
import logging, os, sys
from app import settings                               # ← YENİ 1

# → proje kökü  …/your_project/
BASE_DIR = Path(__file__).resolve().parent

# 1)  logs klasörü
LOG_DIR = Path(settings.get("paths.log_dir"))          # ← YENİ 2
LOG_DIR.mkdir(parents=True, exist_ok=True)             # ← YENİ 3

# 2)  global basicConfig  (tüm import’lar buna bağlanır)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logging.info("Logging baslatildi -> %s", LOG_DIR)



# ── TOAST BLOKU ───────────────────────────────────────────
from typing import Callable, Any

_toast_cb: Callable[[str, str | None], Any] | None = None   # GUI yüklenince set edilir

def register_toast(cb: Callable[[str, str | None], Any]) -> None:
    """MainWindow, kendi callback’ini burada kaydeder."""
    global _toast_cb
    _toast_cb = cb

def toast(title: str, msg: str | None = None) -> None:
    """
    Arka-plan servisleri ile UI sayfaları buraya çağrı yapar.
    GUI açıksa callback devreye girer, yoksa sessizce log’da kalır.
    """
    import logging
    logging.info("TOAST ▸ %s – %s", title, msg or "")
    if _toast_cb:
        _toast_cb(title, msg)
# ──────────────────────────────────────────────────────────
