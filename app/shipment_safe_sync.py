"""
Güvenli Paket Senkronizasyonu
=============================
Kısmi sevkiyat senaryolarını destekleyen güvenli paket yönetimi.
Yüklenmiş paketleri korur, sadece bekleyen paketleri değiştirir.
"""
from typing import Dict, Any, Optional, List
import logging
from app.dao.logo import exec_sql, fetch_all, fetch_one

log = logging.getLogger(__name__)

def safe_sync_packages(trip_id: int, new_pkg_total: int) -> Dict[str, Any]:
    """
    shipment_loaded tablosunu güvenli şekilde senkronize eder.
    Yüklenmiş paketleri (loaded=1) korur, sadece bekleyen paketleri değiştirir.
    
    Args:
        trip_id: Sevkiyat ID
        new_pkg_total: Yeni toplam paket sayısı
        
    Returns:
        Dict: {"success": bool, "message": str, "loaded_count": int, "changes": list}
    """
    result = {
        "success": True,
        "message": "",
        "loaded_count": 0,
        "changes": []
    }
    
    try:
        # 1. Mevcut durumu analiz et
        current_state = fetch_one("""
            SELECT 
                COUNT(*) as total_packages,
                COUNT(CASE WHEN loaded = 1 THEN 1 END) as loaded_count,
                MAX(CASE WHEN loaded = 1 THEN pkg_no END) as max_loaded_pkg
            FROM shipment_loaded 
            WHERE trip_id = ?
        """, trip_id)
        
        if not current_state:
            # Hiç kayıt yok, yeni paketler oluştur
            for pkg_no in range(1, new_pkg_total + 1):
                exec_sql("""
                    INSERT INTO shipment_loaded 
                    (trip_id, pkg_no, loaded, loaded_by, loaded_time)
                    VALUES (?, ?, 0, NULL, NULL)
                """, trip_id, pkg_no)
                result["changes"].append(f"Paket #{pkg_no} oluşturuldu")
            
            result["message"] = f"{new_pkg_total} yeni paket oluşturuldu"
            return result
            
        # Mevcut durum değerleri
        total_packages = current_state.get('total_packages', 0) or 0
        loaded_count = current_state.get('loaded_count', 0) or 0
        max_loaded_pkg = current_state.get('max_loaded_pkg', 0) or 0
        
        result["loaded_count"] = loaded_count
        
        # 2. Kısıtlamaları kontrol et
        # Önemli olan yüklenmiş paket NUMARASI, sayı değil!
        if new_pkg_total < max_loaded_pkg:
            result["success"] = False
            result["message"] = f"HATA: Paket #{max_loaded_pkg} zaten yüklenmiş! En az {max_loaded_pkg} paket olmalı."
            return result
        
        # 3. Mevcut paket listelerini al
        all_packages = fetch_all("""
            SELECT pkg_no, loaded 
            FROM shipment_loaded 
            WHERE trip_id = ? 
            ORDER BY pkg_no
        """, trip_id)
        
        existing_pkg_nos = [row['pkg_no'] for row in all_packages]
        loaded_pkg_nos = [row['pkg_no'] for row in all_packages if row['loaded'] == 1]
        
        # 4. Hedef paket numaraları
        expected_pkg_nos = set(range(1, new_pkg_total + 1))
        existing_set = set(existing_pkg_nos)
        loaded_set = set(loaded_pkg_nos)
        
        # 5. Eksik paketleri ekle (boşlukları doldur)
        missing_packages = expected_pkg_nos - existing_set
        if missing_packages:
            for pkg_no in sorted(missing_packages):
                exec_sql("""
                    INSERT INTO shipment_loaded 
                    (trip_id, pkg_no, loaded, loaded_by, loaded_time)
                    VALUES (?, ?, 0, NULL, NULL)
                """, trip_id, pkg_no)
                result["changes"].append(f"Paket #{pkg_no} eklendi")
        
        # 6. Fazla paketleri sil (SADECE YÜKLENMEMİŞ OLANLAR)
        extra_packages = existing_set - expected_pkg_nos
        if extra_packages:
            for pkg_no in sorted(extra_packages):
                if pkg_no not in loaded_set:  # Yüklenmemişse sil
                    exec_sql("""
                        DELETE FROM shipment_loaded 
                        WHERE trip_id = ? AND pkg_no = ?
                    """, trip_id, pkg_no)
                    result["changes"].append(f"Paket #{pkg_no} silindi")
                else:
                    result["changes"].append(f"Paket #{pkg_no} yüklenmiş, silinemez!")
                    result["success"] = False
                    result["message"] = f"HATA: Paket #{pkg_no} yüklenmiş durumda, silinemez!"
                    return result
        
        # 7. Başarı mesajı
        if not result["message"]:
            if result["changes"]:
                result["message"] = f"Paketler güncellendi: {len(result['changes'])} değişiklik"
            else:
                result["message"] = "Değişiklik yok, paketler zaten senkronize"
                
    except Exception as e:
        result["success"] = False
        result["message"] = f"Hata: {str(e)}"
        log.error(f"safe_sync_packages hatası: {e}")
        
    return result