import os
import shutil
import unittest
import importlib
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine
from urllib.parse import urlparse
from models.download.tools.download_tools import format_date

CODE_ROBOT = 'D_BO_000000270'
UPDATED_TO = '2026-06-30'

def get_executor(code):    
    try:
        module = importlib.import_module(f'models.download.{code}.{code}')
        class_ = getattr(module, code)
    except (ModuleNotFoundError, AttributeError):
        module = importlib.import_module(f'models.download.{code}.Executor_{code}')
        class_ = getattr(module, f'Executor_{code}')
    return class_()

def is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return all([parsed.scheme in ['http', 'https'], parsed.netloc])

class TestDownloadTypeI(unittest.TestCase):

    def setUp(self):
        self.robot = get_executor(CODE_ROBOT)
        
        _host = "10.0.0.16"
        _port = "5434"
        _user = "postgres"
        _password = "datax"


        platform_engine = create_engine(f"postgresql+psycopg2://{_user}:{_password}@{_host}:{_port}/platform_db")
        file_data = pd.read_sql_query(f"SELECT * FROM file WHERE code = '{CODE_ROBOT}';", con=platform_engine)
        file_data = file_data.to_dict('records')[0]
        self.file_data = file_data

        self.file_urls = self.robot.get_file_url(
            main_url=self.file_data['main_url'], 
            updated_to=UPDATED_TO
        )
        path = f"/tmp/{CODE_ROBOT}_test"
        if os.path.exists(path):
            shutil.rmtree(path)
        os.makedirs(path, exist_ok=True)

        self.downloaded_files = self.robot.file_download(urls=self.file_urls, path=path)

    def test_get_file_url(self):        
        self.assertIsInstance(self.file_urls, list, "The result must be a list")
        self.assertTrue(len(self.file_urls) > 0, "At least one file must be scraped")

        for item in self.file_urls:
            self.assertIsInstance(item, str, "Each item must be a URL string")
            self.assertTrue(is_valid_url(item), f"Invalid URL format: {item}")   
    
        updated_to = format_date(UPDATED_TO)
        
        result = self.robot.compare_files(files_paths=self.downloaded_files, updated_to=UPDATED_TO)
        
        self.assertIsInstance(result, list, "The result must be a list")
        self.assertTrue(len(result) > 0, "At least one file must pass the date filter")

        expected_keys = {'tmp_path', 'updated_to', 'download_url'}
        for item in result:
            self.assertIsInstance(item, dict, "Each item must be a dictionary")
            self.assertSetEqual(set(item.keys()), expected_keys, f"Each item must have only {expected_keys} keys")            
            
            result_updated_to = format_date(item['updated_to'])
            self.assertTrue(result_updated_to > updated_to, "The download date must be later than the reference date")

if __name__ == '__main__':
    unittest.main()
