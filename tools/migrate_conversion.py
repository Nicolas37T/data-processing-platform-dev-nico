#!/usr/bin/env python3
"""Script de automatización para migrar robots de conversión (V1 -> V2).

Basado en el manual 'Creacion DAG Covnersion.md'.
Flujo completo:
1. Localiza el código del robot y archivos de muestra en el repositorio antiguo.
2. Consulta metadatos en 'platform_db' (tabla 'report').
3. Refactoriza el código al estándar V2 (Conversion_Base, imports, manejo de excepciones).
4. Crea la estructura en 'models/conversion/<PARENT_CODE>/'.
5. Copia archivos de muestra (.pdf, .xlsx, .sqlite).
6. Configura la tabla 'columns_to_review' en el archivo SQLite según Paso 8.
7. Ejecuta el test unitario 'test_conversion.py'.
8. Genera automáticamente el wrapper del DAG en 'dags/conversion/<PARENT_CODE>.py'.
"""

import argparse
import importlib.util
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import create_engine

# Directorio raíz del proyecto
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    from include.console import error_print, info_print, success_print
except ImportError:
    def info_print(msg: str):
        print(f"[INFO] {msg}")

    def error_print(msg: str):
        print(f"[ERROR] {msg}")

    def success_print(msg: str):
        print(f"[SUCCESS] {msg}")

# Ruta por defecto al repositorio antiguo
DEFAULT_OLD_REPO_PATH = os.getenv("OLD_REPO_PATH", r"E:\DATAX\data-processing-platform-nico")


def get_db_engine():
    """Crea la conexión a platform_db usando variables de entorno o valores por defecto."""
    host = os.getenv("BUSINESS_DB_HOST", "10.0.0.16")
    port = os.getenv("BUSINESS_DB_PORT", "5434")
    user = os.getenv("BUSINESS_DB_USER", "postgres")
    password = os.getenv("BUSINESS_DB_PASSWORD", "datax")
    database = os.getenv("BUSINESS_DB_DATABASE", "platform_db")
    return create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}")


def resolve_conversion_codes(code_input: str) -> Tuple[str, Optional[str]]:
    """Determina el parent_code (C_BO_...) y report_code (D_BO_..._XX) a partir de la entrada."""
    code = code_input.strip()
    if code.startswith("C_"):
        # Se ingresó el código padre, ej. C_BO_000000481
        parent_code = code
        report_code = None
    elif code.startswith("D_"):
        # Se ingresó el código de reporte, ej. D_BO_000000481_01 o D_BO_000000481
        parts = code.split("_")
        if len(parts) >= 4:
            # Tiene sufijo, ej. D_BO_000000481_01
            parent_code = f"C_{parts[1]}_{parts[2]}"
            report_code = code
        else:
            # No tiene sufijo, ej. D_BO_000000481
            parent_code = f"C_{parts[1]}_{parts[2]}"
            report_code = None
    else:
        parent_code = code
        report_code = None

    return parent_code, report_code


def locate_conversion_sources(
    parent_code: str,
    report_code: Optional[str] = None,
    old_repo_path: str = DEFAULT_OLD_REPO_PATH,
) -> Dict[str, any]:
    """Localiza los scripts de conversión y archivos de muestra en el repositorio antiguo."""
    result = {
        "folder": None,
        "scripts": [],      # List[Tuple[str, str]] -> (report_code, full_path)
        "sample_files": [], # List[str] -> rutas a .pdf, .xlsx, etc.
        "sqlite_files": [], # List[str] -> rutas a .sqlite
    }

    if not os.path.isdir(old_repo_path):
        return result

    # La carpeta en models/conversion suele llamarse C_BO_XXXX o D_BO_XXXX
    candidate_folders = [
        os.path.join(old_repo_path, "models", "conversion", parent_code),
        os.path.join(old_repo_path, "models", "conversion", parent_code.replace("C_", "D_")),
    ]

    target_folder = None
    for folder in candidate_folders:
        if os.path.isdir(folder):
            target_folder = folder
            break

    if not target_folder:
        return result

    result["folder"] = target_folder

    for fname in os.listdir(target_folder):
        fpath = os.path.join(target_folder, fname)
        if not os.path.isfile(fpath):
            continue

        lower = fname.lower()
        if lower.endswith(".py") and not lower.startswith("__"):
            # Buscar código de reporte en el nombre del archivo (ej. D_BO_000000481_01)
            code_match = re.search(r"(D_[A-Z]{2}_\d{9}_\d{2})", fname)
            detected_code = code_match.group(1) if code_match else os.path.splitext(fname)[0]
            if report_code and detected_code != report_code:
                continue
            result["scripts"].append((detected_code, fpath))
        elif lower.endswith((".pdf", ".xlsx", ".xls", ".csv", ".zip")):
            result["sample_files"].append(fpath)
        elif lower.endswith(".sqlite"):
            result["sqlite_files"].append(fpath)

    return result


