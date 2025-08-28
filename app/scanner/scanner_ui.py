"""
scanner_ui.py – Depo barkod doğrulama v0.6
=========================================
* Treeview kolonları: AMB | Stok | Ürün | İst | Oku | Eksik
* "✔ Tamamla" butonu: eksik satır varsa backorders’a yazar; koli adedi sorar.
* `warehouse_id` satırdan gelir → backorders’a doğru gider.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from pathlib import Path
import sys, logging
from typing import Dict, List

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

try:
    from app.dao import logo as dao
    import app.backorder as bo
except ModuleNotFoundError:
    import dao.logo as dao
    import backorder as bo

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")

# ---------------------------------------------------------------------------
# STATUS=2 sipariş başlıkları
# ---------------------------------------------------------------------------

def fetch_picking_orders() -> List[Dict]:
    sql = f"""
    SELECT F.LOGICALREF AS order_id,
           F.FICHENO    AS order_no,
           C.CODE       AS customer_code,
           C.DEFINITION_ AS customer_name
    FROM {dao._t('ORFICHE')} F
    JOIN {dao._t('CLCARD', period_dependent=False)} C ON C.LOGICALREF = F.CLIENTREF
    WHERE F.STATUS = 2 AND F.CANCELLED = 0
    ORDER BY F.FICHENO;"""
    with dao.get_conn() as cn:
        cur = cn.execute(sql)
        cols = [c[0].lower() for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

# ---------------------------------------------------------------------------
class ScannerUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sipariş Barkod Doğrulama")
        self.geometry("1000x600")

        self.current_order: Dict | None = None
        self.lines: List[Dict] = []           # sipariş satırları
        self.counts: Dict[str, float] = {}    # item_code → okutulan

        self.create_widgets()
        self.populate_orders()

    # -------------------- UI --------------------
    def create_widgets(self):
        f_top = ttk.Frame(self); f_top.pack(fill="x", padx=10, pady=10)
        ttk.Label(f_top, text="Sipariş:").pack(side="left")
        self.cmb_orders = ttk.Combobox(f_top, width=35, state="readonly")
        self.cmb_orders.pack(side="left", padx=5)
        ttk.Button(f_top, text="Yükle", command=self.load_order).pack(side="left")
        ttk.Button(f_top, text="✔ Tamamla", command=self.finish_order).pack(side="right")

        cols = ("amb", "stok", "ad", "ist", "oku", "eksik")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=22)
        for col, txt, w in [
            ("amb", "AMB", 45),
            ("stok", "Stok Kodu", 140),
            ("ad", "Ürün Adı", 450),
            ("ist", "İst", 60),
            ("oku", "Oku", 60),
            ("eksik", "Eksik", 60)]:
            self.tree.heading(col, text=txt); self.tree.column(col, width=w, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=10)

        self.entry = tk.Entry(self); self.entry.pack(); self.entry.focus_set()
        self.entry.bind("<Return>", self.on_scan)
        self.status_lbl = ttk.Label(self, text="Barkod bekleniyor", foreground="blue")
        self.status_lbl.pack(pady=5)

    # -------------------- Sipariş listesi ---------------
    def populate_orders(self):
        orders = fetch_picking_orders()
        self.orders_map = {f"{o['order_no']} – {o['customer_code']}": o for o in orders}
        self.cmb_orders["values"] = list(self.orders_map.keys())
        if orders:
            self.cmb_orders.current(0)

    # -------------------- Sipariş yükle ---------------
    def load_order(self):
        sel = self.cmb_orders.get()
        if not sel:
            messagebox.showinfo("Bilgi", "Lütfen sipariş seçin"); return
        self.current_order = self.orders_map[sel]
        self.lines = dao.fetch_order_lines(self.current_order["order_id"])
        self.counts = {l["item_code"]: 0 for l in self.lines}
        self.refresh_tree()
        self.status_lbl.config(text=f"{self.current_order['order_no']} yüklendi ✅", foreground="green")
        self.entry.focus_set()

    # -------------------- Barkod okutma ---------------
    def on_scan(self, _):
        code = self.entry.get().strip(); self.entry.delete(0, "end")
        if not code or not self.current_order:
            return
        ln = next((l for l in self.lines if l["item_code"] == code), None)
        if not ln:
            self.status_lbl.config(text=f"{code} siparişte yok", foreground="red"); self.bell(); return
        self.counts[code] += 1
        self.refresh_tree()

    # -------------------- Treeview refresh ------------
    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for l in self.lines:
            ic = l["item_code"]; ordered = l["qty_ordered"]; scanned = self.counts.get(ic,0)
            eksik = max(0, ordered - scanned)
            vals = (l["warehouse_id"], ic, l["item_name"], ordered, scanned, eksik)
            iid = self.tree.insert("", "end", values=vals)
            if eksik==0:
                self.tree.item(iid, tags=("ok",))
        self.tree.tag_configure("ok", background="#c8e6c9")

    # -------------------- Tamamla butonu ---------------
    def finish_order(self):
        if not self.current_order:
            return
        order_id = self.current_order["order_id"]; order_no = self.current_order["order_no"]
        koli = simpledialog.askinteger("Koli", "Kaç koli çıkacak?", minvalue=1, initialvalue=1)
        if koli is None:
            return
        try:
            for l in self.lines:
                missing = l["qty_ordered"] - self.counts.get(l["item_code"],0)
                if missing>0:
                    bo.insert_backorder(order_no, l["line_id"], l["warehouse_id"], l["item_code"], missing, None)
            dao.update_order_header(order_id, genexp4=f"PAKET SAYISI : {koli}", genexp5=order_no)
            dao.update_order_status(order_id, 4)
            self.status_lbl.config(text="Sipariş tamamlandı", foreground="blue"); self.bell()
        except Exception as e:
            logging.error("Tamamlama hatası: %s", e); self.status_lbl.config(text="DB hatası", foreground="red"); return
        self.lines=[]; self.counts={}; self.refresh_tree(); self.populate_orders(); self.current_order=None

# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ScannerUI().mainloop()
