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
        'sql_query': 'SELECT code, download_type, schedule_interval FROM file WHERE 1=1',
    },
    'conversion': {
        'db_table': 'report',
        'prefix': 'C',
        'sql_query': 'SELECT code FROM report WHERE "isActive" = TRUE',
    },
    'migration': {
        'db_table': 'report',
        'prefix': 'M',
        'sql_query': 'SELECT code FROM report WHERE "isActive" = TRUE',
    },
    'product': {
        'db_table': 'data_base',
        'prefix': 'DB',
        'sql_query': 'SELECT db_code AS code FROM data_base WHERE 1=1',
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
    BASE_PATH = '/opt/airflow/'
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

        if isinstance(codes_input, list):
            select_mask = df['code'].isin(codes_input)
            df = df.loc[select_mask]

        if df.empty:
            info_print("No codes found for the selected process and country.")
            return

        df['code'] = df['code'].apply(lambda x: "_".join([prefix] + x.split('_')[1:3]))
        df = df.drop_duplicates()
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
                match = re.search(r'[(](.*)[)]', robot['download_type'])
                template = "_".join(match.group(1).strip().split('_')[:-1])
            elif self.process == 'product' and self.product_template:
                template = self.product_template
            else:
                template = self.process

            for line in fileinput.input(robot_file_path, inplace=True):
                line = line.replace("dag-id", "'" + robot['code'] + "'")
                line = line.replace("tagsToReplace", "'" + self.process.capitalize() + "'")
                line = line.replace("connection-id", "'" + self.DATA_BASE + "'")
                line = line.replace("dag-template", f"{template}_template")
                if self.process == 'download':
                    line = line.replace("#schedule=", "schedule=")
                    line = line.replace("schedule-to-replace", f"'{robot['schedule_interval']}'")
                print(line, end="")

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