def fetch_report_metadata(report_code: str, engine) -> Optional[Dict]:
    """Consulta la configuración del reporte en la tabla 'report' de platform_db."""
    query = f"""
        SELECT id_report, code, name, page_number, decimal_separator, 
               key_words, path, storage_table, replacement_table,
               converted_report_path, is_active
        FROM report 
        WHERE code = '{report_code}';
    """
    try:
        df = pd.read_sql_query(query, con=engine)
        if df.empty:
            return None
        return df.iloc[0].to_dict()
    except Exception as exc:
        error_print(f"Error al consultar tabla 'report' para {report_code}: {exc}")
        return None


def refactor_conversion_code(raw_code: str, report_code: str) -> str:
    """Aplica las reglas de estandarización V2 del Paso 4 de 'Creacion DAG Covnersion.md'."""
    code_content = raw_code

    # 1. Eliminar sys.path.append viejos o rutas relativas
    code_content = re.sub(r"sys\.path\.append\([^)]*\)\s*", "", code_content)

    # 2. Corregir imports de herramientas hacia los paths oficiales de la Plataforma V2
    code_content = re.sub(r"\bfrom\s+(?:models\.)?(?:conversion\.)?tools\.conversion_tools\b", "from models.conversion.tools.conversion_tools", code_content)
    code_content = re.sub(r"\bfrom\s+conversion_tools\b", "from models.conversion.tools.conversion_tools", code_content)
    code_content = re.sub(r"\bimport\s+conversion_tools\b", "import models.conversion.tools.conversion_tools as conversion_tools", code_content)

    code_content = re.sub(r"\bfrom\s+(?:models\.)?(?:download\.)?tools\.download_tools\b", "from models.download.tools.download_tools", code_content)
    code_content = re.sub(r"\bfrom\s+download_tools\b", "from models.download.tools.download_tools", code_content)
    code_content = re.sub(r"\bimport\s+download_tools\b", "import models.download.tools.download_tools as download_tools", code_content)

    # 3. Asegurar import requerido de Conversion_Base
    if "from models.conversion.Conversion_Base import Conversion_Base" not in code_content:
        code_content = (
            "from models.conversion.Conversion_Base import Conversion_Base\n"
            + code_content
        )

    # 4. Renombrar clase principal a <REPORT_CODE>(Conversion_Base)
    # Soporta class Robot:, class Robot():, class Robot(Conversion_Base):, class Executor_...:, etc.
    class_pattern = r"class\s+([A-Za-z0-9_]+)(?:\s*\([^)]*\))?\s*:"
    matches = list(re.finditer(class_pattern, code_content))
    for m in matches:
        cls_name = m.group(1)
        if cls_name != report_code:
            full_match = m.group(0)
            code_content = code_content.replace(full_match, f"class {report_code}(Conversion_Base):", 1)
            break

    # 5. Asegurar traceback.print_exc() en bloques except si falta
    lines = code_content.splitlines()
    new_lines = []
    for i, line in enumerate(lines):
        new_lines.append(line)
        if re.search(r"^\s*except(\s+.*)?:", line):
            next_block = "\n".join(lines[i + 1 : i + 4])
            if "print_exc" not in next_block:
                indent = re.match(r"^(\s*)", line).group(1) + "    "
                new_lines.append(f"{indent}import traceback; traceback.print_exc()")
    code_content = "\n".join(new_lines)

    # 6. Agregar alias al pie de compatibilidad
    alias_footer = f"\n\nExecutor_{report_code} = {report_code}\nRobot = {report_code}\n"
    if f"Executor_{report_code} = {report_code}" not in code_content:
        code_content += alias_footer

    return code_content


