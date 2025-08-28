"""
backorder_worker.py – Eksik ürün tamamlama otomatı
==================================================
30 dakikada bir `backorders` tablosunu kontrol eder; depoya gelen stok
eksik adedi karşılıyorsa kaydı kapatır, hem log dosyasına yazar hem de
GUI açıksa toast bildirimi gösterir.

Çalıştırma
----------
Tek sefer:
    python -m app.services.backorder_worker --once
Sürekli döngü (varsayılan 30 dk):
    python -m app.services.backorder_worker --interval 1800
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple
from app import toast                #  ⇦  satırı ekle

# ---------------------------------------------------------------
#  Proje modülleri & ortam kurulum
# ---------------------------------------------------------------

# Proje kökü PYTHONPATH'e ekle (script doğrudan çalıştırılırsa)
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

# «app» import edildiğinde:
#   • logs/ klasörünü yaratır
#   • logging.basicConfig()'i INFO + dosya handler ile kurar
#   • toast() yardımcı fonksiyonunu dışa vurur
import app                      # noqa: E402  (önce sys.path)
from app import toast           # küçük baloncuk bildirimi

import app.backorder as bo      # backorders DAO
from app.dao import logo as dao  # Logo MSSQL erişimi
import pyodbc                   # type: ignore

log = logging.getLogger(__name__)

# ---------------------------------------------------------------
#  DB yardımı – depo bazında net stok
# ---------------------------------------------------------------

def fetch_free_qty(item_code: str, wh_id: int) -> float:
    """LV_XXX_STINVTOT view'inden *ONHAND* alır (Logo versiyon‑agnostik)."""
    sql = f"""
    SELECT TOP 1 S.ONHAND
      FROM LV_025_01_STINVTOT S
      JOIN {dao._t('ITEMS', period_dependent=False)} I
            ON I.LOGICALREF = S.STOCKREF
     WHERE S.INVENNO = ? AND I.CODE = ?
    """
    with dao.get_conn() as cn:
        row = cn.execute(sql, wh_id, item_code).fetchone()
        return float(row[0]) if row and row[0] is not None else 0.0

# ---------------------------------------------------------------
#  Ana işleyici
# ---------------------------------------------------------------

def process_backorders() -> None:
    """
    • backorders.fulfilled = 0 kayıtlarını alır
    • depo‐stok bazında gruplayıp serbest stoku (ONHAND) kontrol eder
    • yeterli stok varsa bo.mark_fulfilled + toast bildirimi
    """
    pending = bo.list_pending()
    if not pending:
        log.info("Back-order kontrolü: tamamlanacak eksik ürün yok")
        return

    # 🔸 Sipariş + stok bazlı grupla → tek stok sorgusu / işlem
    groups: Dict[Tuple[str, str, int], Dict] = defaultdict(
        lambda: {"need": 0.0, "recs": []}
    )
    for rec in pending:
        key = (rec["order_no"], rec["item_code"], rec["warehouse_id"])
        groups[key]["need"] += rec["qty_missing"]
        groups[key]["recs"].append(rec)

    log.info("Back-order kontrolü başlıyor (%d grup)…", len(groups))

    for (ord_no, item_code, wh_id), g in groups.items():
        need = g["need"]                     # toplu eksik
        try:
            free = fetch_free_qty(item_code, wh_id)
        except pyodbc.Error as exc:
            log.error("Stok sorgu hatası %s – %s", item_code, exc)
            continue

        if free >= need:
            # ► tüm alt kayıtları kapat
            for rec in g["recs"]:
                bo.mark_fulfilled(rec["id"])

            msg = f"{ord_no}  {item_code}  +{need:.0f} (AMB {wh_id})"
            log.info("TAMAMLANDI ▸ %s", msg)
            toast("Eksik Ürün Tamamlandı", msg)
        else:
            log.debug(
                "Yetersiz ▸ %s %s – free %.0f / need %.0f",
                ord_no, item_code, free, need
            )

# ---------------------------------------------------------------
#  Döngü / CLI
# ---------------------------------------------------------------

def watcher_loop(sec: int):
    log.info("Backorder worker %d sn aralıkla çalışıyor…", sec)
    while True:
        try:
            process_backorders()
        except Exception as exc:
            log.exception("Worker hatası: %s", exc)
        time.sleep(sec)

def main():
    ap = argparse.ArgumentParser(description="Back‑order tamamlama servisi")
    ap.add_argument("--once", action="store_true", help="Tek sefer çalış ve çık")
    ap.add_argument("--interval", type=int, default=1800, help="Döngü süresi (sn)")
    args = ap.parse_args()

    if args.once:
        process_backorders()
    else:
        watcher_loop(args.interval)

if __name__ == "__main__":
    main()
