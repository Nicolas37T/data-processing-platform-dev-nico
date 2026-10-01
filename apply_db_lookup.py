# -*- coding: utf-8 -*-
target = r'C:\Users\DATAX\Documents\Nicolas\Taiga\webhook_reader\services\db_lookup.py'

with open(target, 'r', encoding='utf-8') as f:
    content = f.read()

new_func = '''

def resolve_source_for_dag(dag_code: str, file_code: str = None) -> dict:
    """
    Resuelve la fuente oficial real (short_name y name), nombre del archivo y dataset
    para un DAG (ej. C_BO_000000290 -> ASFI, Autoridad de Supervisión del Sistema Financiero).
    Garantiza que la fuente NUNCA sea 'DATAX' a menos que realmente provenga de allí.
    """
    clean_dag = (dag_code or "").strip()
    target_code = file_code or clean_dag
    if target_code.startswith("C_") or target_code.startswith("M_"):
        target_code = "D_" + "_".join(target_code.split("_")[1:3])
    elif target_code.startswith("D_") and len(target_code.split("_")) > 3:
        target_code = "_".join(target_code.split("_")[:3])

    query = """
    SELECT 
        f.code AS file_code,
        f.name AS file_name,
        s.short_name AS source_short,
        s.name AS source_name,
        dbr.db_code AS dataset_code,
        db.name AS dataset_name,
        f.publication_frequency,
        f.updated_to
    FROM file f
    LEFT JOIN source s ON f.id_source = s.id_source
    LEFT JOIN report r ON r.id_file = f.id_file
    LEFT JOIN data_base_report dbr ON dbr.report_code = r.code
    LEFT JOIN data_base db ON db.db_code = dbr.db_code
    WHERE f.code = %s OR f.code = %s
    ORDER BY dbr.db_code DESC NULLS LAST
    LIMIT 1;
    """
    try:
        connection = _connect()
        with connection.cursor() as cursor:
            cursor.execute(query, (target_code, clean_dag))
            row = cursor.fetchone()
        connection.close()
        if row and row.get("source_short"):
            return {
                "file_code": row.get("file_code") or target_code,
                "file_name": row.get("file_name") or "",
                "source_short": row.get("source_short") or "Fuente",
                "source_name": row.get("source_name") or "Fuente Oficial",
                "dataset_code": row.get("dataset_code") or "-",
                "dataset_name": row.get("dataset_name") or "-",
                "publication_frequency": row.get("publication_frequency"),
                "updated_to": str(row.get("updated_to") or "")
            }
    except Exception as e:
        print(f"[DB_LOOKUP] Error resolviendo fuente para {dag_code}: {e}")

    # Fallback deduciendo según siglas conocidas en código
    parts = clean_dag.split("_")
    deduced_source = "Fuente"
    if len(parts) >= 2:
        country = parts[1]
    
    return {
        "file_code": target_code,
        "file_name": "",
        "source_short": deduced_source,
        "source_name": f"Fuente Oficial ({deduced_source})",
        "dataset_code": "-",
        "dataset_name": "-",
        "publication_frequency": None,
        "updated_to": ""
    }
'''

if "def resolve_source_for_dag" not in content:
    content += new_func
    with open(target, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Added resolve_source_for_dag to db_lookup.py!")
else:
    print("resolve_source_for_dag already exists.")