def setup_columns_to_review(sqlite_path: str, report_code: str) -> bool:
    """Configura la tabla 'columns_to_review' según las reglas críticas del Paso 8:

    - Nombre tabla: 'columns_to_review'
    - Columna: 'column'
    - Incluye solo fecha y niveles (nv1, nv2, ...). Excluye 'valor' y metadatos.
    """
    if not os.path.isfile(sqlite_path):
        return False

    try:
        conn = sqlite3.connect(sqlite_path)
        cur = conn.cursor()

        # Obtener columnas de la tabla del reporte
        cur.execute(f"PRAGMA table_info({report_code});")
        cols_info = cur.fetchall()
        if not cols_info:
            conn.close()
            return False

        all_cols = [c[1] for c in cols_info]

        # Filtrar columnas a revisar: solo fecha y niveles/categorías
        # Prohibido: valor, file, tituloX, id_*, etc.
        review_cols = []
        for col in all_cols:
            col_clean = col.strip().lower()
            if col_clean in ("valor", "file") or col_clean.startswith(("titulo", "id_")):
                continue
            if col_clean == "fecha" or col_clean.startswith("nv") or "nivel" in col_clean or "categoria" in col_clean:
                review_cols.append(col)
            elif col_clean not in review_cols:
                # Columnas adicionales de estructura no numéricas
                review_cols.append(col)

        cur.execute("DROP TABLE IF EXISTS columns_to_review;")
        cur.execute("CREATE TABLE columns_to_review (column TEXT);")
        cur.executemany(
            "INSERT INTO columns_to_review (column) VALUES (?);",
            [(col,) for col in review_cols],
        )
        conn.commit()

        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cur.fetchall()]
        conn.close()

        success_print(
            f"SQLite configurado con éxito ({sqlite_path}). Tablas: {tables}, Columnas en revisión: {review_cols}"
        )
        return True
    except Exception as exc:
        error_print(f"Error al configurar columns_to_review en {sqlite_path}: {exc}")
        return False


def run_conversion_test(report_code: str, sample_file_path: str, skip_text_match: bool = False, base_dir: str = ROOT_DIR) -> bool:
    """Ejecuta el test unitario 'models/conversion/tests/test_conversion.py'."""
    test_path = os.path.join(base_dir, "models", "conversion", "tests", "test_conversion.py")
    mode_str = "extracción pura (sin text_match)" if skip_text_match else "completo (con text_match)"
    info_print(f"🧪 Ejecutando prueba unitaria de conversión ({mode_str}) para {report_code} con muestra: {sample_file_path}...")

    env = os.environ.copy()
    env["REPORT_CODE"] = report_code
    env["FILE_PATH"] = sample_file_path
    env["SKIP_TEXT_MATCH"] = "1" if skip_text_match else "0"

    cmd = [sys.executable, "-m", "unittest", test_path]
    result = subprocess.run(cmd, cwd=base_dir, env=env, capture_output=True, text=True)

    if result.returncode == 0:
        success_print(f"Test unitario de conversión APROBADO (OK) para {report_code}.")
        return True
    else:
        error_print(f"Test unitario de conversión FALLÓ para {report_code}.")
        if result.stderr:
            print(result.stderr)
        if result.stdout:
            print(result.stdout)
        return False


def generate_conversion_dag(parent_code: str, base_dir: str = ROOT_DIR) -> bool:
    """Genera el wrapper del DAG en dags/conversion/<PARENT_CODE>.py usando include/main-generate.py."""
    try:
        generator_file = os.path.join(base_dir, "include", "main-generate.py")
        if not os.path.isfile(generator_file):
            error_print(f"Generador no encontrado: {generator_file}")
            return False

        spec = importlib.util.spec_from_file_location("main_generate", generator_file)
        gen_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen_module)
        RobotCodeHandler = getattr(gen_module, "RobotCodeHandler")

        handler = RobotCodeHandler(process="conversion")
        handler.process_codes([parent_code])
        if not handler.robots:
            error_print(f"No se pudo cargar la configuración de DAG para {parent_code} desde BD.")
            return False

        handler.create_dags()
        dag_path = os.path.join(base_dir, "dags", "conversion", f"{parent_code}.py")
        if os.path.isfile(dag_path):
            success_print(f"DAG de conversión generado exitosamente en: {dag_path}")
            return True
        else:
            error_print(f"El archivo DAG no se encontró tras la generación: {dag_path}")
            return False
    except Exception as exc:
        error_print(f"Error al generar DAG de conversión para {parent_code}: {exc}")
        return False


