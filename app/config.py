"""
Basit konfigürasyon yardımcıları.
Ayarları JSON dosyasına yazar/okur ve os.environ’a yükler.
"""
import json, os
from pathlib import Path

CFG_PATH = Path(__file__).resolve().parent / "config.json"
_DEFAULTS = {
    "LOGO_SQL_SERVER": "",
    "LOGO_SQL_USER":   "",
    "LOGO_SQL_PASSWORD": "",
    "ZPL_PRINTER":     "",
}

def save(cfg: dict):
    """cfg sözlüğünü JSON’a kaydeder."""
    with CFG_PATH.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def load() -> dict:
    """Dosya varsa okur, yoksa _DEFAULTS döndürür."""
    if CFG_PATH.exists():
        with CFG_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
            return {**_DEFAULTS, **data}
    return _DEFAULTS.copy()

def apply_env(cfg: dict):
    """cfg içindeki her anahtarı os.environ’a yazar."""
    for k, v in cfg.items():
        if v:
            os.environ[k] = v
