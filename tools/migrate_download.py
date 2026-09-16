#!/usr/bin/env python3
"""Script de automatización para migrar robots de descarga (V1 -> V2).

Flujo completo:
1. Inspecciona y valida el registro del robot en 'platform_db' (tabla 'file').
2. Refactoriza el código Python de V1 a los estándares estrictos de la V2.
3. Crea la estructura en 'models/download/<CODE>/'.
4. Ejecuta el test unitario correspondiente (Tipo I, II, III o IV).
5. Genera automáticamente el wrapper del DAG en 'dags/download/<CODE>.py'.
"""

import argparse
import importlib.util
import os
import re
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import create_engine

# Agregar directorio raíz al path para importaciones internas
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


def locate_source_file(code: str, old_repo_path: str = DEFAULT_OLD_REPO_PATH) -> Optional[str]:
    """Busca automáticamente el archivo .py del robot en el repositorio antiguo."""
    if not os.path.isdir(old_repo_path):
        return None

    # 1. Búsqueda directa en models/download/<CODE>/
    candidate_folder = os.path.join(old_repo_path, "models", "download", code)
    if os.path.isdir(candidate_folder):
        priority_files = [
            os.path.join(candidate_folder, f"Executor_{code}.py"),
            os.path.join(candidate_folder, f"{code}.py"),
        ]
        for fpath in priority_files:
            if os.path.isfile(fpath):
                return fpath

        # Buscar cualquier archivo .py que no sea __init__.py en esa carpeta
        for fname in os.listdir(candidate_folder):
            if fname.endswith(".py") and not fname.startswith("__"):
                return os.path.join(candidate_folder, fname)

    # 2. Búsqueda recursiva en models/download
    download_root = os.path.join(old_repo_path, "models", "download")
    if os.path.isdir(download_root):
        for root, _, files in os.walk(download_root):
            for fname in files:
                if fname.endswith(".py") and code in fname and not fname.startswith("__"):
                    return os.path.join(root, fname)

    return None


def get_db_engine():
    """Crea la conexión a platform_db usando variables de entorno o valores por defecto."""
    host = os.getenv("BUSINESS_DB_HOST", "10.0.0.16")
    port = os.getenv("BUSINESS_DB_PORT", "5434")
    user = os.getenv("BUSINESS_DB_USER", "postgres")
    password = os.getenv("BUSINESS_DB_PASSWORD", "datax")
    database = os.getenv("BUSINESS_DB_DATABASE", "platform_db")
    return create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}")


def fetch_robot_metadata(code: str, engine) -> Optional[Dict]:
    """Consulta los metadatos del robot en la tabla file de platform_db."""
    query = f"""
        SELECT id_file, code, name, main_url, download_type, 
               schedule_interval, updated_to, key_words, state, path
        FROM file 
        WHERE code = '{code}';
    """
    try:
        df = pd.read_sql_query(query, con=engine)
        if df.empty:
            return None
        return df.iloc[0].to_dict()
    except Exception as exc:
        error_print(f"Error al consultar la base de datos para {code}: {exc}")
        return None


def refactor_download_code(raw_code: str, code: str, download_type: str) -> str:
    """Transforma el código fuente V1 al estándar V2."""
    code_content = raw_code

    # 1. Asegurar herencia de Download_Base
    if "from models.download.Download_Base import Download_Base" not in code_content:
        code_content = (
            "from models.download.Download_Base import Download_Base\n"
            + code_content
        )

    # 2. Limpiar rutas obsoletas de sys.path
    code_content = re.sub(r"sys\.path\.append\(['\"][^'\"]*data-processing-platform[^'\"]*['\"]\)\s*", "", code_content)
    code_content = re.sub(r"sys\.path\.append\(['\"][^'\"]*platform_project[^'\"]*['\"]\)\s*", "", code_content)

    # 3. Renombrar clase principal a <CODE>, preservando clase base si no es Executor
    def _replace_class_parent(m):
        parent = m.group(1).strip() if m.group(1) else ""
        if parent in ["Executor", "object", ""] or not parent:
            parent = "Download_Base"
        return f"class {code}({parent}):"

    code_content, n = re.subn(
        r"class\s+Executor_[A-Za-z0-9_]+\s*(?:\(([^)]*)\))?\s*:",
        _replace_class_parent,
        code_content,
    )
    if n == 0:
        code_content = re.sub(
            r"class\s+[A-Za-z0-9_]+\s*(?:\(([^)]*)\))?\s*:",
            _replace_class_parent,
            code_content,
            count=1,
        )

    # 3. Corrección común en Playwright: row.query_selector_all("//td") -> "td"
    code_content = code_content.replace(
        'row.query_selector_all("//td")', 'row.query_selector_all("td")'
    )
    code_content = code_content.replace(
        "row.query_selector_all('//td')", "row.query_selector_all('td')"
    )

    # 4. Regla estricta Tipo I: compare_files debe retornar False si no hay novedades
    if "Tipo I" in download_type:
        # Reemplazar 'return []' en compare_files por 'return False'
        if "def compare_files" in code_content:
            parts = code_content.split("def compare_files")
            pre_compare = parts[0]
            compare_body = parts[1]

            # Reemplazar retornos de listas vacías al final de compare_files
            compare_body = re.sub(
                r"return\s+\[\]\s*$",
                "return False",
                compare_body,
                flags=re.MULTILINE,
            )
            code_content = pre_compare + "def compare_files" + compare_body

    # 5. Agregar alias de compatibilidad al final si no existen
    alias_footer = f"\n\nExecutor_{code} = {code}\nRobot = {code}\n"
    if f"Executor_{code} = {code}" not in code_content:
        code_content += alias_footer

    return code_content


