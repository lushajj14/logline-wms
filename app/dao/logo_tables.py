"""
Logo ERP Tablo Yönetimi
========================
Tüm Logo tablo adlarını merkezi olarak yönetir.
Yıllık dönem/firma değişikliklerinde sadece config değişir, kod değişmez.

Kullanım:
    from app.dao.logo_tables import LogoTables

    # Tablo adına erişim
    cursor.execute(f"SELECT * FROM {LogoTables.ORFICHE} WHERE STATUS = 1")

    # Veya kısa alias ile
    from app.dao.logo_tables import T
    cursor.execute(f"SELECT * FROM {T.ORFICHE}")

Konfigürasyon:
    - LOGO_COMPANY_NR: Firma kodu (örn: "025", "026")
    - LOGO_PERIOD_NR: Dönem kodu (örn: "01", "02")
    - Kaynak: settings.json > environment variables > defaults
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Konfigürasyon Yükleme
# ---------------------------------------------------------------------------

def _get_logo_config() -> tuple[str, str]:
    """
    Logo firma ve dönem numaralarını al.
    Öncelik: settings.json > environment > defaults

    Returns:
        Tuple (company_nr, period_nr)
    """
    company_nr = None
    period_nr = None

    # 1. Önce settings.json'dan dene (db.company_nr veya logo.company_nr)
    try:
        from app.settings_manager import get_manager
        manager = get_manager()
        # Settings UI'da db.company_nr olarak kaydediliyor
        company_nr = manager.get("db.company_nr") or manager.get("logo.company_nr")
        period_nr = manager.get("db.period_nr") or manager.get("logo.period_nr")
    except Exception as e:
        logger.debug(f"Settings'den Logo config okunamadı: {e}")

    # 2. Environment variables
    if not company_nr:
        company_nr = os.getenv("LOGO_COMPANY_NR")
    if not period_nr:
        period_nr = os.getenv("LOGO_PERIOD_NR")

    # 3. env_config'den al (remote config dahil)
    if not company_nr or not period_nr:
        try:
            from app.config.env_config import get_config
            config = get_config()
            db_config = config.get_database_config()
            if not company_nr:
                company_nr = db_config.get("company_nr")
            if not period_nr:
                period_nr = db_config.get("period_nr")
        except Exception as e:
            logger.debug(f"env_config'den Logo config okunamadı: {e}")

    # 4. Defaults
    company_nr = company_nr or "025"
    period_nr = period_nr or "01"

    logger.debug(f"Logo config: company={company_nr}, period={period_nr}")
    return company_nr, period_nr


# ---------------------------------------------------------------------------
# Logo Tablo Sınıfı
# ---------------------------------------------------------------------------

class _LogoTablesMeta(type):
    """
    Metaclass for lazy-loading Logo table names.
    Tablolar ilk erişimde oluşturulur, böylece config değişikliklerini yakalar.
    """

    _company_nr: Optional[str] = None
    _period_nr: Optional[str] = None
    _tables_cache: dict = {}

    def _ensure_config(cls):
        """Config'i yükle veya cache'den al."""
        if cls._company_nr is None:
            cls._company_nr, cls._period_nr = _get_logo_config()

    def _period_table(cls, name: str) -> str:
        """Period-dependent tablo adı (örn: LG_025_01_ORFICHE)"""
        cls._ensure_config()
        return f"LG_{cls._company_nr}_{cls._period_nr}_{name}"

    def _company_table(cls, name: str) -> str:
        """Period-independent tablo adı (örn: LG_025_ITEMS)"""
        cls._ensure_config()
        return f"LG_{cls._company_nr}_{name}"

    def reload_config(cls):
        """Config'i yeniden yükle (runtime değişikliği için)."""
        cls._company_nr = None
        cls._period_nr = None
        cls._tables_cache.clear()
        cls._ensure_config()
        logger.info(f"Logo tables config reloaded: {cls._company_nr}_{cls._period_nr}")

    @property
    def COMPANY_NR(cls) -> str:
        """Aktif firma numarası."""
        cls._ensure_config()
        return cls._company_nr

    @property
    def PERIOD_NR(cls) -> str:
        """Aktif dönem numarası."""
        cls._ensure_config()
        return cls._period_nr

    # ═══════════════════════════════════════════════════════════════════════
    # PERIOD-DEPENDENT TABLOLAR (Yıllık değişen)
    # ═══════════════════════════════════════════════════════════════════════

    @property
    def ORFICHE(cls) -> str:
        """Sipariş fişleri (header) - LG_XXX_YY_ORFICHE"""
        return cls._period_table("ORFICHE")

    @property
    def ORFLINE(cls) -> str:
        """Sipariş satırları - LG_XXX_YY_ORFLINE"""
        return cls._period_table("ORFLINE")

    @property
    def STFICHE(cls) -> str:
        """Stok/Ambar fişleri - LG_XXX_YY_STFICHE"""
        return cls._period_table("STFICHE")

    @property
    def STLINE(cls) -> str:
        """Stok hareket satırları - LG_XXX_YY_STLINE"""
        return cls._period_table("STLINE")

    @property
    def INVOICE(cls) -> str:
        """Faturalar - LG_XXX_YY_INVOICE"""
        return cls._period_table("INVOICE")

    @property
    def INVLINE(cls) -> str:
        """Fatura satırları - LG_XXX_YY_INVLINE"""
        return cls._period_table("INVLINE")

    @property
    def CLFICHE(cls) -> str:
        """Cari fişleri - LG_XXX_YY_CLFICHE"""
        return cls._period_table("CLFICHE")

    @property
    def CLFLINE(cls) -> str:
        """Cari fiş satırları - LG_XXX_YY_CLFLINE"""
        return cls._period_table("CLFLINE")

    @property
    def EMFICHE(cls) -> str:
        """Personel fişleri - LG_XXX_YY_EMFICHE"""
        return cls._period_table("EMFICHE")

    @property
    def EMFLINE(cls) -> str:
        """Personel fiş satırları - LG_XXX_YY_EMFLINE"""
        return cls._period_table("EMFLINE")

    # ═══════════════════════════════════════════════════════════════════════
    # PERIOD-INDEPENDENT TABLOLAR (Sabit)
    # ═══════════════════════════════════════════════════════════════════════

    @property
    def ITEMS(cls) -> str:
        """Stok kartları (malzemeler) - LG_XXX_ITEMS"""
        return cls._company_table("ITEMS")

    @property
    def CLCARD(cls) -> str:
        """Cari kartlar (müşteri/tedarikçi) - LG_XXX_CLCARD"""
        return cls._company_table("CLCARD")

    @property
    def UNITSETF(cls) -> str:
        """Birim setleri - LG_XXX_UNITSETF"""
        return cls._company_table("UNITSETF")

    @property
    def UNITSETL(cls) -> str:
        """Birim set satırları - LG_XXX_UNITSETL"""
        return cls._company_table("UNITSETL")

    @property
    def ITMUNITA(cls) -> str:
        """Malzeme birim tanımları - LG_XXX_ITMUNITA"""
        return cls._company_table("ITMUNITA")

    @property
    def SPECODES(cls) -> str:
        """Özel kodlar - LG_XXX_SPECODES"""
        return cls._company_table("SPECODES")

    @property
    def PAYPLANS(cls) -> str:
        """Ödeme planları - LG_XXX_PAYPLANS"""
        return cls._company_table("PAYPLANS")

    @property
    def EMPLYEE(cls) -> str:
        """Personel kartları - LG_XXX_EMPLYEE"""
        return cls._company_table("EMPLYEE")

    @property
    def PROJECT(cls) -> str:
        """Proje kartları - LG_XXX_PROJECT"""
        return cls._company_table("PROJECT")


