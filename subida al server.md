
C:\Users\Usuario>ssh datax-pds@10.0.0.16
datax-pds@10.0.0.16's password:
Permission denied, please try again.
datax-pds@10.0.0.16's password:
Permission denied, please try again.
datax-pds@10.0.0.16's password:
Welcome to Ubuntu 26.04 LTS (GNU/Linux 7.0.0-30-generic x86_64)

 * Documentation:  https://docs.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/pro

 System information as of Thu Sep 10 09:30:38 AM -04 2026

  System load:  1.92               Temperature:               45.9 C
  Usage of /:   9.5% of 912.81GB   Processes:                 634
  Memory usage: 5%                 Users logged in:           0
  Swap usage:   0%                 IPv4 address for enp132s0: 10.0.0.16

 * Canonical Workshop gives developers fast, composable, reproducible, and
   secure developer environments that are perfect for agentic workflows.

   https://ubuntu.com/workshop

1 device has a firmware upgrade available.
Run `fwupdmgr get-upgrades` for more information.


Expanded Security Maintenance for Applications is not enabled.

65 updates can be applied immediately.
To see these additional updates run: apt list --upgradable

1 additional security update can be applied with ESM Apps.
Learn more about enabling ESM Apps service at https://ubuntu.com/esm


*** System restart required ***

1 device has a firmware upgrade available.
Run `fwupdmgr get-upgrades` for more information.

Web console: https://plat-dev-server:9090/ or https://10.0.0.16:9090/

Last login: Thu Sep 10 08:12:12 2026 from 10.10.20.249
datax-pds@plat-dev-server:~$ ls
CopiaBaseDatos  datax  mongo-panel  yes  yes.pub
datax-pds@plat-dev-server:~$ cd datax/
datax-pds@plat-dev-server:~/datax$ ls
Archivo_Prueba_SSD.xlsx           data-processing-platform-dev   data_migration_db_tool
data-processin-platform-template  data-processing-platform-prod  datax-pipeline-monitor
datax-pds@plat-dev-server:~/datax$ cd data-processing-platform-dev/
datax-pds@plat-dev-server:~/datax/data-processing-platform-dev$ ls
AIRFLOW3_MIGRATION.md  Dockerfile  config  data    docker-compose.yaml  logs    platform_db.backup  requirements.txt
CLAUDE.md              README.md   dags    docker  include              models  plugins
datax-pds@plat-dev-server:~/datax/data-processing-platform-dev$ cd models/
datax-pds@plat-dev-server:~/datax/data-processing-platform-dev/models$ ls
conversion  download  migration  product  tools
datax-pds@plat-dev-server:~/datax/data-processing-platform-dev/models$ cd download/
datax-pds@plat-dev-server:~/datax/data-processing-platform-dev/models/download$ ls
BCRP.py         D_BO_000000250  D_BO_000000419  D_BO_000000484  D_BO_000000489  D_BO_000000572  Download_Base.py  tools
D_BO_000000057  D_BO_000000255  D_BO_000000462  D_BO_000000485  D_BO_000000541  D_BO_000000573  __pycache__
D_BO_000000058  D_BO_000000418  D_BO_000000481  D_BO_000000487  D_BO_000000568  D_BO_000000577  tests
datax-pds@plat-dev-server:~/datax/data-processing-platform-dev/models/download$ sudo mkdir D_BO_000000047
[sudo: authenticate] Password:
datax-pds@plat-dev-server:~/datax/data-processing-platform-dev/models/download$ ls
BCRP.py         D_BO_000000058  D_BO_000000418  D_BO_000000481  D_BO_000000487  D_BO_000000568  D_BO_000000577    tests
D_BO_000000047  D_BO_000000250  D_BO_000000419  D_BO_000000484  D_BO_000000489  D_BO_000000572  Download_Base.py  tools
D_BO_000000057  D_BO_000000255  D_BO_000000462  D_BO_000000485  D_BO_000000541  D_BO_000000573  __pycache__
datax-pds@plat-dev-server:~/datax/data-processing-platform-dev/models/download$ cd D_BO_00000047
-bash: cd: D_BO_00000047: No such file or directory
datax-pds@plat-dev-server:~/datax/data-processing-platform-dev/models/download$ ls
BCRP.py         D_BO_000000058  D_BO_000000418  D_BO_000000481  D_BO_000000487  D_BO_000000568  D_BO_000000577    tests
D_BO_000000047  D_BO_000000250  D_BO_000000419  D_BO_000000484  D_BO_000000489  D_BO_000000572  Download_Base.py  tools
D_BO_000000057  D_BO_000000255  D_BO_000000462  D_BO_000000485  D_BO_000000541  D_BO_000000573  __pycache__
datax-pds@plat-dev-server:~/datax/data-processing-platform-dev/models/download$ cd D_BO_000000047


