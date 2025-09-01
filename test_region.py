"""Test script to check region data in orders"""
from app.dao.logo import fetch_draft_orders, fetch_picking_orders, get_conn, _t

def test_region_data():
    print("Testing region data in orders...")
    print("=" * 60)
    
    # Test draft orders (STATUS=1)
    print("\n1. DRAFT ORDERS (STATUS=1):")
    draft_orders = fetch_draft_orders(limit=5)
    for order in draft_orders:
        print(f"\nOrder: {order.get('order_no')}")
        print(f"  GENEXP1: {order.get('genexp1', 'NULL')}")
        print(f"  GENEXP2: {order.get('genexp2', 'NULL')}")
        print(f"  GENEXP3: {order.get('genexp3', 'NULL')}")
        print(f"  GENEXP4: {order.get('genexp4', 'NULL')}")
        region = f"{order.get('genexp2', '')} - {order.get('genexp3', '')}".strip(" -")
        print(f"  Region String: '{region}'")
    
    # Test picking orders (STATUS=2)
    print("\n2. PICKING ORDERS (STATUS=2):")
    picking_orders = fetch_picking_orders(limit=5)
    for order in picking_orders:
        print(f"\nOrder: {order.get('order_no')}")
        print(f"  GENEXP1: {order.get('genexp1', 'NULL')}")
        print(f"  GENEXP2: {order.get('genexp2', 'NULL')}")
        print(f"  GENEXP3: {order.get('genexp3', 'NULL')}")
        print(f"  GENEXP4: {order.get('genexp4', 'NULL')}")
        region = f"{order.get('genexp2', '')} - {order.get('genexp3', '')}".strip(" -")
        print(f"  Region String: '{region}'")
    
    # Direct SQL query to check raw data
    print("\n3. RAW DATA CHECK:")
    sql = f"""
    SELECT TOP 5
        FICHENO,
        GENEXP1,
        GENEXP2,
        GENEXP3,
        GENEXP4,
        STATUS
    FROM {_t('ORFICHE')}
    WHERE CANCELLED = 0
    ORDER BY LOGICALREF DESC
    """
    
    with get_conn() as cn:
        cur = cn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        
        for row in rows:
            print(f"\nOrder: {row[0]} (STATUS={row[5]})")
            print(f"  GENEXP1: {row[1]}")
            print(f"  GENEXP2: {row[2]}")
            print(f"  GENEXP3: {row[3]}")
            print(f"  GENEXP4: {row[4]}")

if __name__ == "__main__":
    test_region_data()