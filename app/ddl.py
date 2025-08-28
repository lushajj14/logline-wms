# app/ddl.py
_DDL_TRIG = """
IF NOT EXISTS (SELECT * FROM sys.objects WHERE name='trg_pkgs_auto_expand')
EXEC('
CREATE TRIGGER trg_pkgs_auto_expand
ON dbo.shipment_loaded
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS(
        SELECT 1 FROM inserted i
        JOIN dbo.shipment_header h ON h.id=i.trip_id
        WHERE i.loaded=1 AND i.pkg_no>h.pkgs_total)
    BEGIN
        UPDATE h SET pkgs_total=i.pkg_no
        FROM dbo.shipment_header h
        JOIN inserted i ON i.trip_id=h.id
        WHERE i.loaded=1 AND i.pkg_no>h.pkgs_total;
    END
END')
"""
from dao import get_conn  # Use absolute import if db.py is in the same directory

def ensure_triggers():
    with get_conn(autocommit=True) as cn:
        cn.execute(_DDL_TRIG)
