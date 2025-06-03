import os
import shutil
import requests
import time
import pandas as pd
from datetime import datetime, timedelta
from models.download.tools.download_tools import format_date, month_abr_to_number
from models.download.Download_Base import Download_Base

class BCRP(Download_Base):

    def main_check_new_data(self, series_list, main_url, updated_to, path, key_words, format='%Y-%m-%d'):
        """
        Extracts data from the main_url dated after update_to date.

        Parameters:
            series_list (list): List of series codes to include in the request.
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            path (str): The directory path to store temporary files.
            key_words (str): A string used to name the CSV file.
            format (str): The format of the dates. Default is '%Y-%m-%d'.

        Returns:
            list: A list of dictionaries containing information about the extracted data.
        """
        batch_size = 6
        # Convert updated_to from string to datetime object
        updated_to = format_date(updated_to)
        
        now = datetime.now()
        from_date = now - timedelta(days=7)        
        if updated_to>=now:
          print(f"No new data after:{updated_to.strftime(format)}")
          return []

        # Prepare temporary path
        path = os.path.join(path, 'tmp')
        if os.path.exists(path):
            shutil.rmtree(path)
        os.makedirs(path)

        # Construct API URL
        dataframes = []
        for i in range(0,len(series_list),batch_size):
            batch = series_list[i:i+batch_size]
            url = f'https://estadisticas.bcrp.gob.pe/estadisticas/series/api/{"-".join(batch)}/json/{from_date.strftime(format)}/{now.strftime(format)}'
            retries = 5       
            
            response = None
            for _ in range(retries):
                response = requests.get(url)
                if 300>response.status_code>=200:
                    break
                time.sleep(2)
            
            if not response:
                print(f"Failed to get a valid response after {retries} retries.")
                return []
            
            # Try to parse JSON response
            try:
                data = response.json()
            except Exception as e:
                print(f"There are not files after:{updated_to.strftime(format)}")
                return []
            
            # Extract column names from the response
            columns = ['fecha'] + [item['name'] for item in data['config']['series']]

            # Extract rows (periods)
            rows = [[item['name']] + item['values'] for item in data['periods']]
            print(f"Extracted {len(rows)} rows from response.")
            
            # Create DataFrame
            df = pd.DataFrame(data=rows, columns=columns)

            # Format 'fecha' column from 'dd.mmm.yy' to 'yyyy-mm-dd'
            df['fecha'] = df['fecha'].apply(
                lambda x: (
                    items:=str(x).split("."),
                    f'{"19" if int(items[2])>int(str(now.year)[2:]) else "20"}{items[2]}-{month_abr_to_number(items[1].lower())}-{items[0]}'
                )[1]
            )
            # Insert title column
            df = df.set_index('fecha')

            dataframes.append(df)
        final_df = pd.concat(dataframes,axis=1)
        final_df = final_df.reset_index()
        final_df.insert(0,column="titulo1", value=data['config']['title'])
        

        file_date = format_date(max(final_df['fecha']))
        if file_date<=updated_to:
            print(f"No new data after:{updated_to.strftime(format)}")
            return []

        # Save to Excel
        file_path = os.path.join(path,f"{key_words}.xlsx")
        final_df.to_excel(file_path, index=False)
        print(f"Data saved to {file_path}")

        return [{
            "tmp_path":file_path,
            "updated_to":max(final_df['fecha']),
            "download_url":'-',
        }]
        