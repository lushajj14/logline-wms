#!/usr/bin/env python3
"""
Connection Pool Test Script
===========================
Bu script connection pool performansını test eder ve benchmark yapar.

Kullanım:
    python test_connection_pool.py [--no-pool] [--threads 10] [--operations 100]

Argümanlar:
    --no-pool: Connection pool kullanmadan test et
    --threads: Concurrent thread sayısı (default: 10)
    --operations: Her thread'in yapacağı işlem sayısı (default: 50)
"""
import argparse
import concurrent.futures
import os
import sys
import time
import threading
from statistics import mean, stdev
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from app.dao.logo import get_conn, get_pool_info
    from app.dao.connection_pool import get_pool_stats
except ImportError as e:
    print(f"❌ Import hatası: {e}")
    print("Bu script'i proje root dizininde çalıştırın")
    sys.exit(1)


class ConnectionPoolTester:
    """Connection Pool test sınıfı."""
    
    def __init__(self):
        self.results = []
        self.errors = []
        self.lock = threading.Lock()
    
    def single_operation(self, operation_id: int) -> dict:
        """Tek bir veritabanı işlemi yapar."""
        start_time = time.time()
        thread_id = threading.get_ident()
        
        try:
            with get_conn() as conn:
                cursor = conn.execute("SELECT @@VERSION, GETDATE(), @@SPID")
                result = cursor.fetchone()
                
                # Basit bir query daha
                cursor = conn.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES")
                table_count = cursor.fetchone()[0]
                
                duration = time.time() - start_time
                
                return {
                    'operation_id': operation_id,
                    'thread_id': thread_id,
                    'duration': duration,
                    'success': True,
                    'connection_id': result[2] if result else None,
                    'table_count': table_count,
                    'timestamp': time.time()
                }
                
        except Exception as e:
            duration = time.time() - start_time
            with self.lock:
                self.errors.append({
                    'operation_id': operation_id,
                    'thread_id': thread_id,
                    'error': str(e),
                    'duration': duration,
                    'timestamp': time.time()
                })
            
            return {
                'operation_id': operation_id,
                'thread_id': thread_id,
                'duration': duration,
                'success': False,
                'error': str(e),
                'timestamp': time.time()
            }
    
    def run_concurrent_test(self, num_threads: int, operations_per_thread: int) -> dict:
        """Concurrent test çalıştırır."""
        print(f"[TESTING] {num_threads} thread ile {operations_per_thread} islem/thread testi basliyor...")
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            # Her thread için işlemleri hazırla
            futures = []
            for thread_num in range(num_threads):
                for op_num in range(operations_per_thread):
                    operation_id = thread_num * operations_per_thread + op_num
                    future = executor.submit(self.single_operation, operation_id)
                    futures.append(future)
            
            # Sonuçları topla
            results = []
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result(timeout=30)  # 30 saniye timeout
                    results.append(result)
                    
                    # İlerleme göster (her 50 işlemde bir)
                    if len(results) % 50 == 0:
                        print(f"  Completed: {len(results)}/{len(futures)}")
                        
                except concurrent.futures.TimeoutError:
                    print("[WARNING] Timeout error")
                    results.append({
                        'success': False,
                        'error': 'Timeout',
                        'duration': 30.0
                    })
                except Exception as e:
                    print(f"[WARNING] Future error: {e}")
                    results.append({
                        'success': False,
                        'error': str(e),
                        'duration': 0.0
                    })
        
        total_time = time.time() - start_time
        
        # İstatistikleri hesapla
        successful = [r for r in results if r.get('success', False)]
        failed = [r for r in results if not r.get('success', False)]
        
        durations = [r['duration'] for r in successful]
        
        stats = {
            'total_operations': len(results),
            'successful_operations': len(successful),
            'failed_operations': len(failed),
            'success_rate': len(successful) / len(results) * 100,
            'total_time': total_time,
            'operations_per_second': len(results) / total_time,
            'avg_duration': mean(durations) if durations else 0,
            'min_duration': min(durations) if durations else 0,
            'max_duration': max(durations) if durations else 0,
            'stdev_duration': stdev(durations) if len(durations) > 1 else 0,
            'threads_used': num_threads,
            'operations_per_thread': operations_per_thread
        }
        
        return stats


