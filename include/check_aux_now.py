import psycopg2

conn = psycopg2.connect('postgresql://postgres:datax@10.0.0.16:5434/DATA_DB_BO_AUX')
cur = conn.cursor()
cur.execute("SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema IN ('bbv', 'BBV')")
print("Tables in DATA_DB_BO_AUX (BBV schema):")
for r in cur.fetchall():
    print(" ", r)
conn.close()
