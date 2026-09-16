#!/usr/bin/env python3
"""
Herramienta CLI para Despliegue Automatizado de Robots al Servidor Remoto (10.0.0.16)
Copia la carpeta models/<tipo>/<CODIGO> y ejecuta la generación de DAG en Docker.
"""

import os
import sys
import getpass
import argparse
from typing import Optional

# Añadir ruta raíz para importar console y utilidades si existen
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

try:
    from include.console import info_print, error_print, success_print
except ImportError:
    def info_print(m): print(f"[INFO] {m}")
    def error_print(m): print(f"[ERROR] {m}")
    def success_print(m): print(f"[SUCCESS] {m}")

try:
    import paramiko
except ImportError:
    error_print("La librería 'paramiko' no está instalada. Ejecuta: pip install paramiko")
    sys.exit(1)


def deploy_robot(
    host: str,
    port: int,
    username: str,
    password: Optional[str],
    code: str,
    process_type: str,
    remote_base_path: str,
    generate_dag: bool = True
) -> bool:
    local_dir = os.path.join(ROOT_DIR, "models", process_type, code)
    if not os.path.isdir(local_dir):
        error_print(f"Carpeta local del robot no encontrada: {local_dir}")
        return False

    info_print(f"Conectando a {username}@{host}:{port}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            timeout=10,
            look_for_keys=True if not password else False
        )
        success_print("Conexión SSH establecida con el servidor.")

        remote_folder = f"{remote_base_path}/models/{process_type}/{code}"
        info_print(f"Preparando directorio remoto: {remote_folder}...")

        stdin, stdout, stderr = client.exec_command(f"mkdir -p '{remote_folder}'")
        if stdout.channel.recv_exit_status() != 0:
            if password:
                sudo_cmd = f"echo '{password}' | sudo -S mkdir -p '{remote_folder}' && echo '{password}' | sudo -S chown -R {username}:{username} '{remote_folder}'"
                stdin, stdout, stderr = client.exec_command(sudo_cmd)
                if stdout.channel.recv_exit_status() != 0:
                    err = stderr.read().decode("utf-8", errors="ignore").strip()
                    error_print(f"Error creando carpeta con sudo: {err}")
                    return False
            else:
                error_print("Faltan permisos en la carpeta remota y no se proporcionó contraseña sudo.")
                return False

        # SFTP Transfer
        info_print(f"Transfiriendo archivos vía SFTP desde {local_dir}...")
        sftp = client.open_sftp()

        if process_type == "conversion":
            # Para conversión: en models/conversion/<CODE> SOLO van archivos .py
            for f in os.listdir(local_dir):
                if not f.endswith(".py") or f in ("__init__.py", "__pycache__", ".DS_Store"):
                    continue
                lp = os.path.join(local_dir, f)
                if os.path.isfile(lp):
                    rp = f"{remote_folder}/{f}"
                    info_print(f"  -> Subiendo código Python {f} a {remote_folder}")
                    sftp.put(lp, rp)

            # Limpiar archivos no deseados (.xlsx, .pdf, .sqlite, etc.) en models/conversion/<CODE>
            clean_cmd = f"rm -f '{remote_folder}/*.xlsx' '{remote_folder}/*.pdf' '{remote_folder}/*.sqlite' '{remote_folder}/*.csv' '{remote_folder}/__init__.py'"
            client.exec_command(clean_cmd)

            # Subir archivos .sqlite a /mnt/datos1/data_process/<PAIS>/<D_CODE>/
            parts = code.split("_")
            country = parts[1] if len(parts) > 1 else "BO"
            d_code = f"D_{parts[1]}_{parts[2]}" if len(parts) >= 3 else code.replace("C_", "D_")
            remote_data_dir = f"/mnt/datos1/data_process/{country}/{d_code}"

            sqlite_files = [f for f in os.listdir(local_dir) if f.endswith(".sqlite") and os.path.isfile(os.path.join(local_dir, f))]
            if sqlite_files:
                info_print(f"Preparando directorio de datos para SQLite: {remote_data_dir}...")
                mkdir_sql = f"mkdir -p '{remote_data_dir}' && chmod 777 '{remote_data_dir}'"
                stdin, stdout, stderr = client.exec_command(mkdir_sql)
                if stdout.channel.recv_exit_status() != 0 and password:
                    sudo_sql = f"echo '{password}' | sudo -S mkdir -p '{remote_data_dir}' && echo '{password}' | sudo -S chmod 777 '{remote_data_dir}'"
                    stdin, stdout, stderr = client.exec_command(sudo_sql)
                    stdout.channel.recv_exit_status()

                for sql_f in sqlite_files:
                    local_sql = os.path.join(local_dir, sql_f)
                    remote_sql = f"{remote_data_dir}/{sql_f}"
                    info_print(f"  -> Subiendo archivo SQLite {sql_f} a {remote_data_dir}...")
                    sftp.put(local_sql, remote_sql)
                    client.exec_command(f"chmod 777 '{remote_sql}'")
                    if password:
                        client.exec_command(f"echo '{password}' | sudo -S chmod 777 '{remote_sql}'")
                    success_print(f"Archivo SQLite {sql_f} subido correctamente a {remote_data_dir}.")
        else:
            for f in os.listdir(local_dir):
                if f in ("__init__.py", "__pycache__", ".DS_Store") or f.endswith(".pyc"):
                    continue
                lp = os.path.join(local_dir, f)
                if os.path.isfile(lp):
                    rp = f"{remote_folder}/{f}"
                    info_print(f"  -> Subiendo {f}")
                    sftp.put(lp, rp)

        sftp.close()

        # Limpiar __init__.py remoto si existiera
        client.exec_command(f"rm -f '{remote_folder}/__init__.py'")
        success_print("Archivos transferidos correctamente.")

        # Generar DAG en Docker
        if generate_dag:
            info_print("Ejecutando generador de DAGs en Docker...")
            proc_opt = "1" if process_type == "download" else "2"
            gen_cmd = (
                f"cd {remote_base_path} && "
                f"printf '{proc_opt}\\n1\\n{code}\\n' | "
                f"docker compose exec -T airflow-worker python include/main-generate.py"
            )
            stdin, stdout, stderr = client.exec_command(gen_cmd, get_pty=True)
            for line in iter(stdout.readline, ""):
                clean = line.strip()
                if clean:
                    print(f"  [Docker] {clean}")

            status = stdout.channel.recv_exit_status()
            if status == 0:
                success_print(f"¡DAG para {code} generado exitosamente en Airflow!")
            else:
                error_print(f"Aviso: El proceso terminó con código {status}.")

        client.close()
        success_print(f"Despliegue de {code} finalizado con éxito.")
        return True

    except Exception as e:
        error_print(f"Fallo durante el despliegue: {e}")
        if client:
            client.close()
        return False


