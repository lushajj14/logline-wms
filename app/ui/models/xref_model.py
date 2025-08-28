from PyQt5 import QtCore
from app.dao.logo import fetch_one, fetch_all

class XrefModel(QtCore.QAbstractTableModel):
    """
    barcode_xref tablosu için tembel-yüklemeli model.
    • rowCount  → toplam satır (COUNT(*))
    • fetchMore → her seferde batch (1 000) satır çeker
    """
    batch   = 1000
    headers = ["Barkod", "Depo", "Stok Kodu", "Çarpan", "Güncelleme"]

    def __init__(self, wh_filter: str | None = None, text: str = ""):
        super().__init__()
        self.wh_filter = wh_filter
        self.text      = text
        self.rows: list[list] = []

        # toplam satır sayısını bir kez al
        where, params = self._where()
        cnt_sql = f"SELECT COUNT(*) AS n FROM dbo.barcode_xref {where}"
        self.total = fetch_one(cnt_sql, *params)["n"]

    # ---------- Qt zorunlu metotlar ----------------------------------------
    def rowCount(self, parent):    return self.total
    def columnCount(self, parent): return len(self.headers)

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self.headers[section]

    def data(self, idx, role):
        if role != QtCore.Qt.DisplayRole:
            return None

        # İstenen satır henüz bellekte değilse getir
        if idx.row() >= len(self.rows):
            self.fetchMore(QtCore.QModelIndex())
            if idx.row() >= len(self.rows):        # hâlâ yoksa boş döndür
                return None

        return self.rows[idx.row()][idx.column()]

    # ---------- Lazy-loading mantığı ---------------------------------------
    def canFetchMore(self, parent):
        return len(self.rows) < self.total

   
     # ---------------------------------------- Lazy-loading
    # ---------------------------------------- Lazy-loading
    def fetchMore(
        self,
        parent: QtCore.QModelIndex = QtCore.QModelIndex()
    ) -> None:
        """
        Eksik satırları veritabanından çeker ve modele ekler.
        Her çağrıda 'batch' (default = 1000) satır alır.
        """
        offset = len(self.rows)                       # Şu ana kadar yüklenen
        if offset >= self.total:                      # Hepsi geldiyse çık
            return

        # ─ Sorgu hazırlığı ────────────────────────────────────────────────
        where, params = self._where()
        sql = (
            "SELECT barcode, warehouse_id, item_code, multiplier, updated_at "
            "FROM dbo.barcode_xref "
            f"{where} "
            "ORDER BY updated_at DESC, barcode "
            "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
        )

        batch = fetch_all(sql, *params, offset, self.batch)

        # ─ Fallback: prefix araması 0 sonuç dönerse %…% aramasına geç ─────
        if not batch and getattr(self, "_anywhere", None):
            params[-2:] = self._anywhere            # son iki LIKE parametresini değiştir
            batch = fetch_all(sql, *params, offset, self.batch)
            self._anywhere = None                   # yalnızca 1 kez dene

        if not batch:                               # hâlâ boş → toplamı düzelt
            self.total = len(self.rows)
            return

        # ─ Qt’ye “yeni satırlar geliyor” sinyali ─────────────────────────
        self.beginInsertRows(QtCore.QModelIndex(),
                             offset, offset + len(batch) - 1)

        # Kolon sırasını sabit tut – multiplier’ı str yap
        self.rows.extend([
            [
                r["barcode"],
                r["warehouse_id"],
                r["item_code"],
                str(r["multiplier"]),
                r["updated_at"],
            ]
            for r in batch
        ])
        self.endInsertRows()

        # ─ Toplam satır sayısını düzelt & scrollbar’ı yenile ──────────────
        if len(batch) < self.batch or len(self.rows) >= self.total:
            self.total = len(self.rows)
            self.layoutChanged.emit()


    # ---------- Yardımcı filtre oluşturucu ---------------------------------
    def _where(self):
        clauses, params = [], []

        # Depo filtresi
        if self.wh_filter is not None:
            clauses.append("warehouse_id = ?")
            params.append(self.wh_filter)

        if self.text:
            q = self.text.strip().upper()

            # 1. Hızlı önek araması  (indeks kullanır)
            prefix = q if q.startswith('%') else q + '%'
            clauses.append("("
                           "UPPER(barcode)      LIKE ? OR "
                           "UPPER(item_code)    LIKE ? OR "
                           "UPPER(item_code_np) LIKE ?)"
                           )
            params.extend([prefix, prefix, prefix])

            # 2. Hiç sonuç çıkmazsa fallback için %...% kalıbını hazırla
            any_ = '%' + q.strip('%') + '%'
            self._anywhere = (any_, any_, any_)
        else:
            self._anywhere = None

        return ("WHERE " + " AND ".join(clauses)) if clauses else "", params