def migrate_conversion_family(
    parent_code: str,
    report_code_filter: Optional[str] = None,
    custom_source: Optional[str] = None,
    old_repo: str = DEFAULT_OLD_REPO_PATH,
    sample_file: Optional[str] = None,
    skip_test: bool = False,
    skip_dag: bool = False,
    dry_run: bool = False,
    base_dir: str = ROOT_DIR,
) -> bool:
    """Ejecuta la migración completa de un grupo de conversión C_BO_XXXX."""
    info_print(f"=== Procesando migración de Conversión: {parent_code} ===")

    engine = get_db_engine()

    # 1. Localizar archivos en repo antiguo
    if custom_source:
        if os.path.isfile(custom_source):
            code_match = re.search(r"(D_[A-Z]{2}_\d{9}_\d{2})", os.path.basename(custom_source))
            rep_code = code_match.group(1) if code_match else (report_code_filter or "D_BO_UNKNOWN")
            sources = {"folder": os.path.dirname(custom_source), "scripts": [(rep_code, custom_source)], "sample_files": [], "sqlite_files": []}
        else:
            sources = locate_conversion_sources(parent_code, report_code_filter, old_repo_path=custom_source)
    else:
        info_print(f"Buscando automáticamente {parent_code} en {old_repo}...")
        sources = locate_conversion_sources(parent_code, report_code_filter, old_repo_path=old_repo)

    if not sources["scripts"]:
        error_print(f"No se encontraron scripts .py para {parent_code} en el repositorio antiguo.")
        return False

    info_print(f"Scripts encontrados ({len(sources['scripts'])}): {[s[0] for s in sources['scripts']]}")

    # Carpeta destino en V2: models/conversion/<PARENT_CODE>/
    dest_dir = os.path.join(base_dir, "models", "conversion", parent_code)
    if not dry_run:
        os.makedirs(dest_dir, exist_ok=True)
        # __init__.py
        init_path = os.path.join(dest_dir, "__init__.py")
        if not os.path.isfile(init_path):
            with open(init_path, "w", encoding="utf-8") as f:
                f.write(f'"""Module initialization for {parent_code}."""\n')

    # Copiar archivos de muestra (.pdf, .xlsx) al destino para pruebas
    copied_sample = sample_file
    if not copied_sample and sources["sample_files"]:
        primary_sample = sources["sample_files"][0]
        if not dry_run:
            dest_sample = os.path.join(dest_dir, os.path.basename(primary_sample))
            shutil.copyfile(primary_sample, dest_sample)
            copied_sample = dest_sample
            info_print(f"Archivo de muestra copiado para pruebas: {dest_sample}")
        else:
            copied_sample = primary_sample

    # Copiar SQLite de referencia si existe en el repo viejo
    if sources["sqlite_files"] and not dry_run:
        for sql_src in sources["sqlite_files"]:
            dest_sql = os.path.join(dest_dir, os.path.basename(sql_src))
            shutil.copyfile(sql_src, dest_sql)
            info_print(f"SQLite de referencia copiado: {dest_sql}")

    all_ok = True

    # 2. Refactorizar y guardar cada script de reporte (D_BO_..._XX.py)
    for rep_code, script_path in sources["scripts"]:
        info_print(f"Refactorizando robot: {rep_code} desde {script_path}")

        meta = fetch_report_metadata(rep_code, engine)
        if meta:
            info_print(f"Metadatos encontrados en 'report': Nombre='{meta.get('name')}', Tabla='{meta.get('storage_table')}'")
        else:
            info_print(f"Aviso: {rep_code} aún no tiene registro en tabla 'report'. Se continuará con el refactor.")

        with open(script_path, "r", encoding="utf-8", errors="ignore") as f:
            raw_code = f.read()

        refactored = refactor_conversion_code(raw_code, rep_code)

        if dry_run:
            info_print(f"[DRY-RUN] Script {rep_code} refactorizado en memoria.")
            continue

        dest_file = os.path.join(dest_dir, f"{rep_code}.py")
        with open(dest_file, "w", encoding="utf-8") as f:
            f.write(refactored)
        success_print(f"Robot guardado en: {dest_file}")

        # Configurar tabla columns_to_review en el SQLite si existe
        sqlite_local = os.path.join(dest_dir, f"{rep_code}.sqlite")
        if os.path.isfile(sqlite_local):
            setup_columns_to_review(sqlite_local, rep_code)

        # 3. Test Unitario
        if not skip_test:
            if copied_sample and os.path.isfile(copied_sample):
                test_ok = run_conversion_test(rep_code, copied_sample, base_dir)
                if test_ok:
                    # Tras el test se genera o actualiza el SQLite; configurar Paso 8
                    if os.path.isfile(sqlite_local):
                        setup_columns_to_review(sqlite_local, rep_code)
                else:
                    all_ok = False
            else:
                info_print(f"Aviso: No se encontró archivo de muestra (.pdf/.xlsx) para probar {rep_code}. Omite con --skip-test.")
                all_ok = False
        else:
            info_print(f"Test unitario omitido para {rep_code} (--skip-test).")

    if dry_run:
        info_print(f"[DRY-RUN] Simulación completada para {parent_code}.\n")
        return True

    # 4. Generación del DAG en Airflow
    if not skip_dag and all_ok:
        dag_ok = generate_conversion_dag(parent_code, base_dir)
        if not dag_ok:
            return False
    elif skip_dag:
        info_print(f"Paso de generación de DAG omitido (--skip-dag).")

    success_print(f"✨ ¡Migración de Conversión completada para {parent_code}! ✨\n")
    return all_ok


