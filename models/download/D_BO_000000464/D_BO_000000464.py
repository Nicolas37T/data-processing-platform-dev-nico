import traceback
import requests
import os
import shutil
from models.download.Download_Base import Download_Base

class D_BO_000000464(Download_Base):

    def get_data(self, main_url, path, updated_to,format='%Y-%m-%d'):
        """
        Extracts data from URLs for files dated in the present year.

        Parameters:
            main_url (str): The URL of the main page.
            path (str): The path where files are stored.
            updated_to (str): The latest date for which the database contains records.
            format (str): The date format to use for the 'updated_to' field.

        Returns:
            str: A temporary path where the files were stored or an empty string if there are no files downloaded. 
        """
        codes_dicts = {
            "212":"2.2.1.01",
            "31808":"2.2.1.07",
            "31809":"2.2.1.06",
            "31807":"2.2.1.05",
            "31806":"2.2.1.04",
            "211":"2.2.1.02"
        }

        # Create the temporary directory to save files
        new_file_path = os.path.join(path, 'tmp')
        if os.path.exists(new_file_path):
            shutil.rmtree(new_file_path)
        os.makedirs(new_file_path)

        file_paths = []
        try:
            # Define constants for API interaction
            CODE_INDICATOR = 2050
            YEAR_ID = 29117
            DIMS_ID = 1272

            # Launch browser and navigate to main URL
            print(f"Launching browser and navigating to {main_url} ...")

            # Send GET request main URL
            response = requests.get(main_url, timeout=10, headers=self.headers)
            main_url_data = response.json()

            # Filter data for the specific indicator
            indicator_data = [item for item in main_url_data['body']['updates'] if item["id"]==CODE_INDICATOR]
            if not indicator_data:
                raise Exception("The indicator does not exist")
            
            indicator_date = indicator_data[0]["updated"]

            # Construct dimensions URL and get dimensions data
            dims_url = f"https://api-cepalstat.cepal.org/cepalstat/api/v1/indicator/{CODE_INDICATOR}/dimensions?lang=es&format=json&in=1"
            dims_response =requests.get(dims_url, timeout=10, headers=self.headers)
            dims_data = dims_response.json()
            
            # Extract relevant dimensions
            dimensions = [item for item in dims_data['body']['dimensions'] if item['id'] in [YEAR_ID,DIMS_ID]]
            dimensions = [item["members"] for item in dimensions]
            dimensions = [str(item['id']) for sublist in dimensions for item in sublist]

            # Loop through codes and construct the data URL for each
            for key in dict.keys(codes_dicts):
                url = f"https://api-cepalstat.cepal.org/cepalstat/api/v1/indicator/{CODE_INDICATOR}/data?members={key}%2C{'%2C'.join(dimensions)}&lang=es&format=excel&in=1&app=dashboard"
                response = requests.get(url, timeout=10, headers=self.headers)
                if 200 <= response.status_code < 300:
                    file_name = f"{indicator_date}_{codes_dicts[key]}.xlsx"
                    file_path = os.path.join(new_file_path, file_name)

                    # Download the file
                    with open(file_path, "wb") as f:
                        f.write(response.content)
                    file_paths.append(file_path)

            # If the list of verified_urls is empty returns NONE
            if not len(file_paths):
                print("Could not download any file")
                return ""
            return new_file_path
        
        except Exception as e:
            print(f"An error ocurred: {e}")
            traceback.print_exc()
            return ""
        
if __name__ == "__main__":
    robot = Executor_D_BO_000000464()
    x =robot.get_data(main_url="https://api-cepalstat.cepal.org/cepalstat/api/v1/portal/cepalstat/updates?top=1000&app=portal&lang=es",path=r"/opt/airflow/models/download/D_BO_000000464")
    print(len(x))
    print(x)
    # files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"/opt/airflow/dags/models/download/D_BO_000000463/RIN_BCB_abr-24.pdf"}]
    # y = robot.compare_files(files_paths=files,updated_to="2024-01-21")
    # print(y)



Executor_D_BO_000000464 = D_BO_000000464
Robot = D_BO_000000464
