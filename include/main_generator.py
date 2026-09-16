import os
import re
import shutil
import fileinput
import pandas as pd
from typing import List
from sqlalchemy import create_engine
from console import info_print, error_print, success_print
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
# List of available processes
process_dict = {
    'download':{
        'db_table':'file',
        'prefix':'D',
        'sql_query':'SELECT code,download_type,schedule_interval FROM file WHERE 1=1',
    }, 
    'conversion':{
        'db_table':'report',
        'prefix':'C',
        'sql_query':'SELECT code FROM report WHERE \"isActive\" = TRUE',
    }, 
    'migration':{
        'db_table':'report',
        'prefix':'M',
        'sql_query':'SELECT code FROM report WHERE \"isActive\" = TRUE',
    }, 
    'product':{
        'db_table':'data_base',
        'prefix':'DB',
        'sql_query':'SELECT db_code AS code FROM data_base WHERE 1=1',
    }
}

def get_number_choose(max:int):
    """
    Prompts the user to enter an integer value.
    Returns None if the input is not a valid integer within the allowed range.
    """
    choose = input(">> ").strip()
    
    try:
        choose = int(choose)
        if 1 > choose  or choose > max:
            raise ValueError
        return choose
    except ValueError:
        return None

def get_choice_process():
    """
    Displays the list of processes and returns the selected one.
    Returns None if the user chooses to cancel.
    """
    process_list = list(process_dict.keys())
    print(process_list)
    while True:
        info_print("🔧 Choose a process to execute:")
        for i,value in enumerate(process_list):
            print(f'{i+1}. {value.capitalize()}')
        print(f"{len(process_list)+1}. Cancel")

        process = get_number_choose(max=len(process_list)+1)

        if process:
            if process == len(process_list)+1:
                info_print("❌ Operation cancelled by user.")
                return
            chosen_process = process_list[process - 1]
            success_print(f"✅ You selected: {chosen_process.upper()}")
            return chosen_process
        else:
            error_print("❗ Invalid option. Please enter a number from the list.")

def get_second_choose(process:str):
    """
    Based on the selected process, allows the user to choose specific robot codes or 'ALL'.
    Returns a list of valid robot codes or the string 'ALL'. Returns None if cancelled.
    """
    if not process:
        return

    num_char = 14 if process != "product" else 12

    while True:
        info_print(f"🔄 Selected process: {process.upper()}")
        info_print("📋 Choose an option:")
        print("1. Enter robot code(s) separated by ';'")
        print("2. Process ALL available robots")
        print("3. Cancel")

        second_choose = get_number_choose(3)

        if second_choose:
            if second_choose == 3:
                info_print("❌ Operation cancelled by user.")
                return
            elif second_choose == 2:
                success_print("✅ 'ALL' option selected.")
                return "ALL"
            elif second_choose == 1:
                codes = [code.strip() for code in input("🔠 Enter code(s):\n>> ").upper().split(";")]

                # Validate code length
                codes_error = [code for code in codes if len(code) != num_char]

                # Validate code prefix
                prefix = ['db'] if process == "product" else [process[0].upper()]
                codes_error += [
                    code for code in codes
                    if code.split('_')[0] not in prefix and code not in codes_error
                ]

                # Show invalid codes
                if codes_error:
                    error_print("⚠️ These codes are invalid and will be ignored:")
                    for code in codes_error:
                        print(f"  - {code}")

                # Filter valid codes only
                valid_codes = [code for code in codes if code not in codes_error]
                success_print(f"✅ Valid codes to be processed: {valid_codes}")
                return valid_codes                
        else:
            error_print("❗ Invalid option. Please enter a number from the list.")

class RobotCodeHandler:
    """Clase encargada de manejar la validación y conversión de códigos de archivo."""
    BASE_PATH = '/opt/airflow/'
    DATA_BASE = "platform_db"

    def __init__(self, process:str):
        self.process = process
        self.get_db_con()

    def get_db_con(self):
        host = os.getenv("BUSINESS_DB_HOST")
        port = os.getenv("BUSINESS_DB_PORT")
        user = os.getenv("BUSINESS_DB_USER")
        password = os.getenv("BUSINESS_DB_PASSWORD")
        database = os.getenv("BUSINESS_DB_DATABASE")
        self.engine = create_engine(f'postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}')

    def process_codes(self, codes_input:List[str]):
        country = os.getenv("COUNTRY")
        print(process_dict[self.process])     
        sql_query= process_dict[self.process]['sql_query']
        prefix= process_dict[self.process]['prefix']
        df = pd.read_sql_query(sql_query,con=self.engine)
        
        country_mask = df['code'].apply(lambda x: x.split('_')[1] == country)
        df = df.loc[country_mask]
        if isinstance(codes_input,list):
            select_mask = df['code'].isin(codes_input)
            df = df.loc[select_mask]
        if df.empty:
            return

        df['code'] = df['code'].apply(lambda x: "_".join([prefix] + x.split('_')[1:3]))
        df = df.drop_duplicates()
        df['file_path'] = df['code'].apply(lambda x: self._build_base_path(code=x))

        self.robots = df.to_dict(orient='records')

        # codes = [re.sub(r'\s','',code.upper()) for code in codes_input.split(';')]
        # file_paths = [self._build_base_path(code=code) for code in codes]

        # if self._validate_paths(file_paths):
        #     return [{"code":code} for code in codes]

        # messagebox.showerror('Invalid Path', 'One or more file codes do not correspond to valid paths.')
        # return None    

    def _build_base_path(self, code:str)->str:
        
        return os.path.join(self.BASE_PATH,'models',self.process,code)
    
    def create_dags(self):
        dag_template_path = os.path.join(self.BASE_PATH,'include','dag_template.py')
        if not os.path.exists(dag_template_path):
            print(f"There is no template: {dag_template_path}")
        
        for robot in self.robots:
            robot_file_path = os.path.join(self.BASE_PATH, 'dags', self.process, f'{robot['code']}.py')

            os.makedirs(os.path.dirname(robot_file_path), exist_ok=True)
            shutil.copyfile(dag_template_path, robot_file_path)

            template = self.process
            if self.process == 'download':
                template = re.search(r'[(](.*)[)]',robot['download_type'])
                template = "_".join(template.group(1).strip().split('_')[:-1])

            for line in fileinput.input(robot_file_path, inplace=True):
                line = line.replace("dag-id", "'" + robot['code'] + "'")        
                line = line.replace("tagsToReplace", "'" + self.process.capitalize()+ "'")
                line = line.replace("connection-id", "'" + self.DATA_BASE + "'")
                line = line.replace("dag-template", f"{template}_template")
                if self.process == 'download':
                    line = line.replace("#schedule_interval", "schedule_interval")
                    line = line.replace("schedule-to-replace", f"\'{robot['schedule_interval']}\'")
                    print(line, end="")

         
def main():
    

    process = get_choice_process()
    codes = get_second_choose(process=process)
    if not codes:
        info_print("ℹ️Exiting.")
        return
    handler = RobotCodeHandler(process=process)
    handler.process_codes(codes_input=codes)
    handler.create_dags()
    # print(process,codes)


if __name__ == "__main__":
    main()
    # x='D_BO_000000025_02'
    # print(x.split("_")[1:3])