class LogoTables(metaclass=_LogoTablesMeta):
    """
    Logo ERP tablo adları.

    Period-dependent (yıllık değişen):
        - ORFICHE: Sipariş fişleri
        - ORFLINE: Sipariş satırları
        - STFICHE: Stok fişleri
        - STLINE: Stok satırları
        - INVOICE: Faturalar
        - CLFICHE: Cari fişler

    Period-independent (sabit):
        - ITEMS: Stok kartları
        - CLCARD: Cari kartlar
        - UNITSETF/L: Birim setleri

    Kullanım:
        from app.dao.logo_tables import LogoTables

        query = f"SELECT * FROM {LogoTables.ORFICHE} WHERE STATUS = 1"

    Config değişikliği:
        LogoTables.reload_config()  # Runtime'da yeniden yükle
    """
    pass


# Kısa alias
T = LogoTables


# ---------------------------------------------------------------------------
# Yardımcı Fonksiyonlar
# ---------------------------------------------------------------------------

def get_table(name: str, period_dependent: bool = True) -> str:
    """
    Dinamik tablo adı oluştur.

    Args:
        name: Tablo adı (örn: "ORFICHE")
        period_dependent: True ise LG_XXX_YY_name, False ise LG_XXX_name

    Returns:
        Tam tablo adı
    """
    if period_dependent:
        return LogoTables._period_table(name)
    return LogoTables._company_table(name)


def get_current_config() -> dict:
    """
    Aktif Logo konfigürasyonunu döndür.

    Returns:
        {"company_nr": "025", "period_nr": "01", "tables": {...}}
    """
    return {
        "company_nr": LogoTables.COMPANY_NR,
        "period_nr": LogoTables.PERIOD_NR,
        "period_dependent_prefix": f"LG_{LogoTables.COMPANY_NR}_{LogoTables.PERIOD_NR}_",
        "company_prefix": f"LG_{LogoTables.COMPANY_NR}_",
        "tables": {
            "ORFICHE": LogoTables.ORFICHE,
            "ORFLINE": LogoTables.ORFLINE,
            "STFICHE": LogoTables.STFICHE,
            "ITEMS": LogoTables.ITEMS,
            "CLCARD": LogoTables.CLCARD,
        }
    }
