#!/usr/bin/env python3
import os
import re
import shutil
import fileinput
import pandas as pd
from typing import List
from dotenv import load_dotenv
from sqlalchemy import create_engine
from console import info_print, error_print, success_print

load_dotenv()

process_dict = {
    'download': {
        'db_table': 'file',
        'prefix': 'D',
        'sql_query': (
            'SELECT f.code, f.name AS file_name, f.download_type, f.schedule_interval, '
            'f.updated_to, f.main_url, f.navigation_path, '
            's.short_name, s.name AS source_name, '
            'COALESCE(STRING_AGG(DISTINCT db.db_code, \', \'), \'\') AS dataset, '
            'COALESCE(STRING_AGG(DISTINCT db.name, \' / \'), \'\') AS dataset_name '
            'FROM file f '
            'JOIN source s ON f.id_source = s.id_source '
            'LEFT JOIN report r ON r.id_file = f.id_file '
            'LEFT JOIN data_base_report dbr ON dbr.report_code = r.code '
            'LEFT JOIN data_base db ON db.db_code = dbr.db_code '
            'WHERE 1=1 '
            'GROUP BY f.code, f.name, f.download_type, f.schedule_interval, f.updated_to, '
            'f.main_url, f.navigation_path, s.short_name, s.name'
        ),
    },
    'conversion': {
        'db_table': 'report',
        'prefix': 'C',
        'sql_query': (
            'SELECT r.code, r.name AS report_name, r.converted_to, r.key_words, '
            'r.path AS path_file, r.page_number AS location, '
            's.short_name, s.name AS source_name, '
            'COALESCE(STRING_AGG(DISTINCT db.db_code, \', \'), \'\') AS dataset, '
            'COALESCE(STRING_AGG(DISTINCT db.name, \' / \'), \'\') AS dataset_name '
            'FROM report r '
            'JOIN file f ON r.id_file = f.id_file '
            'JOIN source s ON f.id_source = s.id_source '
            'LEFT JOIN data_base_report dbr ON dbr.report_code = r.code '
            'LEFT JOIN data_base db ON db.db_code = dbr.db_code '
            'WHERE 1=1 '
            'GROUP BY r.code, r.name, r.converted_to, r.key_words, r.path, r.page_number, s.short_name, s.name'
        ),
    },
    'migration': {
        'db_table': 'report',
        'prefix': 'M',
        'sql_query': (
            'SELECT r.code, r.name AS report_name, r.migrated_to, r.storage_table, '
            's.short_name, s.name AS source_name, '
            'COALESCE(STRING_AGG(DISTINCT db.db_code, \', \'), \'\') AS dataset, '
            'COALESCE(STRING_AGG(DISTINCT db.name, \' / \'), \'\') AS dataset_name '
            'FROM report r '
            'JOIN file f ON r.id_file = f.id_file '
            'JOIN source s ON f.id_source = s.id_source '
            'LEFT JOIN data_base_report dbr ON dbr.report_code = r.code '
            'LEFT JOIN data_base db ON db.db_code = dbr.db_code '
            'WHERE 1=1 '
            'GROUP BY r.code, r.name, r.migrated_to, r.storage_table, s.short_name, s.name'
        ),
    },
    'product': {
        'db_table': 'data_base',
        'prefix': 'DB',
        'sql_query': (
            'SELECT DISTINCT ON (db.db_code) db.db_code AS code, '
            's.short_name, s.name AS source_name '
            'FROM data_base db '
            'JOIN data_base_report dbr ON db.db_code = dbr.db_code '
            'JOIN report r ON dbr.report_code = r.code '
            'JOIN file f ON r.id_file = f.id_file '
            'JOIN source s ON f.id_source = s.id_source '
            'ORDER BY db.db_code, s.short_name'
        ),
    },
}

PRODUCT_TEMPLATES = {
    '1': 'product',
    '2': 'product_dbt',
    '3': 'product_star_model',
}


def get_number_choose(max: int):
    choose = input(">> ").strip()
    try:
        choose = int(choose)
        if 1 > choose or choose > max:
            raise ValueError
        return choose
    except ValueError:
        return None