def print_pool_status():
    """Pool durumunu yazdırır."""
    try:
        pool_info = get_pool_info()
        print("\n[POOL STATUS]")
        print(f"  Pool Enabled: {pool_info.get('pool_enabled', 'Unknown')}")
        print(f"  Pool Initialized: {pool_info.get('pool_initialized', 'Unknown')}")
        
        stats = pool_info.get('stats')
        if stats:
            print(f"  Active Connections: {stats.get('current_active', 0)}")
            print(f"  Idle Connections: {stats.get('current_idle', 0)}")
            print(f"  Total Created: {stats.get('total_created', 0)}")
            print(f"  Total Borrowed: {stats.get('total_borrowed', 0)}")
            print(f"  Total Returned: {stats.get('total_returned', 0)}")
            print(f"  Max Connections: {stats.get('max_connections', 0)}")
            print(f"  Min Connections: {stats.get('min_connections', 0)}")
        
    except Exception as e:
        print(f"[ERROR] Pool status error: {e}")


def print_test_results(stats: dict, test_name: str):
    """Test sonuçlarını yazdırır."""
    print(f"\n[TEST RESULTS] {test_name}")
    print("="*50)
    print(f"Total Operations: {stats['total_operations']}")
    print(f"Successful: {stats['successful_operations']}")
    print(f"Failed: {stats['failed_operations']}")
    print(f"Success Rate: {stats['success_rate']:.1f}%")
    print(f"Total Time: {stats['total_time']:.2f} seconds")
    print(f"Operations/Second: {stats['operations_per_second']:.1f}")
    print(f"Average Duration: {stats['avg_duration']*1000:.1f} ms")
    print(f"Min Duration: {stats['min_duration']*1000:.1f} ms")
    print(f"Max Duration: {stats['max_duration']*1000:.1f} ms")
    print(f"StdDev Duration: {stats['stdev_duration']*1000:.1f} ms")
    print(f"Threads: {stats['threads_used']}")
    print(f"Operations/Thread: {stats['operations_per_thread']}")


def main():
    parser = argparse.ArgumentParser(description="Connection Pool Performance Test")
    parser.add_argument("--no-pool", action="store_true", 
                       help="Disable connection pool for comparison")
    parser.add_argument("--threads", type=int, default=10,
                       help="Number of concurrent threads (default: 10)")
    parser.add_argument("--operations", type=int, default=50,
                       help="Operations per thread (default: 50)")
    parser.add_argument("--warmup", type=int, default=5,
                       help="Warmup operations (default: 5)")
    
    args = parser.parse_args()
    
    # Environment setup - MUST be before any imports!
    if args.no_pool:
        os.environ["DB_USE_POOL"] = "false"
        # Force reload of logo module to pick up new env var
        import importlib
        import app.dao.logo
        importlib.reload(app.dao.logo)
        print("[WARNING] Connection pool DISABLED for this test")
    else:
        os.environ["DB_USE_POOL"] = "true"
        print("[INFO] Connection pool ENABLED for this test")
    
    print("[CONNECTION POOL PERFORMANCE TEST]")
    print("="*50)
    
    # Pool status
    print_pool_status()
    
    # Warmup
    print(f"\n[WARMUP] Starting with {args.warmup} operations...")
    tester = ConnectionPoolTester()
    warmup_stats = tester.run_concurrent_test(1, args.warmup)
    print(f"Warmup completed in {warmup_stats['total_time']:.2f}s")
    
    # Main test
    test_name = "WITHOUT Pool" if args.no_pool else "WITH Pool"
    tester = ConnectionPoolTester()
    stats = tester.run_concurrent_test(args.threads, args.operations)
    
    print_test_results(stats, test_name)
    print_pool_status()
    
    # Error summary
    if tester.errors:
        print(f"\n[ERRORS] Total: {len(tester.errors)}")
        for error in tester.errors[:5]:  # Show first 5 errors
            print(f"  Thread {error['thread_id']}: {error['error']}")
        if len(tester.errors) > 5:
            print(f"  ... and {len(tester.errors)-5} more errors")
    
    # Recommendations
    print(f"\n[RECOMMENDATIONS]")
    if stats['success_rate'] < 95:
        print("  - Success rate is low, check database connection stability")
    if stats['avg_duration'] > 0.1:  # 100ms
        print("  - Average query time is high, consider database optimization")
    if args.no_pool:
        print("  - Run with pool enabled to compare performance")
    else:
        print("  - Run with --no-pool to compare baseline performance")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Test stopped by user")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()