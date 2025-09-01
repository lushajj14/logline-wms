"""
Remote Configuration Client
============================
Config Server'dan yapılandırma çeken client modülü.
"""

import os
import sys
import json
import uuid
import socket
import logging
import requests
from pathlib import Path
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

class RemoteConfigClient:
    """Config Server'dan yapılandırma çeken client."""
    
    def __init__(self, server_url: str = None):
        """
        Initialize remote config client.
        
        Args:
            server_url: Config server URL (örn: http://192.168.5.100:8001)
        """
        # Config server URL - önce config.ini'den oku, yoksa default kullan
        self.server_url = server_url or self._get_server_url()
        self.machine_id = self._get_machine_id()
        self.hostname = socket.gethostname()
        self.username = os.getenv("USERNAME", "unknown")
        self.app_version = self._get_app_version()
        
        # Cache için
        self.cached_config = None
        self.cache_file = Path.home() / ".wms_config_cache.json"
        
        logger.info(f"RemoteConfigClient initialized: {self.server_url}")
    
    def _get_server_url(self) -> str:
        """Config server URL'ini belirle."""
        # 1. Environment variable (override için)
        if os.getenv("WMS_CONFIG_SERVER"):
            return os.getenv("WMS_CONFIG_SERVER")
        
        # 2. Harici config.ini dosyası (opsiyonel)
        config_paths = [
            Path("config.ini"),
            Path(sys.executable).parent / "config.ini",
            Path.home() / ".wms" / "config.ini"
        ]
        
        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        for line in f:
                            if line.startswith("server="):
                                server_url = line.split("=", 1)[1].strip()
                                logger.info(f"Using server from config.ini: {server_url}")
                                return server_url
                except Exception as e:
                    logger.warning(f"Failed to read config from {config_path}: {e}")
        
        # 3. HARDCODED DEFAULTS (exe'ye gömülü)
        # Önce VPN IP'yi dene, bağlanamazsa public IP'ye geç
        servers = [
            "http://192.168.5.100:8001",  # VPN üzerinden (hızlı)
            "http://78.135.108.160:8001"   # Public IP (yedek)
        ]
        
        for server in servers:
            try:
                # Hızlı bağlantı testi
                import requests
                response = requests.get(f"{server}/", timeout=2)
                if response.status_code == 200:
                    logger.info(f"Using server: {server}")
                    return server
            except:
                logger.debug(f"Server unreachable: {server}")
                continue
        
        # Hiçbirine bağlanamazsa ilkini döndür (cache kullanır)
        logger.warning(f"No server reachable, using default: {servers[0]}")
        return servers[0]
    
    def _get_machine_id(self) -> str:
        """Makine ID'sini al (MAC adresi bazlı)."""
        try:
            # Windows için WMI kullan
            if sys.platform == "win32":
                import subprocess
                result = subprocess.run(
                    ["wmic", "csproduct", "get", "UUID"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        machine_uuid = lines[1].strip()
                        if machine_uuid and machine_uuid != "UUID":
                            return machine_uuid
        except Exception as e:
            logger.warning(f"Failed to get machine UUID: {e}")
        
        # Fallback: MAC address
        return str(uuid.getnode())
    
    def _get_app_version(self) -> str:
        """Uygulama versiyonunu al."""
        version_file = Path("version.txt")
        if version_file.exists():
            try:
                return version_file.read_text().strip()
            except:
                pass
        return "2.0.0"  # Default version
    
    def fetch_config(self, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Config Server'dan yapılandırmayı çek.
        
        Args:
            use_cache: Cache kullanılsın mı (offline durumlar için)
            
        Returns:
            Config dictionary veya None
        """
        try:
            # Önce sunucudan çekmeyi dene
            logger.info(f"Fetching config from {self.server_url}")
            
            response = requests.post(
                f"{self.server_url}/desktop/config",
                json={
                    "machine_id": self.machine_id,
                    "hostname": self.hostname,
                    "username": self.username,
                    "app_version": self.app_version
                },
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                config = data.get("config", {})
                
                # Version kontrolü
                version_info = data.get("version_info", {})
                if version_info.get("update_available"):
                    logger.warning(f"Update available: {version_info.get('current_version')}")
                    print(f"\n[UYARI] Yeni versiyon mevcut: {version_info.get('current_version')}")
                    print(f"   Indirmek icin: {version_info.get('update_url')}\n")
                
                # Cache'e kaydet
                self._save_cache(config)
                
                # Environment'a yükle
                self._load_to_environment(config)
                
                logger.info("Config successfully fetched and loaded")
                return config
            
            elif response.status_code == 403:
                logger.error(f"Machine not authorized: {self.machine_id}")
                print("\n[HATA] Bu bilgisayar yetkilendirilmemis!")
                print(f"   Machine ID: {self.machine_id}")
                print("   Sistem yöneticisine başvurun.\n")
                return None
            
            else:
                logger.error(f"Config fetch failed: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            logger.warning("Config server unreachable, trying cache...")
        except requests.exceptions.Timeout:
            logger.warning("Config server timeout, trying cache...")
        except Exception as e:
            logger.error(f"Config fetch error: {e}")
        
        # Sunucu erişilemiyorsa cache kullan
        if use_cache:
            return self._load_cache()
        
        return None
    
    def _load_to_environment(self, config: Dict[str, Any]):
        """Config değerlerini environment variable'lara yükle."""
        for key, value in config.items():
            os.environ[key] = str(value)
        logger.debug(f"Loaded {len(config)} config values to environment")
    
    def _save_cache(self, config: Dict[str, Any]):
        """Config'i cache dosyasına kaydet."""
        try:
            cache_data = {
                "config": config,
                "timestamp": datetime.now().isoformat(),
                "machine_id": self.machine_id
            }
            
            self.cache_file.write_text(
                json.dumps(cache_data, indent=2),
                encoding='utf-8'
            )
            logger.debug(f"Config cached to {self.cache_file}")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")
    
    def _load_cache(self) -> Optional[Dict[str, Any]]:
        """Cache'den config yükle."""
        if not self.cache_file.exists():
            logger.warning("No cached config found")
            return None
        
        try:
            cache_data = json.loads(
                self.cache_file.read_text(encoding='utf-8')
            )
            
            config = cache_data.get("config", {})
            timestamp = cache_data.get("timestamp", "unknown")
            
            logger.info(f"Using cached config from {timestamp}")
            print(f"\n[UYARI] Offline mod - Cache kullaniliyor (Son guncelleme: {timestamp})\n")
            
            # Environment'a yükle
            self._load_to_environment(config)
            
            return config
            
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")
            return None
    
    def register_machine(self) -> bool:
        """Makineyi config server'a kaydet."""
        try:
            response = requests.post(
                f"{self.server_url}/desktop/register",
                json={
                    "machine_id": self.machine_id,
                    "hostname": self.hostname,
                    "username": self.username,
                    "app_version": self.app_version
                },
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info("Machine registered successfully")
                return True
                
        except Exception as e:
            logger.error(f"Machine registration failed: {e}")
        
        return False
    
    def send_heartbeat(self) -> bool:
        """Heartbeat gönder (canlılık sinyali)."""
        try:
            response = requests.post(
                f"{self.server_url}/desktop/heartbeat",
                json={"machine_id": self.machine_id},
                timeout=2
            )
            return response.status_code == 200
        except:
            return False
    
    def check_update(self) -> Optional[Dict[str, Any]]:
        """Güncelleme kontrolü yap."""
        try:
            response = requests.get(
                f"{self.server_url}/desktop/version",
                params={"current": self.app_version},
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json()
                
        except Exception as e:
            logger.error(f"Update check failed: {e}")
        
        return None


from datetime import datetime

def initialize_remote_config() -> bool:
    """
    Remote config'i başlat ve test et.
    
    Returns:
        Başarılı ise True
    """
    try:
        client = RemoteConfigClient()
        config = client.fetch_config()
        
        if config:
            print("[OK] Remote config basariyla yuklendi!")
            return True
        else:
            print("[HATA] Remote config yuklenemedi!")
            return False
            
    except Exception as e:
        print(f"[HATA] Remote config hatasi: {e}")
        return False