def get_choice_process():
    process_list = list(process_dict.keys())
    while True:
        info_print("Choose a process to generate DAGs for:")
        for i, value in enumerate(process_list):
            print(f'{i + 1}. {value.capitalize()}')
        print(f"{len(process_list) + 1}. Cancel")

        process = get_number_choose(max=len(process_list) + 1)
        if process:
            if process == len(process_list) + 1:
                info_print("Operation cancelled.")
                return None
            chosen = process_list[process - 1]
            success_print(f"Selected: {chosen.upper()}")
            return chosen
        else:
            error_print("Invalid option. Please enter a number from the list.")


def get_product_template():
    while True:
        info_print("Choose a product template type:")
        print("1. Python Product   (product_template)")
        print("2. DBT Product      (product_dbt_template)")
        print("3. Star Model       (product_star_model_template)")
        print("4. Cancel")

        choice = get_number_choose(max=4)
        if choice:
            if choice == 4:
                return None
            return PRODUCT_TEMPLATES[str(choice)]
        else:
            error_print("Invalid option. Please enter a number from the list.")


def get_second_choose(process: str):
    if not process:
        return None

    num_char = 14 if process != "product" else 12

    while True:
        info_print(f"Selected process: {process.upper()}")
        info_print("Choose an option:")
        print("1. Enter robot code(s) separated by ';'")
        print("2. Process ALL available robots")
        print("3. Cancel")

        second_choose = get_number_choose(3)
        if second_choose:
            if second_choose == 3:
                info_print("Operation cancelled.")
                return None
            elif second_choose == 2:
                success_print("'ALL' option selected.")
                return "ALL"
            elif second_choose == 1:
                codes = [code.strip() for code in input("Enter code(s):\n>> ").upper().split(";")]

                prefix = ['DB'] if process == "product" else [process[0].upper()]
                codes_error = [code for code in codes if len(code) != num_char]
                codes_error += [
                    code for code in codes
                    if code.split('_')[0] not in prefix and code not in codes_error
                ]

                if codes_error:
                    error_print("These codes are invalid and will be ignored:")
                    for code in codes_error:
                        print(f"  - {code}")

                valid_codes = [code for code in codes if code not in codes_error]
                if not valid_codes:
                    error_print("No valid codes entered. Try again.")
                    continue
                success_print(f"Valid codes to be processed: {valid_codes}")
                return valid_codes
        else:
            error_print("Invalid option. Please enter a number from the list.")


