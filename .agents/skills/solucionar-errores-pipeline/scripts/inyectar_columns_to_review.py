#!/usr/bin/env python3
"""Script para Inyectar columns_to_review en Archivos SQLite Históricos.

Evita falsos positivos de 'Structure Change' causados por archivos SQLite
que no contenían la tabla de referencia 'columns_to_review'.
"""

import os
import sqlite3
import sys
import pandas as pd


def inyectar_columns(sqlite_path: str, columns: list = None):
    if not os.path.exists(sqlite_path):
        print(f"❌ El archivo no existe: {sqlite_path}")
        return False

    with sqlite3.connect(sqlite_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [
            r[0]
            for r in cur.fetchall()
            if r[0] not in ("columns_to_review", "replaces_table")
        ]

        if not tables:
            print(f"⚠️ No se encontraron tablas de datos en {sqlite_path}")
            return False

        target_table = tables[0]

        if not columns:
            df = pd.read_sql_query(f"SELECT * FROM {target_table} LIMIT 1", conn)
            # Detectar automáticamente columnas jerárquicas nv1..nvN
            columns = [col for col in df.columns if col.startswith("nv")]
            if not columns:
                print(
                    f"⚠️ No se detectaron columnas 'nv' en {target_table}. Columnas encontradas: {df.columns.tolist()}"
                )
                return False

        col_df = pd.DataFrame({"column": columns})
        col_df.to_sql(
            "columns_to_review", conn, if_exists="replace", index=False
        )
        print(
            f"✅ Tabla 'columns_to_review' inyectada exitosamente en {sqlite_path} con columnas: {columns}"
        )
        return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Uso: python inyectar_columns_to_review.py <ruta_sqlite> [col1,col2,...]"
        )
        sys.exit(1)

    path = sys.argv[1]
    cols = sys.argv[2].split(",") if len(sys.argv) > 2 else None
    inyectar_columns(path, cols)
