# app/services/backorder_label_service.py
from __future__ import annotations
import argparse
import datetime as dt
import logging
from typing import Optional, Set

from app.backorder import list_fulfilled
from app.dao.logo import fetch_order_header, update_order_header
from app.services.label_service import make_labels as create_labels

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
def make_backorder_labels(
        the_date: dt.date,
        *,
        force: bool = False,
        override_pkg_tot: Optional[int] = None,
        only_order: Optional[str] = None,        # ← GUI’den tek sipariş için
) -> None:
    """
    Back-order kayıtlarını toplar ve etiket PDF(-ler)ini üretir.

    Parameters
    ----------
    the_date : date
        list_fulfilled() tarih filtresi için kullanılır.
        only_order verildiyse ihmal edilir.
    force : bool
        Fatura yoksa bile label_service'in --force seçeneğini geçir.
    override_pkg_tot : int
        GENEXP4’te yazılacak “PAKET SAYISI : N” değeri.
        None → qty_missing sahası kadar.
    only_order : str
        Sadece belirtilen sipariş numarası işlensin. (UI seçimi)
    """
    if only_order:
        rows = [r for r in list_fulfilled() if r["order_no"] == only_order]
    else:
        rows = list_fulfilled(the_date.isoformat())

    if not rows:
        log.info("İşlenecek back-order yok.")
        return

    done: Set[str] = set()
    for r in rows:
        ord_no = r["order_no"]
        if ord_no in done:
            continue

        pkg_tot = override_pkg_tot or max(int(r.get("qty_missing", 1)), 1)

        hdr = fetch_order_header(ord_no)
        if not hdr:
            log.error("Header bulunamadı: %s", ord_no)
            continue
        order_id = hdr.get("order_id") or hdr.get("logicalref")

        if not order_id:
            log.error("Geçersiz order_id, güncelleme atlandı: %s", ord_no)
            continue

        try:
            update_order_header(
                order_id,
                genexp4=f"PAKET SAYISI : {pkg_tot}",
                genexp5=ord_no,
            )
            log.info("GENEXP4/5 güncellendi → %s", ord_no)
            
            # shipment_header tablosunu da güncelle (eğer varsa)
            from app.shipment import upsert_header
            from app.dao.logo import fetch_one, exec_sql
            
            # Mevcut shipment header'ı bul
            ship_hdr = fetch_one(
                "SELECT id, trip_date, customer_code, customer_name, region, address1, invoice_root "
                "FROM shipment_header WHERE order_no = ?", 
                ord_no
            )
            
            if ship_hdr:
                # shipment_header'ı güncelle
                upsert_header(
                    order_no=ord_no,
                    trip_date=ship_hdr["trip_date"],
                    pkgs_total=pkg_tot,  # Yeni paket sayısı
                    customer_code=ship_hdr["customer_code"],
                    customer_name=ship_hdr["customer_name"],
                    region=ship_hdr["region"],
                    address1=ship_hdr["address1"],
                    invoice_root=ship_hdr["invoice_root"]
                )
                log.info("shipment_header güncellendi: %s paket → %s", ord_no, pkg_tot)

            # Yeni etiket üretimi
            create_labels(
                ord_no,
                force=force,
                footer="EGS"  # Eksik Gönderilen Sevkiyat dipnotu
            )
            log.info("Etiketler üretildi → %s", ord_no)
            done.add(ord_no)
        except Exception as exc:
            log.error("Header güncelleme veya etiket üretim hatası %s: %s", ord_no, exc)
            continue



# --------------------------------------------------------------------------- #
# (Opsiyonel) CLI – terminalden tek sefer çalıştırmak için
def _cli() -> None:
    ap = argparse.ArgumentParser("Back-order etiket basıcı")
    ap.add_argument("--date", default=dt.date.today().isoformat(),
                    help="YYYY-MM-DD (vars. bugün)")
    ap.add_argument("--force", action="store_true",
                    help="Fatura yoksa bile bas")
    ap.add_argument("--pkg-tot", type=int,
                    help="Tüm siparişlere sabit koli sayısı yaz")
    ap.add_argument("--order", help="Sadece bu sipariş")
    args = ap.parse_args()
    make_backorder_labels(
        dt.datetime.strptime(args.date, "%Y-%m-%d").date(),
        force=args.force,
        override_pkg_tot=args.pkg_tot,
        only_order=args.order,
    )

if __name__ == "__main__":
    _cli()