def main():
    parser = argparse.ArgumentParser(
        description="Automatizador de Migración de Robots de Conversión V1 -> V2 (Plataforma V2)"
    )
    parser.add_argument(
        "--code",
        type=str,
        help="Código padre (ej. C_BO_000000481) o de reporte (ej. D_BO_000000481_01)",
    )
    parser.add_argument(
        "--source",
        type=str,
        help="Ruta al archivo .py específico o carpeta en el repositorio antiguo",
    )
    parser.add_argument(
        "--old-repo",
        type=str,
        default=DEFAULT_OLD_REPO_PATH,
        help=f"Ruta raíz del repositorio antiguo (por defecto: {DEFAULT_OLD_REPO_PATH})",
    )
    parser.add_argument(
        "--sample-file",
        type=str,
        help="Ruta a un archivo de muestra (.pdf, .xlsx) para ejecutar el test unitario",
    )
    parser.add_argument("--skip-test", action="store_true", help="Omitir la ejecución del test unitario")
    parser.add_argument(
        "--generate-dag",
        action="store_true",
        default=False,
        help="Generar el archivo DAG en dags/conversion (por defecto desactivado)",
    )
    parser.add_argument(
        "--skip-dag",
        action="store_true",
        default=True,
        help="Omitir la generación del archivo DAG (activo por defecto)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simular el proceso sin escribir archivos en disco",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Migrar todas las familias de conversión encontradas en el repositorio antiguo",
    )

    args = parser.parse_args()

    if not args.code and not args.batch:
        parser.print_help()
        print(f"\n[INFO] Repositorio antiguo por defecto: {DEFAULT_OLD_REPO_PATH}")
        print("Ejemplo de uso simple: python tools/migrate_conversion.py --code C_BO_000000481")
        sys.exit(1)

    effective_skip_dag = not args.generate_dag

    if args.code:
        parent_code, report_code = resolve_conversion_codes(args.code)
        ok = migrate_conversion_family(
            parent_code=parent_code,
            report_code_filter=report_code,
            custom_source=args.source,
            old_repo=args.old_repo,
            sample_file=args.sample_file,
            skip_test=args.skip_test,
            skip_dag=effective_skip_dag,
            dry_run=args.dry_run,
        )
        sys.exit(0 if ok else 1)

    elif args.batch:
        conv_root = os.path.join(args.old_repo, "models", "conversion")
        if not os.path.isdir(conv_root):
            error_print(f"Carpeta de conversión no encontrada en {conv_root}")
            sys.exit(1)

        info_print(f"Buscando familias de conversión en: {conv_root}")
        results = []

        for item in sorted(os.listdir(conv_root)):
            item_path = os.path.join(conv_root, item)
            if not os.path.isdir(item_path):
                continue

            match = re.search(r"(C_[A-Z]{2}_\d{9})", item)
            if not match:
                continue

            parent_code = match.group(1)
            ok = migrate_conversion_family(
                parent_code=parent_code,
                old_repo=args.old_repo,
                skip_test=args.skip_test,
                skip_dag=effective_skip_dag,
                dry_run=args.dry_run,
            )
            results.append((parent_code, ok))

        print("\n=== RESUMEN DE MIGRACIÓN POR LOTE (CONVERSIÓN) ===")
        for p, status in results:
            stat_str = "EXITOSO" if status else "FALLIDO"
            print(f"  - {p}: {stat_str}")


if __name__ == "__main__":
    main()
