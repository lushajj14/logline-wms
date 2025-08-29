"""
Thread-Safe Cache Implementation
=================================
Thread-safe caching with TTL and size limits.
"""
import threading
import time
from typing import Any, Dict, Optional, Callable
from collections import OrderedDict
import weakref
import logging

logger = logging.getLogger(__name__)


class ThreadSafeCache:
    """Thread-safe cache with TTL and size limits."""
    
    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: Optional[int] = None,
        name: str = "cache"
    ):
        """
        Initialize thread-safe cache.
        
        Args:
            max_size: Maximum number of items in cache
            ttl_seconds: Time-to-live in seconds (None for no expiry)
            name: Cache name for logging
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.name = name
        
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: Dict[Any, float] = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        
        logger.debug(f"ThreadSafeCache '{name}' initialized (max_size={max_size}, ttl={ttl_seconds})")
    
    def get(self, key: Any, default: Any = None) -> Any:
        """
        Get item from cache.
        
        Args:
            key: Cache key
            default: Default value if not found
            
        Returns:
            Cached value or default
        """
        with self._lock:
            # Check if key exists
            if key not in self._cache:
                self._misses += 1
                return default
            
            # Check TTL if enabled
            if self.ttl_seconds is not None:
                timestamp = self._timestamps.get(key, 0)
                if time.time() - timestamp > self.ttl_seconds:
                    # Expired, remove it
                    del self._cache[key]
                    del self._timestamps[key]
                    self._misses += 1
                    return default
            
            # Move to end (LRU)
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]
    
    def set(self, key: Any, value: Any) -> None:
        """
        Set item in cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        with self._lock:
            # Remove oldest if at capacity
            if key not in self._cache and len(self._cache) >= self.max_size:
                # Remove oldest (first) item
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                if oldest_key in self._timestamps:
                    del self._timestamps[oldest_key]
            
            # Add or update
            self._cache[key] = value
            self._cache.move_to_end(key)
            
            # Update timestamp
            if self.ttl_seconds is not None:
                self._timestamps[key] = time.time()
    
    def delete(self, key: Any) -> bool:
        """
        Delete item from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if item was deleted, False if not found
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                if key in self._timestamps:
                    del self._timestamps[key]
                return True
            return False
    
    def clear(self) -> None:
        """Clear all items from cache."""
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()
            logger.debug(f"Cache '{self.name}' cleared")
    
    def size(self) -> int:
        """Get current cache size."""
        with self._lock:
            return len(self._cache)
    
    def contains(self, key: Any) -> bool:
        """Check if key exists in cache (considers TTL)."""
        return self.get(key, object()) is not object()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            
            return {
                'name': self.name,
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': f"{hit_rate:.1f}%",
                'ttl_seconds': self.ttl_seconds
            }
    
    def reset_stats(self) -> None:
        """Reset hit/miss statistics."""
        with self._lock:
            self._hits = 0
            self._misses = 0
    
    def cleanup_expired(self) -> int:
        """
        Remove expired items from cache.
        
        Returns:
            Number of items removed
        """
        if self.ttl_seconds is None:
            return 0
        
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, timestamp in self._timestamps.items()
                if current_time - timestamp > self.ttl_seconds
            ]
            
            for key in expired_keys:
                if key in self._cache:
                    del self._cache[key]
                del self._timestamps[key]
            
            if expired_keys:
                logger.debug(f"Cache '{self.name}' cleaned up {len(expired_keys)} expired items")
            
            return len(expired_keys)


class BarcodeCache(ThreadSafeCache):
    """Specialized cache for barcode lookups."""
    
    def __init__(self, max_size: int = 500):
        super().__init__(
            max_size=max_size,
            ttl_seconds=300,  # 5 minutes TTL
            name="barcode_cache"
        )
    
    def get_barcode(
        self,
        barcode: str,
        order_id: int,
        lookup_func: Optional[Callable] = None
    ) -> Optional[tuple]:
        """
        Get barcode lookup result with automatic fetch.
        
        Args:
            barcode: Barcode string
            order_id: Order ID for cache key
            lookup_func: Function to call if not in cache
            
        Returns:
            Tuple of (matched_line, qty_inc) or None
        """
        cache_key = f"{barcode}_{order_id}"
        
        # Try cache first
        result = self.get(cache_key)
        if result is not None:
            return result
        
        # If lookup function provided, fetch and cache
        if lookup_func:
            try:
                result = lookup_func(barcode)
                if result:
                    self.set(cache_key, result)
                return result
            except Exception as e:
                logger.error(f"Barcode lookup failed: {e}")
                return None
        
        return None


# Global cache instances
_cache_instances: Dict[str, ThreadSafeCache] = {}
_cache_lock = threading.Lock()


def get_cache(name: str, **kwargs) -> ThreadSafeCache:
    """
    Get or create a named cache instance.
    
    Args:
        name: Cache name
        **kwargs: Arguments for ThreadSafeCache
        
    Returns:
        ThreadSafeCache instance
    """
    with _cache_lock:
        if name not in _cache_instances:
            _cache_instances[name] = ThreadSafeCache(name=name, **kwargs)
        return _cache_instances[name]


def get_barcode_cache() -> BarcodeCache:
    """Get the global barcode cache instance."""
    with _cache_lock:
        if 'barcode' not in _cache_instances:
            _cache_instances['barcode'] = BarcodeCache()
        return _cache_instances['barcode']


def clear_all_caches():
    """Clear all cache instances."""
    with _cache_lock:
        for cache in _cache_instances.values():
            cache.clear()
        logger.info(f"Cleared {len(_cache_instances)} cache instances")


def get_all_cache_stats() -> Dict[str, Dict]:
    """Get statistics for all caches."""
    with _cache_lock:
        return {
            name: cache.get_stats()
            for name, cache in _cache_instances.items()
        }