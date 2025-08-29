#!/usr/bin/env python3
"""
Connection Pool Comparison Test
================================
Pool'lu ve pool'suz performans karşılaştırması yapar.

Kullanım:
    python test_pool_comparison.py
"""
import os
import sys
import time
import threading
import concurrent.futures
from statistics import mean, stdev
from pathlib import Path

# IMPORTANT: Set environment BEFORE imports!
USE_POOL = "--no-pool" not in sys.argv

if not USE_POOL:
    os.environ["DB_USE_POOL"] = "false"
    print("[INFO] Running WITHOUT connection pool")
else:
    os.environ["DB_USE_POOL"] = "true"
    print("[INFO] Running WITH connection pool")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Now import after env is set
from app.dao.logo import get_conn, get_pool_info


def single_db_operation(operation_id: int) -> dict:
    """Tek bir veritabanı işlemi."""
    start_time = time.time()
    
    try:
        with get_conn() as conn:
            # Simple query
            cursor = conn.execute("SELECT @@VERSION, GETDATE(), @@SPID")
            result = cursor.fetchone()
            
            # Another query
            cursor = conn.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES")
            table_count = cursor.fetchone()[0]
            
            duration = time.time() - start_time
            
            return {
                'success': True,
                'duration': duration,
                'connection_id': result[2] if result else None
            }
            
    except Exception as e:
        return {
            'success': False,
            'duration': time.time() - start_time,
            'error': str(e)
        }


def run_concurrent_test(num_threads: int, operations_per_thread: int):
    """Concurrent test çalıştırır."""
    print(f"\n[TESTING] {num_threads} threads x {operations_per_thread} operations each")
    print(f"Total operations: {num_threads * operations_per_thread}")
    
    start_time = time.time()
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        # Submit all tasks
        futures = []
        for i in range(num_threads * operations_per_thread):
            future = executor.submit(single_db_operation, i)
            futures.append(future)
        
        # Collect results with progress
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            try:
                result = future.result(timeout=30)
                results.append(result)
                
                # Progress indicator
                if i % 100 == 0:
                    print(f"  Progress: {i}/{len(futures)}")
                    
            except Exception as e:
                results.append({
                    'success': False,
                    'duration': 0,
                    'error': str(e)
                })
    
    total_time = time.time() - start_time
    
    # Calculate statistics
    successful = [r for r in results if r.get('success', False)]
    failed = [r for r in results if not r.get('success', False)]
    durations = [r['duration'] for r in successful]
    
    return {
        'total_operations': len(results),
        'successful': len(successful),
        'failed': len(failed),
        'success_rate': len(successful) / len(results) * 100 if results else 0,
        'total_time': total_time,
        'ops_per_second': len(results) / total_time if total_time > 0 else 0,
        'avg_duration_ms': mean(durations) * 1000 if durations else 0,
        'min_duration_ms': min(durations) * 1000 if durations else 0,
        'max_duration_ms': max(durations) * 1000 if durations else 0,
        'stdev_duration_ms': stdev(durations) * 1000 if len(durations) > 1 else 0
    }


def print_results(stats: dict, title: str):
    """Sonuçları formatla ve yazdır."""
    print(f"\n{'='*60}")
    print(f"{title:^60}")
    print('='*60)
    print(f"Total Operations:    {stats['total_operations']:>10}")
    print(f"Successful:          {stats['successful']:>10}")
    print(f"Failed:              {stats['failed']:>10}")
    print(f"Success Rate:        {stats['success_rate']:>9.1f}%")
    print(f"Total Time:          {stats['total_time']:>9.2f}s")
    print(f"Operations/Second:   {stats['ops_per_second']:>9.1f}")
    print(f"Avg Response Time:   {stats['avg_duration_ms']:>9.1f}ms")
    print(f"Min Response Time:   {stats['min_duration_ms']:>9.1f}ms")
    print(f"Max Response Time:   {stats['max_duration_ms']:>9.1f}ms")
    print(f"StdDev:              {stats['stdev_duration_ms']:>9.1f}ms")
    print('='*60)


def main():
    print("\n" + "="*60)
    print("CONNECTION POOL PERFORMANCE COMPARISON TEST")
    print("="*60)
    
    # Check pool status
    pool_info = get_pool_info()
    print(f"\nPool Configuration:")
    print(f"  Enabled: {pool_info.get('pool_enabled', 'Unknown')}")
    print(f"  Initialized: {pool_info.get('pool_initialized', 'Unknown')}")
    
    if pool_info.get('stats'):
        stats = pool_info['stats']
        print(f"  Max Connections: {stats.get('max_connections', 'N/A')}")
        print(f"  Min Connections: {stats.get('min_connections', 'N/A')}")
    
    # Test parameters
    num_threads = 10
    ops_per_thread = 20
    
    # Warmup
    print(f"\n[WARMUP] Running 5 operations...")
    warmup_stats = run_concurrent_test(1, 5)
    print(f"Warmup completed in {warmup_stats['total_time']:.2f}s")
    
    # Main test
    print(f"\n[MAIN TEST] Starting...")
    stats = run_concurrent_test(num_threads, ops_per_thread)
    
    # Print results
    mode = "WITH Connection Pool" if USE_POOL else "WITHOUT Connection Pool"
    print_results(stats, f"RESULTS - {mode}")
    
    # Final pool status
    if USE_POOL:
        pool_info = get_pool_info()
        if pool_info.get('stats'):
            stats = pool_info['stats']
            print(f"\nFinal Pool Statistics:")
            print(f"  Total Created: {stats.get('total_created', 0)}")
            print(f"  Total Borrowed: {stats.get('total_borrowed', 0)}")
            print(f"  Total Returned: {stats.get('total_returned', 0)}")
            print(f"  Current Active: {stats.get('current_active', 0)}")
            print(f"  Current Idle: {stats.get('current_idle', 0)}")
    
    # Recommendations
    print(f"\n[RECOMMENDATIONS]")
    if USE_POOL:
        print("  - Run 'python test_pool_comparison.py --no-pool' to compare")
    else:
        print("  - Run 'python test_pool_comparison.py' to test with pool")
    
    if 'avg_duration_ms' in stats and stats['avg_duration_ms'] > 100:
        print("  - Response time is high, check database performance")
    
    if 'success_rate' in stats and stats['success_rate'] < 100:
        print(f"  - {stats.get('failed', 0)} operations failed, check error logs")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Test stopped by user")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()