def save_robot_files(code: str, refactored_code: str, base_dir: str = ROOT_DIR) -> Tuple[str, str]:
    """Crea la carpeta y el archivo <CODE>.py en models/download/<CODE>/."""
    dest_dir = os.path.join(base_dir, "models", "download", code)
    os.makedirs(dest_dir, exist_ok=True)

    # Eliminar __init__.py si existiera para mantener compatibilidad con el estándar del servidor
    init_path = os.path.join(dest_dir, "__init__.py")
    if os.path.exists(init_path):
        try:
            os.remove(init_path)
        except Exception:
            pass

    robot_path = os.path.join(dest_dir, f"{code}.py")
    with open(robot_path, "w", encoding="utf-8") as f:
        f.write(refactored_code)

    return dest_dir, robot_path


def run_robot_test(code: str, download_type: str, test_updated_to: Optional[str] = None, base_dir: str = ROOT_DIR) -> bool:
    """Ejecuta el test unitario correspondiente al tipo de descarga."""
    type_map = {
        "Tipo I": "test_download_type_i.py",
        "Tipo II": "test_download_type_ii.py",
        "Tipo III": "test_download_type_iii.py",
        "Tipo IV": "test_download_type_iv.py",
    }

    test_file = None
    for type_name, script_name in type_map.items():
        if type_name in download_type:
            test_file = script_name
            break

    if not test_file:
        error_print(f"Tipo de descarga desconocido para test: '{download_type}'")
        return False

    test_path = os.path.join(base_dir, "models", "download", "tests", test_file)
    info_print(f"Ejecutando test unitario: {test_file} para {code}...")

    env = os.environ.copy()
    env["CODE_ROBOT"] = code
    if test_updated_to:
        env["UPDATED_TO"] = test_updated_to
    elif "UPDATED_TO" not in env:
        env["UPDATED_TO"] = "2024-01-01"

    cmd = [sys.executable, "-m", "unittest", test_path]
    result = subprocess.run(cmd, cwd=base_dir, env=env, capture_output=True, text=True)

    if result.returncode == 0:
        success_print(f"Test unitario {test_file} APROBADO (OK) para {code}.")
        return True
    else:
        error_print(f"Test unitario FALLÓ para {code}.")
        if result.stderr:
            print(result.stderr)
        if result.stdout:
            print(result.stdout)
        return False


def generate_robot_dag(code: str, base_dir: str = ROOT_DIR) -> bool:
    """Genera el wrapper del DAG en dags/download/<CODE>.py invocando RobotCodeHandler."""
    try:
        generator_file = os.path.join(base_dir, "include", "main-generate.py")
        if not os.path.isfile(generator_file):
            error_print(f"Generador no encontrado: {generator_file}")
            return False

        spec = importlib.util.spec_from_file_location("main_generate", generator_file)
        if not spec or not spec.loader:
            error_print(f"No se pudo crear spec para {generator_file}")
            return False

        gen_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen_module)
        RobotCodeHandler = getattr(gen_module, "RobotCodeHandler")

        handler = RobotCodeHandler(process="download")
        handler.process_codes([code])
        if not handler.robots:
            error_print(f"No se pudo cargar la configuración de DAG para {code} desde BD.")
            return False

        handler.create_dags()
        dag_path = os.path.join(base_dir, "dags", "download", f"{code}.py")
        if os.path.isfile(dag_path):
            success_print(f"DAG generado exitosamente en: {dag_path}")
            return True
        else:
            error_print(f"El archivo DAG no se encontró tras la generación: {dag_path}")
            return False
    except Exception as exc:
        error_print(f"Error al generar DAG para {code}: {exc}")
        return False


