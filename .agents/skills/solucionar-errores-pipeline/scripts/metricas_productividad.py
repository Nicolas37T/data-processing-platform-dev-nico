import argparse
import paramiko

def consultar_metricas_despliegue(fecha_desde=None, fecha_hasta=None, dias=None):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('10.0.0.16', username='datax-pds', password='.datax-pds*/$')

    filtro_sql = "HAVING MIN(c.conversion_date) = CURRENT_DATE"
    label = "HOY"
    if dias:
        filtro_sql = f"HAVING MIN(c.conversion_date) >= CURRENT_DATE - INTERVAL '{dias} days'"
        label = f"ÚLTIMOS {dias} DÍAS"
    elif fecha_desde and fecha_hasta:
        filtro_sql = f"HAVING MIN(c.conversion_date) >= '{fecha_desde}' AND MIN(c.conversion_date) <= '{fecha_hasta}'"
        label = f"ENTRE {fecha_desde} Y {fecha_hasta}"
    elif fecha_desde:
        filtro_sql = f"HAVING MIN(c.conversion_date) >= '{fecha_desde}'"
        label = f"DESDE {fecha_desde}"

    py_script = f"""
from airflow.providers.postgres.hooks.postgres import PostgresHook
hook = PostgresHook('platform_db')
conn = hook.get_conn()
cur = conn.cursor()

cur.execute('''
    SELECT 
        r.code, 
        r.name, 
        MIN(c.conversion_date) as primera_conversion,
        (SELECT MIN(m.migration_date) FROM migration m WHERE m.id_report = r.id_report) as primera_migracion,
        (SELECT MIN(d.download_date) FROM download d WHERE d.id_file = r.id_file) as primera_descarga
    FROM conversion c
    JOIN report r ON c.id_report = r.id_report
    GROUP BY r.code, r.name, r.id_report, r.id_file
    {filtro_sql}
    ORDER BY primera_conversion DESC, r.code ASC
''')
filas = cur.fetchall()

print("=" * 105)
print(f"  [+] ROBOTS NUEVOS DESPLEGADOS Y ESTRENADOS ({label})")
print("=" * 105)
print(f"Total de robots nuevos estrenados: {{len(filas)}}")
print("-" * 105)
header = "%-18s | %-12s | %-12s | %-12s | %-40s" % ("CÓDIGO", "DESCARGA", "CONVERSIÓN", "MIGRACIÓN", "NOMBRE REPORTE")
print(header)
print("-" * 105)

for r in filas:
    c_code = r[0]
    c_name = (r[1][:37] + '...') if r[1] and len(r[1]) > 40 else (r[1] or '')
    d_date = str(r[4]) if r[4] else 'Pendiente'
    c_date = str(r[2]) if r[2] else 'Pendiente'
    m_date = str(r[3]) if r[3] else 'Pendiente'
    print("%-18s | %-12s | %-12s | %-12s | %-40s" % (c_code, d_date, c_date, m_date, c_name))
print("-" * 105)
"""

    import base64
    b64_script = base64.b64encode(py_script.encode('utf-8')).decode('ascii')
    cmd = f'docker exec data-processing-platform-dev-airflow-worker-1 python -c "import base64; exec(base64.b64decode(\'{b64_script}\').decode(\'utf-8\'))"'

    stdin, stdout, stderr = ssh.exec_command(cmd)
    salida = stdout.read().decode('utf-8', errors='replace')
    errores = stderr.read().decode('utf-8', errors='replace')
    ssh.close()

    if salida.strip():
        print(salida.encode('ascii', errors='replace').decode('ascii'))
    if errores.strip():
        print("STDERR:", errores)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Mide los robots nuevos desplegados por primera vez en Airflow.")
    parser.add_argument('--dias', type=int, help="Últimos N días.")
    parser.add_argument('--desde', type=str, help="Fecha inicio (YYYY-MM-DD).")
    parser.add_argument('--hasta', type=str, help="Fecha fin (YYYY-MM-DD).")
    args = parser.parse_args()

    consultar_metricas_despliegue(fecha_desde=args.desde, fecha_hasta=args.hasta, dias=args.dias)
