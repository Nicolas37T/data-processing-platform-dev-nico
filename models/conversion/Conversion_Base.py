import os
import traceback
import re
import csv
import openpyxl
import xlrd
import fitz
import shutil
import sqlite3
import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
from sqlalchemy import MetaData, Table, Column, Integer, String, DateTime
from rapidfuzz import fuzz
from models.conversion.tools.conversion_tools import verify_frecuency, verify_levels, verify_values
from models.download.tools.download_tools import createDirectoryStruct, format_date
from models.conversion.tools.text_normalization import Text_Normalization
    
class Conversion_Base():
    def read_file(self,file_path,path):
        """
        Reads and validates a file based on its extension, and prepares it 
        for further processing by copying it to a temporary directory.

        Parameters:
        - file_path (str): Path to the file to be read.
        - path (str): Base directory path where a temporary folder will be created.

        Returns:
        - str: The path to the copied temporary file.

        Raises:
        - FileNotFoundError: If the file does not exist at the specified path.
        - PermissionError: If the file is not accessible for reading.
        - ValueError: If the file type is not supported.
        """
        # Extract the file name from the path
        file_name = os.path.basename(file_path)        

        # Define the temporary file path
        tmp_file = os.path.join(path, file_name)
        shutil.copy(src=file_path,dst=tmp_file)
        print(f"Copied '{file_path}' to temporary location: '{tmp_file}'.")
        try:
            # Check if the file exists
            if not os.path.exists(tmp_file):
                raise FileNotFoundError(f"The file '{tmp_file}' does not exist.")
            
            # Check if the file is accessible for reading
            if not os.access(tmp_file, os.R_OK):
                raise PermissionError("The file is not accessible for reading.")
            
            # Determine the file extension and validate accordingly
            _, extension = os.path.splitext(tmp_file)
            extension = extension.lower()

            # Validate the file based on its extension
            if extension == '.csv':
                # Validate CSV file by attempting to read it
                with open(file_path, 'r', newline='') as csvfile:
                    csv.reader(csvfile)
                print("CSV file is valid.")
            
            elif extension == '.xlsx':
                # Validate Excel file using openpyxl
                openpyxl.load_workbook(file_path, read_only=True)
                print("XLSX file is valid.")
            
            elif extension == '.xls':
                # Validate older Excel file format using xlrd
                try:
                    xlrd.open_workbook(file_path)
                    print("XLS file is valid.")
                except Exception as e:
                    with open(file_path, 'rb') as f:                        
                        first_bytes = f.read(8)
                    if b'<html' in first_bytes.lower():
                        pd.read_html(file_path)
                        print("HTML file is valid.")
                    elif b'<?xml' in first_bytes.lower():
                        ET.parse(file_path)
                        print("XML file is valid.")
            
            elif extension == '.pdf':
                # Validate PDF file using PyMuPDF (fitz)
                fitz.open(file_path)
                print("PDF file is valid.")
            
            elif extension == '.xml':
                # Validate XML file by parsing it with ElementTree
                ET.parse(file_path)
                print("XML file is valid.")
            else:
                # Raise ValueError for unsupported file types
                raise ValueError(f"File type '{extension}' is not supported.")
            
            print(f"The file: '{tmp_file}' is valid and accessible.")
            return tmp_file
        except FileNotFoundError as e:
            print(f"File not found error: {e}")
        except PermissionError as e:
            print(f"Permission error: {e}")
        except ValueError as e:
            print(f"Unsupported file type error: {e}")
        except Exception as e:            
            print(f"The file is corrupt or invalid: {e}")
        traceback.print_exc()
        return ''
    
    def text_match(self, df:pd.DataFrame,db_aux_conn, replacement_table_name,replacement_table_schema, dag_run_date, table_exists=True, first_execution=False)->pd.DataFrame:
        """
        Normalizes text data in a DataFrame by replacing inconsistent values with standardized ones.
        It uses an auxiliary database table for replacements and updates the table with new replacements if needed.

        Args:
            df (pd.DataFrame): The input DataFrame containing text data to be normalized.
            db_aux_conn: SQLAlchemy connection object to the auxiliary database.
            replacement_table_name (str): Name of the table that stores replacement values.
            replacement_table_schema (str): Schema of the replacement table.
            dag_run_date: The execution date of the DAG (used for timestamping new replacements).
            table_exists (bool, optional): Indicates if the replacement table already exists in the database. Defaults to True.
            first_execution (bool, optional): Flag to indicate if this is the first time the function is being executed. Defaults to False.

        Returns:
            Tuple[dict, pd.DataFrame]: 
                - Dictionary mapping original values to their replacements.
                - The updated DataFrame with normalized text values.
        """

        # Replace multiple spaces with a single space and convert 'nan' strings to actual NaN values
        df = df.replace(r'\s+',' ', regex=True).replace('nan',np.nan)
        
        # Load existing replacements from the auxiliary database if the table exists
        replacement_df = pd.DataFrame()
        if table_exists:
            replacement_df = pd.read_sql_table(table_name=replacement_table_name,con=db_aux_conn,schema=replacement_table_schema)  

        strings = []
        # Identify non-numeric strings in the DataFrame for normalization
        for col in df.columns: 
            column = df.loc[df[col].notna(),col] # Filter out NaN values
            
             # Mask to identify numeric values after removing unnecessary characters
            numeric_mask = pd.to_numeric(column.replace(r'\s+','',regex=True).replace('-','0').apply(lambda x: m if (m:=re.sub(r'[.(),%-]', '', str(x)))!="" else '0'),errors='coerce').notna()
            
            # Collect non-numeric unique strings for potential replacements
            strings_col = column[~numeric_mask].drop_duplicates()            
            if not strings_col.empty:
                strings.append(strings_col)

        # If no strings are found for replacement, return the original DataFrame
        if not strings:
            return ({}, df)
        
        # Combine all non-numeric strings into a single DataFrame
        strings = pd.concat(strings, ignore_index=True).drop_duplicates().reset_index(drop=True)

        try:
             # Get the replacement dictionary and any new replacements from the normalization function
            replaces_dict, new_replacements_df = Text_Normalization.get_replaces(strings_list = strings, replaces_df = replacement_df,first_execution=first_execution)

        except Exception as e:
            traceback.print_exc()
            raise ValueError("There was an error trying to get replaces")
        
        # Apply replacements to the original DataFrame
        if len(replaces_dict) != 0:
            df = df.replace(replaces_dict)            
        
        # If there are new replacements, update the auxiliary database table
        if not new_replacements_df.empty:
            new_replacements_df['created_at'] = dag_run_date
            if not table_exists:
                # Create the replacement table if it doesn't exist
                metadata = MetaData(schema=replacement_table_schema)

                columns = [Column('id',Integer,primary_key=True, autoincrement=True)]
                for col in new_replacements_df.columns[:-1]:
                    columns.append(Column(col, String))
                columns.append(Column(new_replacements_df.columns[-1], DateTime))

                # Create the table schema in the database
                table = Table(replacement_table_name, metadata, *columns)
                metadata.create_all(db_aux_conn)
            
            # Insert new replacements into the table
            new_replacements_df.to_sql(name=replacement_table_name,schema=replacement_table_schema, con=db_aux_conn, if_exists="append", index=False)
            
        return (replaces_dict, df)

    def compare_dates(self,df:pd.DataFrame, converted_to,format='%Y-%m-%d'):
        """
        Compares the latest date in the DataFrame with a specified date.

        Args:
            df (pd.DataFrame): DataFrame containing a 'fecha' column with date values.
            converted_to: The date to compare against. Can be a string or datetime object.
            format (str, optional): The date format for displaying dates in print statements. Defaults to '%Y-%m-%d'.

        Returns:
            str: Returns 'no_updates' if the latest date in the DataFrame is not after the specified date.
            None: Returns None if the latest date is after the specified date.
        """
        # Convert 'converted_to' to datetime if it is a string
        converted_to = format_date(date=converted_to) if isinstance(converted_to,str) else converted_to

        # Process the 'fecha' column:
        # - Replace hyphens with NA
        # - Drop NA values
        # - Convert remaining values to datetime
        # - Sort dates in ascending order
        # - Get unique dates and convert to a list
        data_dates =df['fecha'].replace('-',pd.NA).dropna().apply(lambda x: format_date(str(x))).sort_values(ascending=True).unique().tolist()

        # Get the latest date from the list
        formated_date = data_dates[-1]
        
        # Compare the latest date with the specified date
        if formated_date<=converted_to:
            print(f"The report's date ({formated_date.strftime(format)}) is not after the specified date ({converted_to.strftime(format)}).")
            return 'no_updates'
        
        print(f"Its a new Report, date: ({formated_date.strftime(format)})")
        return

    def structure_review(self,data_file:str,last_conversion_path:str):
        """
        Verifies the structure of a new data file against a previous conversion.

        Args:
            data_file (str): Path to the new data file to be checked.
            last_conversion_path (str): Path to the previous conversion data.

        Returns:
            str: Returns the data file path if the structure is verified successfully, or an empty string if an error occurs.
        """
        try:
            # Load the data into DataFrames
            data_df = self.get_last_conversion_df(last_conversion_path=data_file,table_name=self.__class__.__name__)
            last_conversion_df = self.get_last_conversion_df(last_conversion_path=last_conversion_path)    
            
            # Retrieve the columns from both DataFrames
            last_conversion_cols = last_conversion_df.columns
            data_cols = data_df.columns

            # Filter out columns with 'titulo' in the name from both DataFrames
            last_conversion_cols_without_titles = [col for col in last_conversion_cols if not re.search('titulo',col)]
            data_cols_without_titles = [col for col in data_cols if not re.search('titulo',col)]

            # Compare each column
            for i, template_col in enumerate(last_conversion_cols_without_titles):
                # Use fuzzy matching to compare column names 
                similarity = fuzz.ratio(Text_Normalization.get_srch_value(template_col), Text_Normalization.get_srch_value(data_cols_without_titles[i]))   

                # Raise an error if the similarity between columns is below the acceptable threshold
                if similarity < 90:
                    raise ValueError(f"Column mismatch detected: Template column '{template_col}' does not match New report column '{data_cols_without_titles[i]}'.")
            
            # Update data frame column names to match the template columns
            data_df.columns = last_conversion_cols

            # Verify values in the data frame
            verify_values(data_df=data_df)

            # Verify the columns that need to be reviewed
            columns_to_review_df = self.get_last_conversion_df(last_conversion_path=last_conversion_path, table_name='columns_to_review')
            columns_to_review = columns_to_review_df['column'].unique().tolist()
            
            if not columns_to_review:
                return data_file # Return the data file path if no columns need review
            
            # Filter out date columns from the columns to review
            columns_to_review_without_date = [col for col in columns_to_review if not re.search(r'fecha',col)]

            # If there are columns to review that aren't date-related, verify their levels
            if len(columns_to_review_without_date)>0:
                verify_levels(template_df=last_conversion_df,data_df=data_df, columns_to_review=columns_to_review_without_date)   
            
            # If there are date-related columns, verify the frequency of the data
            if len(columns_to_review) != len(columns_to_review_without_date):
                verify_frecuency(template_df=last_conversion_df,data_df=data_df)
                
            # Return the data file path if the structure verification is successful
            print("Structure verified successfully.")
            return data_file
        
        except ValueError as e:
            print(f"There might be a change in structure: {e}")            
        except Exception as e:
            # Print the error message and traceback if an exception occurs
            print("An error occurred during structure verification")
            traceback.print_exc()            
        return ""

    def report_data_validation(self, code:str, reviewed_files, path:str, publication_frequency:str,last_conversion_path:str, format='%Y-%m-%d', file_extension='sqlite',mongo_client=None, decimal_separator=','):
        """
        Validates and processes report data by checking and saving it into the appropriate format (SQLite, Excel, etc.).

        Args:
            code (str): A unique identifier or code for the report.
            reviewed_files (list): List of dictionaries containing file paths and replacement dictionaries.
            path (str): Directory path to save the processed data.
            publication_frequency (str): The frequency of report publication
            last_conversion_path (str): Path to the previous conversion for reference.
            format (str): Date format to parse the 'fecha' column (default is '%Y-%m-%d').
            file_extension (str): File extension for the output file ('sqlite' or 'xlsx', default is 'sqlite').
            mongo_client (object): MongoDB client to store data in MongoDB (optional).
            decimal_separator (str): Separator for decimals in numbers (default is ',').

        Returns:
            dict: A dictionary containing the path to the processed file, the conversion date, file extension, totals mismatch, and page number.
        """
        
        try:
            # Initialize lists to store DataFrames and replacement data
            dataframes = []
            replaces_dataframes =[]

            # Process each reviewed file
            for f in reviewed_files:
                # Load data from the Excel file
                df = self.get_last_conversion_df(last_conversion_path=f['file_path'],table_name=self.__class__.__name__)
                dataframes.append(df)

                # Load the replacement dictionary into a DataFrame
                df_replaces = pd.DataFrame(f['replaces_dict'].items(), columns=['original_value', 'final_value'])
                replaces_dataframes.append(df_replaces)
            
            # Combine all DataFrames into a single DataFrame
            combined_df = pd.concat(dataframes, ignore_index=True)
            combined_df[combined_df.columns[-1]] = combined_df[combined_df.columns[-1]].astype(str).replace("nan", np.nan)

            # Get the latest date from the 'fecha' column
            date = pd.to_datetime(combined_df['fecha'], format=format,errors='coerce').max()
            date = date.strftime(format)

            # Validate the data results (e.g., totals mismatch)
            result = self.validate_data_results(dataframe=combined_df, decimal_separator=decimal_separator)
            totals_mismatch = result[0] 
            validated_df = result[1]

            # Merge all replacement DataFrames and calculate similarity between the original and final values
            replaces_df_merged = pd.concat(replaces_dataframes, ignore_index=True).drop_duplicates()
            if not replaces_df_merged.empty:
                replaces_df_merged['similarity'] = replaces_df_merged.apply(lambda x: fuzz.ratio(Text_Normalization.get_srch_value(text=x['original_value']), Text_Normalization.get_srch_value(text=x['final_value'])), axis=1)

            # If MongoDB client is provided, insert data into MongoDB
            if mongo_client:
                try:
                    db = mongo_client.get_database()  
                    collection = db[f'raw_{code}']

                    # Convert DataFrame to dictionary and insert into MongoDB
                    mongo_data = combined_df.to_dict(orient='records')
                    collection.insert_many(mongo_data)
                except Exception as e:
                    print('Insert was not done in mongo database')
            
            # Create the directory structure based on the publication date and frequency
            path = createDirectoryStruct(file_date=date,base_path=path,publication_frequency=publication_frequency)
            
            # Define the result file path based on the desired extension
            result_file_path = os.path.join(path, f'{date}_{code}.{file_extension}')

            # Handle file saving based on the selected file extension
            if file_extension == 'sqlite':
                columns_to_review_df = self.get_last_conversion_df(last_conversion_path=last_conversion_path, table_name='columns_to_review')
                
                # Create SQLite connection and save DataFrames to the database
                connection = sqlite3.connect(result_file_path)
                validated_df.to_sql(code, connection, if_exists='replace', index=False)
                replaces_df_merged.to_sql('replaces_table', connection, if_exists='replace', index=False)
                columns_to_review_df.to_sql('columns_to_review', connection, if_exists='replace', index=False)
            
            elif file_extension == 'xlsx':                
                validated_df.to_excel(result_file_path, index=False)

            else:                
                raise ValueError('Unsupported File Format')
            
            #! To supports old fabric
            xlsx_file_path = os.path.join(path, f'{date}_{code}.xlsx')
            validated_df.to_excel(xlsx_file_path, index=False)

            self.store_excel_file(df=replaces_df_merged, file_path=xlsx_file_path, sufix='replaces',file_extension='xlsx')

            print(f"Data successfully saved to SQLite database at: {result_file_path}")
            
            return {
                "conversion_path": result_file_path,
                "converted_to":date,
                "file_extension":file_extension,
                "totals_mismatch": totals_mismatch,
                "page_number": int(reviewed_files[0].get('page_number',0))
                }
        except Exception as e:            
            print(f"An unexpected error occurred: {e}")
            traceback.print_exc()
        
        return ""
    
    def store_excel_file(self, df:pd.DataFrame,file_path:str, sufix='',file_extension='sqlite'):
        """
        Saves a DataFrame as an Excel file in the directory of the input file, 
        generating a new name based on the original name and adding a suffix.

        Args:
            df (pd.DataFrame): The DataFrame to be saved as an Excel file.
            file_path (str): The full path of the input file, used to derive the name and save path.
            sufix (str, optional): A suffix to be added to the file name before the extension (default is '').

        Returns:
            str: The full path of the saved Excel file.
        """
        df[df.columns[-1]] = df[df.columns[-1]].astype(str).replace("nan", np.nan)
        # Get the file name from the full path (without the directory)
        file_name = os.path.basename(file_path)

        # Extract the base name without the file extension
        name = file_name.split('.')[0]

        # Get the directory path where the output file will be saved
        directory_path = os.path.dirname(file_path)

        # Generate the output file path, including the base name, class name, and suffix
        result_file_path = os.path.join(directory_path, f"{name.split('__')[0]}__{self.__class__.__name__}{sufix}.{file_extension}")
        if file_extension == 'sqlite':
            connection = sqlite3.connect(result_file_path)
            df.to_sql(self.__class__.__name__, connection, if_exists='replace', index=False)
        else:
            df.to_excel(result_file_path, index=False)
        return result_file_path
    
    def get_last_conversion_df(self,last_conversion_path:str,table_name=None)->pd.DataFrame:
        """
        Retrieves a DataFrame from the specified conversion file (Excel or SQLite) based on the given table name.
        
        Args:
            last_conversion_path (str): The path to the conversion file (either .xlsx or .sqlite).
            table_name (str, optional): The name of the sheet or table to retrieve. If not provided, defaults to the class name.

        Returns:
            pd.DataFrame: The DataFrame containing the data from the specified sheet/table.
        """
        # Get the file extension from the conversion file path
        last_conversion_extension = os.path.basename(last_conversion_path)
        last_conversion_extension = os.path.splitext(last_conversion_extension)[1]

        # If no table_name is provided, use the class name as the default
        if not table_name:
            table_name = self.__class__.__name__

        # If the file is an Excel file (.xlsx), read the specified sheet
        if re.search(r'xlsx',last_conversion_extension,re.IGNORECASE):
            last_conversion_df = pd.read_excel(last_conversion_path,sheet_name=table_name)
            
        # If the file is a SQLite database, query the specified table
        else:
            with sqlite3.connect(last_conversion_path)as connection:
                query = f"SELECT * FROM {table_name}"
                last_conversion_df = pd.read_sql_query(query,con=connection)
            
        return last_conversion_df