class RobotCodeHandler:
    BASE_PATH = '/opt/airflow/' if os.path.exists('/opt/airflow/include/dag_template.py') else os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    DATA_BASE = 'platform_db'

    def __init__(self, process: str, product_template: str = None):
        self.process = process
        self.product_template = product_template
        self.robots = []
        self._get_db_con()

    def _get_db_con(self):
        host = os.getenv("BUSINESS_DB_HOST")
        port = os.getenv("BUSINESS_DB_PORT")
        user = os.getenv("BUSINESS_DB_USER")
        password = os.getenv("BUSINESS_DB_PASSWORD")
        database = os.getenv("BUSINESS_DB_DATABASE")
        self.engine = create_engine(f'postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}')

    def process_codes(self, codes_input):
        country = os.getenv("COUNTRY")
        sql_query = process_dict[self.process]['sql_query']
        prefix = process_dict[self.process]['prefix']

        df = pd.read_sql_query(sql_query, con=self.engine)

        country_mask = df['code'].apply(lambda x: x.split('_')[1] == country)
        df = df.loc[country_mask]

        # Transform before filtering so user codes (C_BO_* / M_BO_*) match DB values
        df['code'] = df['code'].apply(lambda x: "_".join([prefix] + x.split('_')[1:3]))
        
        if self.process == 'conversion':
            agg_dict = {
                'short_name': 'first',
                'source_name': 'first',
                'dataset': lambda x: ', '.join(sorted(set(filter(None, [s.strip() for item in x.dropna() for s in str(item).split(',')])))),
                'dataset_name': lambda x: ' / '.join(sorted(set(filter(None, [s.strip() for item in x.dropna() for s in str(item).split('/')])))),
                'report_name': lambda x: ' / '.join(sorted(set(filter(None, x.dropna().astype(str))))),
                'converted_to': lambda x: max([d for d in x if pd.notna(d)], default=None),
                'key_words': lambda x: ', '.join(sorted(set(filter(None, x.dropna().astype(str))))),
                'path_file': 'first',
                'location': 'first',
            }
            df = df.groupby('code', as_index=False).agg(agg_dict)
        elif self.process == 'migration':
            agg_dict = {
                'short_name': 'first',
                'source_name': 'first',
                'dataset': lambda x: ', '.join(sorted(set(filter(None, [s.strip() for item in x.dropna() for s in str(item).split(',')])))),
                'dataset_name': lambda x: ' / '.join(sorted(set(filter(None, [s.strip() for item in x.dropna() for s in str(item).split('/')])))),
                'report_name': lambda x: ' / '.join(sorted(set(filter(None, x.dropna().astype(str))))),
                'storage_table': lambda x: ' / '.join(sorted(set(filter(None, x.dropna().astype(str))))),
                'migrated_to': lambda x: max([d for d in x if pd.notna(d)], default=None),
            }
            df = df.groupby('code', as_index=False).agg(agg_dict)
        else:
            df = df.drop_duplicates(subset=['code'])

        if isinstance(codes_input, list):
            select_mask = df['code'].isin(codes_input)
            df = df.loc[select_mask]

        if df.empty:
            info_print("No codes found for the selected process and country.")
            return
        df['file_path'] = df['code'].apply(lambda x: self._build_model_path(code=x))

        self.robots = df.to_dict(orient='records')

    def _build_model_path(self, code: str) -> str:
        return os.path.join(self.BASE_PATH, 'models', self.process, code)

    def create_dags(self):
        dag_template_path = os.path.join(self.BASE_PATH, 'include', 'dag_template.py')
        if not os.path.exists(dag_template_path):
            error_print(f"Template not found: {dag_template_path}")
            return

        for robot in self.robots:
            robot_file_path = os.path.join(
                self.BASE_PATH, 'dags', self.process, f'{robot["code"]}.py'
            )
            os.makedirs(os.path.dirname(robot_file_path), exist_ok=True)
            shutil.copyfile(dag_template_path, robot_file_path)

            # Resolve template name
            if self.process == 'download':
                match = re.search(r'[(](.*)[)]', str(robot.get('download_type', '')))
                if match:
                    template = "_".join(match.group(1).strip().split('_')[:-1])
                else:
                    template = 'file_download'
            elif self.process == 'product' and self.product_template:
                template = self.product_template
            else:
                template = self.process

            # Build enriched tags
            tags = []
            short_name = str(robot.get('short_name') or '').strip()
            if short_name:
                tags.append(short_name)

            dataset = str(robot.get('dataset') or '').strip()
            if dataset:
                for ds in dataset.split(','):
                    ds_clean = ds.strip()
                    if ds_clean and ds_clean not in tags:
                        tags.append(ds_clean)

            tags.append(self.process.capitalize())

            if self.process == 'download':
                updated_to = str(robot.get('updated_to') or '').strip()
                if updated_to and updated_to != 'None':
                    tags.append(updated_to)
            elif self.process == 'conversion':
                converted_to = robot.get('converted_to')
                if converted_to and str(converted_to) != 'None':
                    tags.append(str(converted_to).strip())
                key_words = str(robot.get('key_words') or '').strip()
                if key_words and key_words != 'None':
                    kw_clean = key_words.split(',')[0].strip()
                    if kw_clean and kw_clean not in tags:
                        tags.append(kw_clean)
            elif self.process == 'migration':
                migrated_to = robot.get('migrated_to')
                if migrated_to and str(migrated_to) != 'None':
                    tags.append(str(migrated_to).strip())

            tags_str = ", ".join([f"'{t}'" for t in tags])

            # Build doc_md content as clean GFM Markdown Table (100% compatible with Airflow 3)
            def clean_val(val, default='-'):
                if val is None or pd.isna(val) or str(val).strip().lower() in ('nan', 'none', ''):
                    return default
                return str(val).strip()

            source_name = clean_val(robot.get("source_name"))
            short_name = clean_val(robot.get("short_name"))
            datasets_str = clean_val(robot.get("dataset"))
            dataset_name = clean_val(robot.get("dataset_name"))

            if self.process == 'download':
                url = clean_val(robot.get('main_url'), default='#')
                url_display = f"[Abrir portal ↗]({url})" if url != '#' else '-'
                doc_md_str = (
                    f"## 📥 DAG Descarga: {robot['code']}\n\n"
                    f"| Parámetro | Detalle |\n"
                    f"|---|---|\n"
                    f"| **🏛️ Fuente** | **{short_name}** ({source_name}) |\n"
                    f"| **📊 Dataset(s)** | `{datasets_str}` |\n"
                    f"| **📝 Nombre Dataset** | {dataset_name} |\n"
                    f"| **📁 Archivo** | {clean_val(robot.get('file_name'))} |\n"
                    f"| **⚙️ Tipo Descarga** | {clean_val(robot.get('download_type'))} |\n"
                    f"| **📅 Última Descarga** | **{clean_val(robot.get('updated_to'))}** |\n"
                    f"| **⏱️ Frecuencia** | `{clean_val(robot.get('schedule_interval'))}` |\n"
                    f"| **🧭 Ruta Web** | {clean_val(robot.get('navigation_path'))} |\n"
                    f"| **🌐 Portal Web** | {url_display} |\n"
                )
            elif self.process == 'conversion':
                raw_path = clean_val(robot.get('path_file'))
                clean_path = raw_path.replace('\\', '/') if raw_path != '-' else '-'
                doc_md_str = (
                    f"## 🔄 DAG Conversión: {robot['code']}\n\n"
                    f"| Parámetro | Detalle |\n"
                    f"|---|---|\n"
                    f"| **🏛️ Fuente** | **{short_name}** ({source_name}) |\n"
                    f"| **📊 Dataset(s)** | `{datasets_str}` |\n"
                    f"| **📝 Nombre Dataset** | {dataset_name} |\n"
                    f"| **📄 Reporte(s)** | {clean_val(robot.get('report_name'))} |\n"
                    f"| **📅 Última Conversión** | **{clean_val(robot.get('converted_to'))}** |\n"
                    f"| **🔑 Palabras Clave** | {clean_val(robot.get('key_words'))} |\n"
                    f"| **📍 Ubicación** | {clean_val(robot.get('location'))} |\n"
                    f"| **💾 Ruta Almacén** | `{clean_path}` |\n"
                )
            elif self.process == 'migration':
                doc_md_str = (
                    f"## 🚚 DAG Migración: {robot['code']}\n\n"
                    f"| Parámetro | Detalle |\n"
                    f"|---|---|\n"
                    f"| **🏛️ Fuente** | **{short_name}** ({source_name}) |\n"
                    f"| **📊 Dataset(s)** | `{datasets_str}` |\n"
                    f"| **📝 Nombre Dataset** | {dataset_name} |\n"
                    f"| **📄 Sub-reporte(s)** | {clean_val(robot.get('report_name'))} |\n"
                    f"| **🗄️ Tabla(s) Almacén** | `{clean_val(robot.get('storage_table'))}` |\n"
                    f"| **📅 Última Migración** | **{clean_val(robot.get('migrated_to'))}** |\n"
                )
            else:
                doc_md_str = (
                    f"## 📋 DAG {self.process.capitalize()}: {robot['code']}\n\n"
                    f"- **Fuente:** **{short_name}**\n"
                    f"- **Tipo:** {self.process.capitalize()}\n"
                )

            with open(robot_file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()

            file_content = file_content.replace("dag-id", f"'{robot['code']}'")
            file_content = file_content.replace("tagsToReplace", tags_str)
            file_content = file_content.replace("docMdToReplace", doc_md_str.replace('"""', "'''"))
            file_content = file_content.replace("connection-id", f"'{self.DATA_BASE}'")
            file_content = file_content.replace("dag-template", f"{template}_template")
            if self.process == 'download':
                file_content = file_content.replace("#schedule=", "schedule=")
                file_content = file_content.replace("schedule-to-replace", f"'{robot['schedule_interval']}'")

            with open(robot_file_path, 'w', encoding='utf-8') as f:
                f.write(file_content)

            success_print(f"Generated: {robot_file_path}")


def main():
    info_print("=== DAG Generator ===")

    process = get_choice_process()
    if not process:
        return

    product_template = None
    if process == 'product':
        product_template = get_product_template()
        if not product_template:
            return

    codes = get_second_choose(process=process)
    if not codes:
        info_print("Exiting.")
        return

    handler = RobotCodeHandler(process=process, product_template=product_template)
    handler.process_codes(codes_input=codes)

    if not handler.robots:
        info_print("No matching robots found. Nothing to generate.")
        return

    handler.create_dags()
    success_print(f"Done! {len(handler.robots)} DAG(s) generated.")


if __name__ == "__main__":
    main()
