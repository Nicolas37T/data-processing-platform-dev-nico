import sys
sys.path.append('d:/DATAX/data-processing-platform')
import os
import unittest
import importlib
import pandas as pd
from sqlalchemy import create_engine
from models.download.tools.download_tools import format_date

CODE_ROBOT = 'D_BO_000000547'
UPDATED_TO = '2024-05-31'

def get_executor(code):    
    module = importlib.import_module(f'models.download.{code}.Executor_{code}')
    class_ = getattr(module, f'Executor_{code}')    
    return class_()

class TestDownloadTypeIV(unittest.TestCase):

    def setUp(self):
        self.robot = get_executor(CODE_ROBOT)

        _host = os.environ.get("BUSINESS_DB_HOST", "localhost")
        _port = os.environ.get("BUSINESS_DB_PORT", "5432")
        _user = os.environ.get("BUSINESS_DB_USER", "postgres")
        _password = os.environ.get("BUSINESS_DB_PASSWORD", "datax")
        platform_engine = create_engine(f"postgresql+psycopg2://{_user}:{_password}@{_host}:{_port}/platform_db")
        file_data = pd.read_sql_query(F"SELECT * FROM file WHERE code = \'{CODE_ROBOT}\';",con=platform_engine)
        file_data = file_data.to_dict('records')[0]
        self.file_data = file_data

        self.files_path = self.robot.get_data(main_url=self.file_data['main_url'], path=self.file_data['path'], updated_to=UPDATED_TO)

    def test_check_new_data(self): 

        tmp_path = os.path.join(self.file_data['path'],'tmp')
        self.assertEqual(tmp_path,self.files_path, "The result must be a tmp directory inside the main path")
        self.assertTrue(os.path.exists(self.files_path), "The result must exists.")

        list_files = os.listdir(self.files_path)
        self.assertTrue(len(list_files)>0, "At least one file must be downloaded")

        for item in list_files:

            self.assertRegex(item, r'^\d{4}-\d{2}-\d{2}', "Each file must have the date at the start of the name file")
            item_path = os.path.join(self.files_path, item)
            self.assertTrue(os.path.isfile(item_path), "The item must be a file")

if __name__ == '__main__':
    unittest.main()