def migrate_single_robot(
    code: str,
    source_file: str,
    engine,
    skip_test: bool = False,
    skip_dag: bool = False,
    test_updated_to: Optional[str] = None,
    dry_run: bool = False,
    base_dir: str = ROOT_DIR,
) -> bool:
    """Ejecuta el flujo completo de migración para un robot."""
    info_print(f"=== Procesando migración de {code} ===")

    if not os.path.isfile(source_file):
        error_print(f"Archivo origen no encontrado: {source_file}")
        return False

    meta = fetch_robot_metadata(code, engine)
    if not meta:
        error_print(f"Robot {code} no encontrado en la tabla 'file' de platform_db.")
        return False

    download_type = str(meta.get("download_type") or "Tipo I (file_download_template)")
    info_print(f"Metadatos encontrados: Nombre='{meta.get('name')}', Tipo='{download_type}'")

    with open(source_file, "r", encoding="utf-8", errors="ignore") as f:
        raw_code = f.read()

    refactored_code = refactor_download_code(raw_code, code, download_type)

    if dry_run:
        info_print(f"[DRY-RUN] Robot {code} refactorizado en memoria. No se escribirán archivos.")
        return True

    dest_dir, robot_path = save_robot_files(code, refactored_code, base_dir)
    success_print(f"Código refactorizado guardado en: {robot_path}")

    # Ejecutar test unitario
    if not skip_test:
        test_ok = run_robot_test(code, download_type, test_updated_to, base_dir)
        if not test_ok:
            error_print(f"La migración de {code} se detuvo debido a fallo en el test unitario.")
            return False
    else:
        info_print(f"Paso de prueba unitaria omitido (--skip-test).")

    # Generar DAG
    if not skip_dag:
        dag_ok = generate_robot_dag(code, base_dir)
        if not dag_ok:
            return False
    else:
        info_print(f"Paso de generación de DAG omitido (--skip-dag).")

    success_print(f"¡Migración completada con éxito para {code}!\n")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Automatizador de Migración de Robots de Descarga V1 -> V2"
    )
    parser.add_argument("--code", type=str, help="Código del robot (ej. D_BO_000000541)")
    parser.add_argument("--source", type=str, help="Ruta al archivo .py del repositorio antiguo")
    parser.add_argument(
        "--batch-dir",
        type=str,
        help="Carpeta que contiene múltiples scripts .py de robots antiguos a migrar",
    )
    parser.add_argument("--skip-test", action="store_true", help="Omitir la ejecución del test unitario")
    parser.add_argument(
        "--old-repo",
        type=str,
        default=DEFAULT_OLD_REPO_PATH,
        help=f"Ruta raíz del repositorio antiguo (por defecto: {DEFAULT_OLD_REPO_PATH})",
    )
    parser.add_argument(
        "--generate-dag",
        action="store_true",
        default=False,
        help="Generar el archivo DAG en dags/download (por defecto desactivado)",
    )
    parser.add_argument(
        "--skip-dag",
        action="store_true",
        default=True,
        help="Omitir la generación del archivo DAG (activo por defecto)",
    )
    parser.add_argument(
        "--test-updated-to",
        type=str,
        help="Fecha de corte para la prueba (por defecto 2024-01-01)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simular el proceso sin escribir archivos en disco",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Migrar automáticamente todos los robots encontrados en el repositorio antiguo",
    )

    args = parser.parse_args()

    if not args.code and not args.batch_dir and not args.batch:
        parser.print_help()
        print(f"\n[INFO] Repositorio antiguo por defecto: {DEFAULT_OLD_REPO_PATH}")
        print("Ejemplo de uso simple: python tools/migrate_download.py --code D_BO_000000541")
        sys.exit(1)

    engine = get_db_engine()

    if args.code:
        code = args.code.strip()
        source_file = args.source.strip() if args.source else None

        if not source_file:
            info_print(f"Buscando automáticamente el código de {code} en {args.old_repo}...")
            source_file = locate_source_file(code, args.old_repo)
            if not source_file:
                error_print(
                    f"No se encontró el archivo fuente para {code} en {args.old_repo}.\n"
                    f"Por favor proporciona la ruta manualmente con --source."
                )
                sys.exit(1)
            info_print(f"Archivo localizado automáticamente: {source_file}")

        effective_skip_dag = not args.generate_dag

        ok = migrate_single_robot(
            code=code,
            source_file=source_file,
            engine=engine,
            skip_test=args.skip_test,
            skip_dag=effective_skip_dag,
            test_updated_to=args.test_updated_to,
            dry_run=args.dry_run,
        )
        sys.exit(0 if ok else 1)

    elif args.batch or args.batch_dir:
        batch_path = (
            os.path.abspath(args.batch_dir)
            if args.batch_dir
            else os.path.join(args.old_repo, "models", "download")
        )
        if not os.path.isdir(batch_path):
            error_print(f"Directorio de lote no encontrado: {batch_path}")
            sys.exit(1)

        info_print(f"Buscando scripts de robots en: {batch_path}")
        results = []

        for root, _, files in os.walk(batch_path):
            for file_name in files:
                if not file_name.endswith(".py") or file_name.startswith("__"):
                    continue

                code_match = re.search(r"(D_[A-Z]{2}_\d{9})", file_name)
                if not code_match:
                    continue

                code = code_match.group(1)
                file_path = os.path.join(root, file_name)
                effective_skip_dag = not args.generate_dag
                ok = migrate_single_robot(
                    code=code,
                    source_file=file_path,
                    engine=engine,
                    skip_test=args.skip_test,
                    skip_dag=effective_skip_dag,
                    test_updated_to=args.test_updated_to,
                    dry_run=args.dry_run,
                )
                results.append((code, ok))

        print("\n=== RESUMEN DE MIGRACIÓN POR LOTE ===")
        for c, status in results:
            stat_str = "EXITOSO" if status else "FALLIDO"
            print(f"  - {c}: {stat_str}")


if __name__ == "__main__":
    main()
