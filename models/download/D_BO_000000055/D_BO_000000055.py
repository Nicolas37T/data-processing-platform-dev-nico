import os
import shutil
import traceback
import time
import re
from datetime import datetime
from playwright.sync_api import sync_playwright
import pandas as pd
from models.download.tools.download_tools import format_date

try:
    from models.download.Download_Base import Download_Base
except ImportError:
    Download_Base = object


class D_BO_000000055(Download_Base):
    """
    Robot de Descarga Tipo II: Ubicación de Puntos de Atención de Entidades Financieras (ASFI)
    Obtiene el consolidado nacional de puntos de atención financiera a nivel nacional.
    """

    def verify_download(self, main_url: str, updated_to: str, path: str, key_words: str = "", format: str = "%Y-%m-%d") -> list:
        """
        Descarga el consolidado nacional de puntos de atención desde ASFI.
        Retorna lista de diccionarios con llaves exactas: {'tmp_path', 'download_url'}.
        """
        # Limpieza rigurosa de carpeta temporal tmp
        tmp_dir = os.path.join(path, "tmp")
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
        os.makedirs(tmp_dir, exist_ok=True)

        # XPaths de los elementos en el portal ASFI
        entidad_checkbox_xpath = '//*[@id="ASPxTreeListEntidades_D"]//td/span'
        departamento_checkbox_xpath = '//*[@id="ASPxTreeListDepartamentos_D"]//td/span'
        tipo_checkbox_xpath = '//*[@id="ASPxTreeTipoSucursal_R-100_D"]'
        search_button_xpath = '//*[@id="btnBuscar_CD"]'
        export_button_xpath = '//*[@id="btnReporte_CD"]'

        with sync_playwright() as pl:
            browser = None
            try:
                print(f"Iniciando navegador hacia {main_url}...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                context.set_default_timeout(60000)
                page = context.new_page()
                page.goto(main_url, timeout=60000)

                # 1. Seleccionar 'Todos' en Entidades (índice 0)
                page.locator(entidad_checkbox_xpath).first.wait_for(state="visible", timeout=30000)
                print("Seleccionando filtro Entidades: Todos...")
                page.locator(entidad_checkbox_xpath).first.click()
                time.sleep(1)

                # 2. Seleccionar 'Todos' en Departamentos (índice 0)
                page.locator(departamento_checkbox_xpath).first.wait_for(state="visible", timeout=30000)
                print("Seleccionando filtro Departamentos: Todos...")
                page.locator(departamento_checkbox_xpath).first.click()
                time.sleep(1)

                # 3. Seleccionar 'Todos' en Tipo de PAF
                tipo_loc = page.locator(tipo_checkbox_xpath)
                tipo_loc.wait_for(state="visible", timeout=30000)
                print("Seleccionando filtro Tipo de PAF: Todos...")
                tipo_loc.click()
                time.sleep(1)

                # 4. Ejecutar búsqueda consolidada
                print("Ejecutando búsqueda consolidada...")
                page.locator(search_button_xpath).click()

                # Esperar a que el ciclo AJAX de ASP.NET termine completamente
                # y que el overlay UpdateProgress2 desaparezca
                print("Esperando procesamiento AJAX y desaparición de overlays...")
                time.sleep(2)
                try:
                    page.wait_for_selector("#UpdateProgress2", state="hidden", timeout=60000)
                except Exception:
                    pass
                page.wait_for_load_state("networkidle")
                time.sleep(2)
                print("Búsqueda completada exitosamente.")

                # 5. Exportar reporte a Excel usando Locator dinámico (evita 'Element not attached to DOM')
                export_loc = page.locator(export_button_xpath)
                export_loc.wait_for(state="visible", timeout=30000)

                today_str = datetime.today().strftime("%Y-%m-%d_%H%M%S")
                download_path = os.path.join(tmp_dir, f"{today_str}_download.xlsx")

                print("Iniciando descarga del archivo consolidado...")
                with page.expect_download(timeout=60000) as download_info:
                    export_loc.click()

                download = download_info.value
                download.save_as(download_path)
                print(f"Archivo descargado exitosamente en: {download_path} ({os.path.getsize(download_path)} bytes)")

                return [{"tmp_path": download_path, "download_url": main_url}]

            except Exception as e:
                print(f"Error en verify_download: {e}")
                traceback.print_exc()
                return []
            finally:
                if browser:
                    browser.close()

    def compare_files(self, files_paths: list, updated_to: str, format: str = "%Y-%m-%d") -> list:
        """
        Inspecciona la fecha del archivo descargado y verifica que sea posterior a updated_to.
        Retorna lista de diccionarios con llaves exactas: {'tmp_path', 'updated_to', 'download_url'}.
        """
        print("Comparando fechas de archivos descargados...")
        files_dicts = []
        updated_to_dt = format_date(updated_to)
        re_date = r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})"

        for file_info in files_paths:
            file_path = file_info["tmp_path"]
            print(f"Inspeccionando archivo: {file_path}")

            df_new_file = pd.read_excel(file_path)
            for column in df_new_file.columns:
                if df_new_file[column].isna().all():
                    df_new_file.drop(columns=[column], inplace=True)

            sub_set = df_new_file.iloc[:5]
            dates = []
            for row in range(len(sub_set)):
                row_vals = sub_set.iloc[row]
                for val in row_vals:
                    m = re.search(re_date, str(val))
                    if m:
                        dates.append(m)

            if not dates:
                print("No se encontró fecha en la cabecera del archivo.")
                continue

            last_match = dates[-1]
            day, month, year = last_match.group(1), last_match.group(2), last_match.group(3)
            date_formatted = format_date(f"{year}-{month}-{day}")

            if date_formatted > updated_to_dt:
                print(f"Fecha del reporte: {date_formatted.strftime(format)} > {updated_to_dt.strftime(format)}")
                file_info["updated_to"] = date_formatted.strftime(format)
                files_dicts.append(file_info)
            else:
                print(f"Fecha del reporte ({date_formatted.strftime(format)}) no es posterior a {updated_to_dt.strftime(format)}.")

        if not files_dicts:
            print(f"No hay archivos posteriores a {updated_to_dt.strftime(format)}")
            return False

        return files_dicts


Executor_D_BO_000000055 = D_BO_000000055
Robot = D_BO_000000055