datax-pds@plat-dev-server:~/datax/data-processing-platform-dev/models/download/D_BO_000000047$ cat D_BO_000000047.py
import sys, traceback
sys.path.append("..")
from playwright.sync_api import sync_playwright
import pandas as pd
from models.download.tools.download_tools import format_date, search_key_words, get_date_method_2,last_day_month
from models.download.Download_Base import Download_Base

class D_BO_000000047(Download_Base):

    def get_file_url(self, main_url, updated_to, format='%Y-%m-%d', key_words="variacion 12 meses"):
        """
        Extracts download URLs for files dated after update_to date.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list: A list of download URLs for files that meet the criteria.
        """

        with sync_playwright() as pl:
            # Convert updated_to string to datetime object
            updated_to = format_date(updated_to)
            # XPath to locate elements
            files_links_xpath = '//div[@class="standard-arrow list-divider bullet-top"]//li'
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch()
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url)

                files_links = page.query_selector_all(files_links_xpath)
                files_link_searched = [link.query_selector(
                    '//a') for link in files_links if search_key_words(text=link.inner_text().lower(),key_word=key_words) ]
                files_link_searched = [link.get_attribute("href") for link in files_link_searched]

                if not len(files_link_searched):
                    print("The searched files were not found")

                print("Found files matching the criteria.")
                return files_link_searched
            except Exception as e:
                print(f"An error ocurred: {e}")
                traceback.print_exc()
                return []
            finally:
                # Close page and browser
                if 'page' in locals():
                    page.close()
                if 'browser' in locals():
                    browser.close()

    def compare_files(self, files_paths, updated_to, format='%Y-%m-%d'):
        """
        Extract the date from a list of files to compare and filter which are more recent than the updated_to date.

        Parameters:
            files_paths (list): List of dictionaries containing information about files.
            updated_to (str): The latest date for which the database contains records.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list or bool: A list of dictionaries with information about files that meet the criteria of being more recent than 'updated_to'. Returns False if no more recent files are found.
        """
        print("Comparing files...")
        # List to store file dictionaries
        files_dicts = []

        # Convert updated_to string to datetime object
        updated_to = format_date(updated_to)

        # Iterate over each file path
        for file in files_paths:
            print(f"Comparing file: {file['tmp_path']}")
            # Extract date from the file
            df_new_file = pd.read_excel(file["tmp_path"])
            print("Extracting date from the file...")
            date = get_date_method_2(dataframe=df_new_file,final_index=10)

            if not date:
                raise NameError("An error occurred while extracting the date")
            month = date[0]
            year = date[1]
            day = last_day_month(year=year, month=month)

            date_formated = format_date(f"{year}-{month}-{day}")

            # Check if the file is newer than the provided date
            if date_formated>updated_to:
                print(f"File date: {date_formated.strftime(format)}. Adding to filtered files.")
                file["updated_to"] = date_formated.strftime(format)
                files_dicts.append(file)

            else:
                print("File does not meet update criteria. Skipping...")

        # Check if any files were found after the updated date
        if not len(files_dicts):
            print(f"There are NO files after {updated_to.strftime(format)}")
            return False
        return files_dicts



# if __name__ == "__main__":
#     robot = D_BO_000000047()
#     # x = robot.get_file_url(main_url="https://www.ine.gob.bo/index.php/estadisticas-economicas/indice-global-de-actividad-economica-igae/#1584545313102-06cf787f-a790",updated_to="2023-12-21")
#     # print(x)
#     y = robot.compare_files(files_paths=[{"tmp_path": r"C:\Users\Kevin Padilla\Downloads\01.03.xlsx"}],updated_to="2023-01-21")
#     print(y)

Executor_D_BO_000000047 = D_BO_000000047
Robot = D_BO_000000047
datax-pds@plat-dev-server:~/datax/data-processing-platform-dev/models/download/D_BO_000000047$ docker compose exec airflow-worker python include/main-generate.py
[INFO] === DAG Generator ===
[INFO] Choose a process to generate DAGs for:
1. Download
2. Conversion
3. Migration
4. Product
5. Cancel
>> 1
[SUCCESS] Selected: DOWNLOAD
[INFO] Selected process: DOWNLOAD
[INFO] Choose an option:
1. Enter robot code(s) separated by ';'
2. Process ALL available robots
3. Cancel
>> 1
Enter code(s):
>> D_BO_000000047
[SUCCESS] Valid codes to be processed: ['D_BO_000000047']
[SUCCESS] Generated: /opt/airflow/dags/download/D_BO_000000047.py
[SUCCESS] Done! 1 DAG(s) generated.
datax-pds@plat-dev-server:~/datax/data-processing-platform-dev/models/download/D_BO_000000047$