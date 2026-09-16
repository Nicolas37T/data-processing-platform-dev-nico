import sys, re, traceback, requests
sys.path.append("..")
from datetime import datetime
from models.download.tools.download_tools import format_date, month_abr_to_number, month_to_number, last_day_month,text_extract
from models.download.Download_Base import Download_Base

class D_BO_000000262(Download_Base):

    def get_file_url(self, main_url, updated_to,format='%Y-%m-%d'):
        """
        Extracts download URLs for files dated after update_to date.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list: A list of download URLs for files that meet the criteria.
        """        
        # Convert updated_to string to datetime object
        updated_to = format_date(updated_to)
        today = datetime.today()

        re_month = r"((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))"

        files_urls = []

        try:
            # Launch browser and navigate to main URL
            print(f"Launching browser and navigating to {main_url} ...")
            
            # Iterate over each year from updated_to year to the current year
            for year in range(updated_to.year,today.year+1):
                # Construct URL for the given year
                url = f"https://www.aps.gob.bo/?option=com_ajax&module=apsfilesdisplayer&method=getFiles&format=json&folder=webdocs___UNE___DS___Estadisticas___Inversiones___{year}&format=json"

                # Send GET request to the constructed URL
                response = requests.get(url, timeout=10, headers=self.headers)

                data = response.json()
                files = data["data"]["files"]
                for file in files:
                    # Extract month from the filename
                    month = re.search(re_month, file["filename"],re.IGNORECASE).group(1)
                    month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
                    day = last_day_month(year=year,month=month)

                    # Format the date to compare with updated_to
                    date_formated = format_date(f"{year}-{month}-{day}")

                    # If the file date is after updated_to, add to the list
                    if date_formated>updated_to:
                        files_urls.append(file["path"])

            # If no files are found after updated_to    
            if not len(files_urls):
                    print(f"There are NO files after {updated_to.strftime(format)}")
                    return []
                
            print(f"There are {len(files_urls)} files after {updated_to.strftime(format)}")
            return files_urls

        except Exception as e:
            print(f"An error ocurred: {e}")
            traceback.print_exc()
            return []
    
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

        re_date = r'(\d{1,2})\D*((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\D*(\d{4})'
        
        # Iterate over each file path
        for file in files_paths: 

            
            
            print(f"Comparing file: {file['tmp_path']}")
            
            # Extract date from the file
            lines = text_extract(file["tmp_path"])            
           
            dates = [re.search(re_date, line,re.IGNORECASE) for line in lines if re.search(re_date, line,re.IGNORECASE)]
            day, month, year = dates[-1].group(1,2,3)
            month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
            
            date_formated = format_date(f"{year}-{month}-{day}")
            
            # Check if the file is newer than the provided date
            if date_formated>updated_to:
                # Format the update date
                update_to_formatted = date_formated.strftime(format)
                print(f"File date: {update_to_formatted}. Adding to filtered files.")
                file["updated_to"] = update_to_formatted
                files_dicts.append(file)
                
            
            else:
                print("File does not meet update criteria. Skipping...") 

        # Check if any files were found after the updated date
        if not len(files_dicts):
            print(f"There are NO files after {updated_to.strftime(format)}")
            return False
        return files_dicts
    
# if __name__ == "__main__":
#     robot = D_BO_000000262()
#     # x = robot.get_file_url(main_url="http://senamhi.gob.bo/index.php/pcpn",updated_to="2023-5-21")
#     # print(len(x))
#     # print(x)
#     files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"C:\Users\Kevin Padilla\Downloads\Enero.pdf"}]
#     y = robot.compare_files(files_paths=files,updated_to="2023-01-21")
#     print(y)

Executor_D_BO_000000262 = D_BO_000000262
Robot = D_BO_000000262
