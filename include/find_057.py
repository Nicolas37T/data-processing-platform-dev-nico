import sqlalchemy
import pandas as pd

engine = sqlalchemy.create_engine('postgresql+psycopg2://postgres:datax@10.0.0.16:5434/platform_db')
with engine.connect() as conn:
    query = sqlalchemy.text("""
        SELECT r.id_report, r.code as report_code, r.name, r."isActive", f.code as file_code, f.id_file
        FROM report r 
        LEFT JOIN file f ON r.id_file = f.id_file 
        WHERE f.code ILIKE '%57%' OR r.code ILIKE '%57%';
    """)
    rows = conn.execute(query).fetchall()
    print("Reports found:")
    for r in rows:
        print(r)

    # Check for downloads of D_BO_000000057 or D_BO_00000057...
    query_d = sqlalchemy.text("""
        SELECT d.id_download, d.id_file, d.downloaded_to, d.path, f.code 
        FROM download d 
        JOIN file f ON d.id_file = f.id_file 
        WHERE f.code ILIKE '%57%'
        ORDER BY d.id_download DESC LIMIT 10;
    """)
    rows_d = conn.execute(query_d).fetchall()
    print("\nDownloads found:")
    for rd in rows_d:
        print(rd)
