import sys
sys.path.append('d:/DATAX/data-processing-platform')
import unittest
import importlib
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine,inspect,text
from models.conversion.tools.conversion_tools import insert_metadata, verify_values

REPORT_CODE = 'D_PY_000000007_01'
FILE_PATH = r"\\10.0.0.12\downloaded_files\PY\D_PY_000000007\historical data\2014-12-31_indicadores inflacion.pdf"

def get_executor(code):
    db_code = '_'.join(code.split('_')[:-1]).replace('D_','C_')
    module = importlib.import_module(f'models.conversion.{db_code}.{code}')
    class_ = getattr(module, code)    
    return class_()

class TestConversion(unittest.TestCase):

    def setUp(self):
        self.robot = get_executor(REPORT_CODE)
        
        platform_engine = create_engine("postgresql+psycopg2://postgres:datax@10.0.0.12:5432/platform_db")
        report_data = pd.read_sql_query(sql=f'SELECT * FROM report WHERE code = \'{REPORT_CODE}\'',con=platform_engine)
        report_data = report_data.to_dict('records')[0]
        self.report_data = report_data        

        self.replacement_table = report_data['replacement_table'].split(';')
        country_code = REPORT_CODE.split('_')[1]

        engine = create_engine(f"postgresql+psycopg2://postgres:datax@10.0.0.12:5432/DATA_DB_{country_code}_AUX")
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {self.replacement_table[0]}"))
        inspector = inspect(engine)
        self.table_exists = inspector.has_table(self.replacement_table[1], schema=self.replacement_table[0])

        self.engine = engine

    def test_extract(self):
        # Test data extraction
        report_dict,report_df = self.robot.extraction(file_path=FILE_PATH,key_words=self.report_data['key_words'], template_path=self.report_data['converted_report_path'],page_number=self.report_data['page_number'])

        # Validate report_dict structure and content
        expected_report_keys = {'file_name', 'titles', 'page_number'}
        self.assertIsInstance(report_dict, dict, "The first returned element should be a dictionary")
        self.assertSetEqual(
            set(report_dict.keys()), 
            expected_report_keys,
            f"The report information must contain these keys: {expected_report_keys}"
        )

        # Validate file_name
        self.assertIsInstance(report_dict['file_name'], str, "File name should be a string")
        self.assertTrue(len(report_dict['file_name']) > 0, "File name should not be empty")

        # Validate titles
        self.assertIsInstance(report_dict['titles'], list, "Titles should be a list")

        # Validate page number
        self.assertIsInstance(report_dict['page_number'], int, "Page number should be an integer")
        self.assertTrue(report_dict['page_number'] > 0, "Page number should be greater than zero")

        # Validate report DataFrame
        self.assertIsInstance(report_df, pd.DataFrame, "Report should be a DataFrame")
        self.assertFalse(report_df.empty, "DataFrame should not be empty")
        self.assertTrue(len(report_df.columns) > 2, "DataFrame should have more than two columns")

        # Verify DataFrame values
        verify_values(data_df=report_df)

        # Validate date column
        self.assertTrue("fecha", report_df.columns[-2], f"The 'fecha' column must be the second-to-last column in the DataFrame (found: {report_df.columns[-2]}")
        try:
            pd.to_datetime(report_df['fecha'], errors='raise', format='%Y-%m-%d')
        except ValueError as e:
            self.fail(f"Date format validation failed: {str(e)}")

        #* comentar para pruebas intermedias        
        replaces_dict, report_df = self.robot.text_match(df=report_df,db_aux_conn=self.engine,replacement_table_name=self.replacement_table[1],replacement_table_schema=self.replacement_table[0],table_exists=self.table_exists,first_execution=True, dag_run_date= datetime.now())
        #*        

        # Metadata insertion
        final_df = insert_metadata(dataframe=report_df, titles=report_dict['titles'],file_name=report_dict['file_name'])

        # Validate data results
        has_error = self.robot.validate_data_results(
            dataframe=final_df,
            decimal_separator=self.report_data['decimal_separator']
        )
        self.assertFalse(has_error, "Data validation failed - sums should equal zero")

if __name__ == '__main__':
    unittest.main()