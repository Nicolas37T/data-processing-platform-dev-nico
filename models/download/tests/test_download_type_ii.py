import os
import shutil
import unittest
import importlib
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine
from models.download.tools.download_tools import format_date

CODE_ROBOT = 'D_BO_000000550'
UPDATED_TO = '2008-12-31'

def get_executor(code):    
    try:
        module = importlib.import_module(f'models.download.{code}.{code}')
        class_ = getattr(module, code)
    except (ModuleNotFoundError, AttributeError):
        module = importlib.import_module(f'models.download.{code}.Executor_{code}')
        class_ = getattr(module, f'Executor_{code}')
    return class_()

class TestDownloadTypeII(unittest.TestCase):

    def setUp(self):
        self.robot = get_executor(CODE_ROBOT)
        
        _host = os.environ.get("BUSINESS_DB_HOST", "10.0.0.16")
        _port = os.environ.get("BUSINESS_DB_PORT", "5434")
        _user = os.environ.get("BUSINESS_DB_USER", "postgres")
        _password = os.environ.get("BUSINESS_DB_PASSWORD", "datax")

        platform_engine = create_engine(f"postgresql+psycopg2://{_user}:{_password}@{_host}:{_port}/platform_db")
        file_data = pd.read_sql_query(f"SELECT * FROM file WHERE code = '{CODE_ROBOT}';", con=platform_engine)
        file_data = file_data.to_dict('records')[0]
        self.file_data = file_data

        path = f"/tmp/{CODE_ROBOT}_test"
        if os.path.exists(path):
            shutil.rmtree(path)
        os.makedirs(path, exist_ok=True)

        self.files_list = self.robot.verify_download(
            main_url=self.file_data['main_url'],
            updated_to=UPDATED_TO,
            path=path
        )

    def test_verify_download(self):
        self.assertIsInstance(self.files_list, list, "The result must be a list")
        self.assertTrue(len(self.files_list) > 0, "At least one file must be downloaded")

        expected_keys = {'tmp_path', 'download_url'}
        for item in self.files_list:
            self.assertIsInstance(item, dict, "Each item must be a dictionary")
            self.assertSetEqual(set(item.keys()), expected_keys, f"Each item must have only {expected_keys} keys")
            self.assertTrue(os.path.exists(item['tmp_path']), f"The downloaded file must exist: {item['tmp_path']}")

        updated_to = format_date(UPDATED_TO)
        result = self.robot.compare_files(files_paths=self.files_list, updated_to=UPDATED_TO)

        self.assertIsInstance(result, list, "The result must be a list")
        self.assertTrue(len(result) > 0, "At least one file must pass the date filter")

        expected_result_keys = {'tmp_path', 'updated_to', 'download_url'}
        for item in result:
            self.assertIsInstance(item, dict, "Each item must be a dictionary")
            self.assertSetEqual(set(item.keys()), expected_result_keys, f"Each item must have only {expected_result_keys} keys")
            result_updated_to = format_date(item['updated_to'])
            self.assertTrue(result_updated_to > updated_to, "The download date must be later than the reference date")

if __name__ == '__main__':
    unittest.main()
