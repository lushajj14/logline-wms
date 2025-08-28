"""
CSV / Excel → barcode_xref toplu içe aktarma
-------------------------------------------
Kullanım:
    from app.services.import_barcodes import load_file
    ok, sec, err = load_file("dosya.csv")

Beklenen sütunlar (büyük / küçük harf duyarsız, boşluklar önemsiz):
    • barcode       (veya barkod)
    • warehouse_id  (veya depo)
    • item_code     (veya stok kodu / stok_kodu / stok)
İsteğe bağlı:
    • multiplier    (veya çarpan) — yoksa 1 kabul edilir

Örnek Excel:
+-------------+------+-----------+----------+
|  barcode    | depo | stok kodu | çarpan   |
+-------------+------+-----------+----------+
| 12345678901 |  2   | ABC‑001   | 1        |
| 98765432109 |  4   | XYZ‑777   |          |
+-------------+------+-----------+----------+

"""

from pathlib import Path
import time
import csv
from typing import List, Tuple, Dict

import pandas as pd  # openpyxl + xlrd kurulu olmalı
from app.dao.logo import get_connection  # DAO’daki ortak bağlantı

# ────────────────────────────────────────────────────────────────────────────
# MERGE  →  varsa UPDATE  |  yoksa INSERT
# ────────────────────────────────────────────────────────────────────────────
SQL = (
    "MERGE dbo.barcode_xref AS tgt "
    "USING (VALUES (?, ?, ?, ?)) "
    "     AS src(barcode, wh, item_code, mul) "
    "ON (tgt.barcode = src.barcode AND tgt.warehouse_id = src.wh) "
    "WHEN MATCHED THEN "
    "     UPDATE SET tgt.item_code   = src.item_code, "
    "                tgt.multiplier  = src.mul, "
    "                tgt.updated_at  = GETDATE() "
    "WHEN NOT MATCHED THEN "
    "     INSERT (barcode, warehouse_id, item_code, multiplier, updated_at) "
    "     VALUES (src.barcode, src.wh, src.item_code, src.mul, GETDATE());"
)

# ────────────────────────────────────────────────────────────────────────────
# Başlık normalizasyonu ve doğrulama
# ────────────────────────────────────────────────────────────────────────────
COLMAP: Dict[str, set] = {
    "barcode": {"barcode", "barkod"},
    "warehouse_id": {"warehouse_id", "depo"},
    "item_code": {"item_code", "stok kodu", "stok_kodu", "stok kod", "stok"},
    "multiplier": {"multiplier", "çarpan"},
}

REQUIRED_COLS = {"barcode", "warehouse_id", "item_code"}


def _norm_key(col: str) -> str:
    """Başlık adını standarda çevirir (strip + lower + eşleştirme)."""
    col = col.strip().lower()
    for std, aliases in COLMAP.items():
        if col in aliases:
            return std
    return col  # eşleşmezse olduğu gibi bırak


def _validate_columns(cols) -> None:
    """Gerekli başlıkların mevcut olduğunu doğrular."""
    missing = REQUIRED_COLS - set(cols)
    if missing:
        sample = "barcode | depo | stok kodu | çarpan (opsiyonel)"
        raise ValueError(
            "Excel/CSV sütunları eksik: "
            + ", ".join(missing)
            + "\n\nBeklenen format örneği:\n"
            + sample
        )

# ────────────────────────────────────────────────────────────────────────────
# Dosya okuma yardımcıları
# ────────────────────────────────────────────────────────────────────────────

def _read_csv(path: Path) -> List[Tuple]:
    with open(path, newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        if rdr.fieldnames is None:
            raise ValueError("CSV dosyası boş veya başlık satırı eksik.")
        norm_fieldnames = [_norm_key(h) for h in rdr.fieldnames]
        _validate_columns(norm_fieldnames)

        rows = []
        for raw in rdr:
            r = {_norm_key(k): v for k, v in raw.items()}
            rows.append(
                (
                    r["barcode"].strip(),
                    int(r["warehouse_id"]),
                    r["item_code"].strip(),
                    float(r.get("multiplier") or 1),
                )
            )
        return rows


def _read_xlsx(path: Path) -> List[Tuple]:
    df = pd.read_excel(path, dtype=str)
    df.columns = [_norm_key(c) for c in df.columns]  # başlıkları normalize et
    _validate_columns(df.columns)

    # multiplier kolonunu güvenli şekilde işle
    if "multiplier" in df.columns:
        df["multiplier"] = df["multiplier"].fillna(1).astype(float)
    else:
        df["multiplier"] = 1.0

    return list(
        zip(
            df["barcode"].str.strip(),
            df["warehouse_id"].astype(int),
            df["item_code"].str.strip(),
            df["multiplier"],
        )
    )

# ────────────────────────────────────────────────────────────────────────────
# Ana fonksiyon
# ────────────────────────────────────────────────────────────────────────────

def load_file(path: str) -> Tuple[int, float, int]:
    """CSV / XLSX dosyayı içeri alıp DB’ye yazar.

    Döner ⇒ (işlenen satır sayısı, geçen süre sn, hata adedi)
    """
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Dosya bulunamadı: {path_obj}")

    rows = _read_csv(path_obj) if path_obj.suffix.lower() == ".csv" else _read_xlsx(path_obj)

    conn = get_connection(False)  # tek transaction
    cur = conn.cursor()
    cur.fast_executemany = True

    t0 = time.time()
    err = 0
    done = 0
    try:
        if rows:  # boş dosya kontrolü
            cur.executemany(SQL, rows)  # tek seferde bütün satırlar
            conn.commit()
            done = len(rows)
    except ValueError as exc:  # biçim hatası
        err = 1
        print(f"[import_barcodes] Biçim/başlık hatası → {exc}")
        conn.rollback()
    except Exception as exc:  # DB veya diğer hatalar
        err = 1
        print(f"[import_barcodes] DB hatası → {exc}")
        conn.rollback()
    finally:
        conn.close()

    return done, time.time() - t0, err
