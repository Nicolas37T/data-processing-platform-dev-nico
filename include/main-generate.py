import json
import psycopg2
import os
import re
import shutil
import fileinput
import tkinter as tk
from typing import List
from tkinter import simpledialog, messagebox, ttk
from tkinter.messagebox import showinfo, showerror
import pandas as pd


class CustomDialog(simpledialog.Dialog):
    def __init__(self, parent, title=None):
        self.result = None
        self.selection_process = None
        self.selection_robot_type = None
        super().__init__(parent, title)

    def body(self, master):
        tk.Label(master, text="Choose a process:").grid(row=2, column=0, sticky='w')
        self.process_combo = ttk.Combobox(master, values=["download", "conversion", "CODE3"], state="readonly", width=47)
        self.process_combo.grid(row=3, column=0, columnspan=3)
        self.process_combo.bind("<<ComboboxSelected>>", self.update_sub_options)

        self.robot_type_combo_label = tk.Label(master, text="Robot type:")
        self.robot_type_combo = ttk.Combobox(master, state="readonly", width=47)

        tk.Label(master, text="Please enter robot code(s) separated by ';' or a single file code:").grid(row=0, column=0, columnspan=3)
        self.entry = tk.Entry(master, width=50)
        self.entry.grid(row=1, column=0, columnspan=3)
        return self.entry

    def update_sub_options(self, event):
        process = self.process_combo.get()
        self.selection_process = process

        robot_type_option = {
            "download": ["Tipo I (file_download_template)","Tipo II (direct_download_template)","Tipo III (data_download_template)","Tipo IV (multi_file_download_template)"],
            "product": ["Python Product","DBT Product","Star Model Product"],
        }

        self.robot_type_combo['values'] = robot_type_option.get(process,[])
        self.robot_type_combo.set('')

        if self.robot_type_combo['values']:
            self.robot_type_combo_label.grid(row=4, column=0, sticky='w', pady=(10, 0))
            self.robot_type_combo.grid(row=5, column=0, columnspan=3)
        
    def buttonbox(self):
        box = tk.Frame(self)
        tk.Button(box, text="OK", width=10, command=self.ok, default=tk.ACTIVE).grid(row=0, column=0)
        tk.Button(box, text="Cancel", width=10, command=self.cancel).grid(row=0, column=1)
        tk.Button(box, text="All", width=10, command=self.all).grid(row=0, column=2)
        box.pack()

    def all(self):
        self.result = "ALL"
        self.cancel()  # Close the dialog

    def apply(self):
        self.result = self.entry.get().strip()  # Get the value entered by the user

class RobotCodeHandler:
    """Clase encargada de manejar la validación y conversión de códigos de archivo."""
    
    def __init__(self, base_path):
        self.base_path = base_path

    def process_codes(self, codes_input):
        """Procesa la entrada del usuario y genera las rutas de archivo."""
        if not codes_input:
            messagebox.showerror('Invalid Input', 'You must enter something')
            return None

        if codes_input == "ALL":
            #todo DAR SOPORTE CUANDO SE OPRIMA ESTE BOTON
            conexion = psycopg2.connect(
                host="10.0.0.12", #10.0.0.9
                database="platform_db", #downloadDev
                user="postgres",
                password="datax"
            )
            query = "SELECT code FROM report WHERE \"isActive\" = TRUE"
            df = pd.read_sql_query(query,con=conexion)
            robot_codes = set(['_'.join(code.split('_')[:-1]).replace('D_','C_') for code in df['code'].to_list()])
            robot_codes = robot_codes + [code.replace('C_','M_') for code in robot_codes]
            robot_codes = [{"code":re.sub(r'\s','',code.upper())} for code in robot_codes]
            return robot_codes

        codes = [re.sub(r'\s','',code.upper()) for code in codes_input.split(';')]
        file_paths = [self._build_base_path(code=code) for code in codes]

        if self._validate_paths(file_paths):
            return [{"code":code} for code in codes]

        messagebox.showerror('Invalid Path', 'One or more file codes do not correspond to valid paths.')
        return None    

    def _build_base_path(self,code:str)->str:        
        robot_kind = robots_code_dict.get(code[0])
        if not robot_kind:
            os.path.join(self.base_path,'nan')
        return os.path.join(self.base_path,'models',robot_kind,code)

    def _validate_paths(self, paths:List[str])->bool:
        """Valida que todas las rutas existan."""
        return all(os.path.exists(path) for path in paths)

robots_code_dict = {
        'D':'download',
        'C':'conversion',
        'M':'migration'
    }
def ask_robots_code(root):
    robot_code_handler = RobotCodeHandler(base_path=os.getcwd())

    while True:
        dialog = CustomDialog(root, 'Robot Code')
        dialog_result = dialog.result

        if dialog_result is None:
            return []
        processed_codes = robot_code_handler.process_codes(codes_input=dialog_result)

        if processed_codes:
            return processed_codes
        return []

def create_dags(robots_codes):
    DATA_BASE = "platform_db"
    DAG_TEMPLATE='dag_template'
    dag_template_path = os.path.join(os.getcwd(),'include','dag-template',f'{DAG_TEMPLATE}.py')
    if not os.path.exists(dag_template_path):
        print(f"No existe el template en {DAG_TEMPLATE}")
    
    for robot in robot_codes:
        code = robot['code']
        kind_robot = robots_code_dict.get(code[0])
        country = code.split('_')[1]
        new_filename = os.path.join(os.getcwd(),'dags',country,kind_robot,f'{code}.py')
        os.makedirs(os.path.dirname(new_filename), exist_ok=True)
        print(new_filename)
        shutil.copyfile(dag_template_path, new_filename)
        for line in fileinput.input(new_filename, inplace=True):
            line = line.replace("dag-id", "'" + robot['code'] + "'")        
            line = line.replace("tagsToReplace", "'" + kind_robot.capitalize()+ "'")
            line = line.replace("connection-id", "'" + DATA_BASE + "'")
            line = line.replace("dag-template", f"{kind_robot}_template")
            print(line, end="")
    

if __name__=='__main__':
    root = tk.Tk()
    width = 0  # Ancho de la ventana (0 para no mostrar)
    height = 0  # Altura de la ventana (0 para no mostrar)
    screen_width = root.winfo_screenwidth()  # Ancho de la pantalla
    screen_height = root.winfo_screenheight()  # Altura de la pantalla
    x = (screen_width / 2) - (width / 2)  # Coordenada x para centrar la ventana
    y = (screen_height / 2) - (height / 2)  # Coordenada y para centrar la ventana
    root.geometry('%dx%d+%d+%d' % (width, height, x, y))
    root.update_idletasks()

    robot_codes = ask_robots_code(root=root)
    create_dags(robot_codes)
    showinfo("Processing Complete", "The processing of all file codes has been completed successfully.")

    # Destruir la ventana de Tkinter
    root.destroy()
    root.mainloop()