def main():
    parser = argparse.ArgumentParser(description="Desplegar robot al servidor remoto (10.0.0.16) y crear DAG en Docker.")
    parser.add_argument("--code", type=str, help="Código del robot (ej. D_BO_000000047)")
    parser.add_argument("--type", type=str, choices=["download", "conversion"], default="download", help="Tipo de proceso")
    parser.add_argument("--host", type=str, default="10.0.0.16", help="IP del servidor")
    parser.add_argument("--port", type=int, default=22, help="Puerto SSH")
    parser.add_argument("--user", type=str, default="datax-pds", help="Usuario SSH")
    parser.add_argument("--password", type=str, help="Contraseña SSH / sudo (si se omite, se solicitará)")
    parser.add_argument("--remote-path", type=str, default="/home/datax-pds/datax/data-processing-platform-dev", help="Ruta de la plataforma en el servidor")
    parser.add_argument("--no-dag", action="store_true", help="Omitir la generación del DAG en Docker")

    args = parser.parse_args()

    if not args.code:
        parser.print_help()
        sys.exit(1)

    password = args.password
    if not password:
        password = getpass.getpass(f"Introduce la contraseña para {args.user}@{args.host}: ")

    ok = deploy_robot(
        host=args.host,
        port=args.port,
        username=args.user,
        password=password,
        code=args.code.strip(),
        process_type=args.type,
        remote_base_path=args.remote_path,
        generate_dag=not args.no_dag
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
