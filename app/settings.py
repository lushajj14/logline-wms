#!/usr/bin/env python3
# ──────────────────────────────────────────────────────────────
#  Kalıcı ayar yönetimi (JSON’suz sürüm)  –  app/settings.py
# ──────────────────────────────────────────────────────────────
from __future__ import annotations
import sys
from pathlib import Path
from typing import Any, Dict
import json  # ileride gerekirse kullanırsın

# ───────────── PyInstaller uyumlu kök dizin ─────────────
if getattr(sys, "frozen", False):                       # exe içindeysek
    BASE_DIR = Path(getattr(sys, "_MEIPASS"))           # sanal kök
else:
    BASE_DIR = Path(__file__).resolve().parents[2]      # geliştirme modu

# ───────────── Dinamik log yolu ─────────────
if getattr(sys, "frozen", False):                       # exe → Kullanıcı profili
    LOG_DIR_DEFAULT = Path.home() / "MyAppLogs"
else:                                                   # geliştirme → proje/logs
    LOG_DIR_DEFAULT = BASE_DIR / "logs"

# ───────────── Varsayılan ayarlar ─────────────
DEFAULTS: Dict[str, Any] = {
    "ui": {
        "theme":      "light",
        "font_pt":    10,
        "toast_secs": 3,
        "lang":       "TR",
        "sounds": {
            "enabled": True,
            "volume":  0.9
        },
        "auto_focus": True
    },
    "scanner": {
        "prefixes": {"D1-": "0", "D3-": "1"},
        "over_scan_tol": 0
    },
    "loader": {
        "auto_refresh": 30,
        "block_incomplete": True
    },
    "db": {
        "server":    "78.135.108.160,1433",
        "database":  "logo",
        "user":      "barkod1",
        "retry":     3,
        "heartbeat": 10
    },
    "paths": {
        "label_dir":  str(Path.home() / "Documents" / "Yönetim" / "labels"),
        "export_dir": str(Path.home() / "Desktop"),
        "log_dir":    str(LOG_DIR_DEFAULT),
        "font_dir": str(BASE_DIR / "fonts")
    },
    "print": {
        "label_printer": "",
        "doc_printer":   "",
        "label_tpl":     "default.tpl",
        "auto_open":     True
    }
}

# ───────────── Yardımcılar ─────────────
_cfg: Dict[str, Any] = {}


def _deep_update(dst: Dict, src: Dict) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k, {}), dict):
            _deep_update(dst.setdefault(k, {}), v)
        else:
            dst[k] = v


# JSON kullanılmıyor → disk yükleme/kaydetme no-op
def _load_disk() -> Dict[str, Any]:
    return {}


def save() -> None:
    pass


# ───────────── Ana API ─────────────
def reload() -> Dict[str, Any]:
    global _cfg
    _cfg = {}
    _deep_update(_cfg, DEFAULTS)        # 1) varsayılanlar

    disk = _load_disk()                 # 2) kullanıcı JSON (boş)
    _deep_update(_cfg, disk)

    # scanner.prefixes tamamen override olsun
    if isinstance(disk.get("scanner", {}).get("prefixes"), dict):
        _cfg["scanner"]["prefixes"] = disk["scanner"]["prefixes"]

    # —— Log klasörü yoksa oluştur —— 
    Path(get("paths.log_dir")).mkdir(parents=True, exist_ok=True)
    Path(get("paths.font_dir")).mkdir(parents=True, exist_ok=True)
    return _cfg


# Eski çağrılar bozulmasın
load = reload


def get(path: str, default: Any = None) -> Any:
    cur = _cfg
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def set(path: str, value: Any) -> None:
    parts = path.split(".")
    cur = _cfg
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value
    save()

# ───────────── İlk yükleme ─────────────
reload()


# — Basit CLI testi —
if __name__ == "__main__":
    from pprint import pprint
    print("Tema:", get("ui.theme"))
    set("ui.theme", "dark")
    pprint(_cfg)
