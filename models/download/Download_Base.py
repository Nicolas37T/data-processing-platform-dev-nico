import requests
import time
import traceback
import os
import sys
import urllib
import mimetypes
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects, RequestException
import shutil
import warnings
from datetime import datetime
from collections import defaultdict
#sys.path.insert(0, '/home/datax/platform_project/models/download/tools')
from models.download.tools.download_tools import createDirectoryStruct, get_proxy, format_date

class Download_Base():
    headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'en-US,en;q=0.9',
            }
    
    def verify_url(self,url, retries=3, wait_time=3, timeout=120, is_download_url=False):
        """
        Check if the main URL is accessible.

        Arguments:
            url (string): URL to verify.
            retries (int): Number of retries.
            wait_time (int): Wait time between retries.
            timeout (int): Request timeout.

        Returns:
            bool: True if reachable, False if not reachable.
        """
        
        # Create a session to maintain state across multiple requests
        session = requests.Session()

        # Create an HTTPAdapter with maximum retries
        adapter = HTTPAdapter(max_retries=retries)

        # Mount the adapter to both HTTP and HTTPS protocols
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        # Iterate over retries
        for _ in range(retries):
            try:
                # Ignore Unverified HTTPS request warning
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    # Send a GET request to the URL with stream=True, timeout, and SSL verification disabled
                    response = session.get(
                        url, stream=True, timeout=timeout, verify=False, headers=self.headers)

                    # If response status code is 403 (Forbidden), try with a random proxy
                    if response.status_code == 403:
                        random_proxy = get_proxy()
                        response = session.get(
                            url,
                            stream=True,
                            timeout=timeout,
                            verify=False,
                            proxies={
                                'http': random_proxy['proxy'],
                                'https': random_proxy['proxy']},
                            headers=self.headers)

                    # Check if the response status code indicates success (2xx range)
                    if 200 <= response.status_code < 300:
                        # Check if the URL is a download URL by inspecting the content-type header
                        if is_download_url:
                            mime_type = mimetypes.guess_extension(response.headers['content-type'])
                            parsed_url = urllib.parse.urlparse(url)
                            file_name = os.path.basename(parsed_url.path)
                            extension = os.path.splitext(file_name)[1]
                            if mime_type or extension:
                                print(f"{response.url} is reachable download url, a succesful response")
                                return True
                            else:
                                print(f"{response.url} is not a download url")
                                return False
                        print(f"{response.url} is reachable, a successful response.")
                        return True
                    else:
                        # Print error message if status code indicates failure
                        print(f"{response.url} is not reachable, status_code: {response.status_code}")
                        return False
            except ConnectionError as e:
                # Handle ConnectionError exception
                print(f"Connection error: {e}")
            except Timeout as e:
                # Handle Timeout exception
                print(f"Timeout error: {e}")
                return False
            except TooManyRedirects as e:
                # Handle TooManyRedirects exception
                print(f"Too many redirects: {e}")
                return False
            except RequestException as e:
                # Handle other RequestException exceptions
                print(f"Request exception: {e}")
                return False

            # If an exception occurred, wait for a specified time before retrying
            print(f"Retrying in {wait_time} seconds...")
            time.sleep(wait_time)

        # Return False if all retries are exhausted
        return False


    def verify_file_url(self,urls, wait_time=3):
        """
        Verifies the availability of file URLs with a specified wait time between verification attempts.

        Args:
            urls (list): List of URLs of the files to be verified.
            wait_time (int, optional): Time to wait between verification attempts. Defaults to 3 seconds.

        Returns:
            list: List of verified URLs.
        """
        verified_urls = []

        # Iterate over each URL in the list
        for url in urls:
            # Verify the URL
            if self.verify_url(url=url,is_download_url=True):
                # If the URL is reachable, add it to the list of verified URLs
                verified_urls.append(url)

            # Wait for the specified time before the next verification attempt
            time.sleep(wait_time)

        # If the list of verified_urls is empty returns NONE
        if not len(verified_urls):
            return False
        return verified_urls


    def file_download(self,urls, path, wait_time=2):
        """
        Downloads a file from the given URL(s) to the specified path and optionally renames it.

        Parameters:
            urls (list of string): List of URLs of the files to be downloaded.
            path (string): Path where the downloaded files will be saved.
            rename (string, optional): Optional new name for the downloaded file(s).

        Returns:
            list: List of dictionaries containing information about files that meet the criteria.
        """
        file_paths = []

        # Ignore Unverified HTTPS request warning
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            # Erase the previous tmp path and create the a new one 
            path = os.path.join(path, 'tmp')
            if os.path.exists(path):
                shutil.rmtree(path)
            os.makedirs(path)

            for url in urls:
                print(f"Downloading: {url} ...")
                # Parse the URL to extract the file name and extension
                parsed_url = urllib.parse.urlparse(url)
                file_name = os.path.basename(parsed_url.path)
                extension = os.path.splitext(file_name)[1]

                # Make a request to the URL
                response = requests.get(url, verify=False, headers=self.headers)

                while response.status_code == 403:
                    random_proxy = get_proxy()
                    response = requests.get(
                        url,
                        verify=False,
                        proxies={
                            'http': random_proxy['proxy'],
                            'https': random_proxy['proxy']},
                        headers=self.headers)

                # If the extension is not provided, try to guess it from the content-type header
                if 200 <= response.status_code < 300:
                    if not extension:
                        extension = mimetypes.guess_extension(response.headers['content-type'])
                        file_name += extension

                    date_now = datetime.now()
                    date_now = date_now.strftime("%Y-%m-%d_%H%M%S")
                    # Combine the file name with the file path
                    file_name = date_now + file_name
                    file_path = os.path.join(path, file_name)

                    # Download the file
                    with open(file_path, "wb") as f:
                        f.write(response.content)

                    # Append the file path to the list
                    file_paths.append({
                        "download_url": url,
                        "tmp_path": file_path})

                    # Wait for the specified time before the next download
                    time.sleep(wait_time)
        
        # If the list of verified_urls is empty returns NONE
        if not len(file_paths):
            print("Could not download any file")
            return False
        return file_paths


    def store_files(self,files_dicts, files_name, publication_frequency, path):
        """
        Store files in a directory structure based on publication date.

        Parameters:
            files_dicts (list): List of dictionaries with paths and dates of all files to be stored
            files_names (str): Name of all the historic files.
            publication_frequency (str): Frecuency of publication of the files (diario, semanal, mensual, trimestral, semestral, anual).
            path (str): Base path where the files will be stored.

        Returns:
            files_dicts (list): List of dictionaries adding the final path of the file
        """
        files_dicts_ = []
        files_dicts_to_be_stored =[]
        for file in files_dicts:
            # Get the file extension
            extension = os.path.splitext(file["tmp_path"])[1]

            # Create directory structure for the new file location
            new_file_path = createDirectoryStruct(
                file_date=file["updated_to"],
                base_path=path,
                publication_frequency=publication_frequency)
            # If it has a compress file copy it into location
            if "zip_path" in file:
                
                compress_extension = os.path.splitext(file["zip_path"])[1]
                new_zip_path = os.path.join(new_file_path, f"{file['updated_to']}_{files_name}{compress_extension}")
                shutil.copy(file["zip_path"], new_zip_path)
                zip_element = {
                    "updated_to": file["updated_to"],
                    "datax_file_path": new_zip_path,
                    "download_url": file["download_url"]
                }
                file["zip_path"] = new_zip_path
                files_dicts_.append(zip_element)
            # Create the full path for the new file location
            new_file_path = os.path.join(new_file_path, f"{file['updated_to']}_{files_name}{extension}")
            file["datax_file_path"] = new_file_path
            
            # Copy the file to the new location
            shutil.copy(file["tmp_path"], new_file_path)
            files_dicts_.append(file)

        # Erase the previous tmp path to save space
        # tmp_path = os.path.join(path, 'tmp')
        # if os.path.exists(tmp_path):
        #     shutil.rmtree(tmp_path)
        
        dates = set([file["updated_to"] for file in files_dicts_])
        for date in dates:
            element = {}
            files = [file for file in files_dicts_ if file["updated_to"] == date]
            
            element["updated_to"] = date
            if len(files)>1:
                element["download_url"] = ";".join([file["download_url"] for file in files if "download_url" in file])  
            else: 
                element["download_url"] = files[0]["download_url"] if "download_url" in files[0] else ''
            element["datax_file_path"] = ";".join([file["datax_file_path"] for file in files]) if len(files)>1 else files[0]["datax_file_path"]
            files_dicts_to_be_stored.append(element)

        return sorted(files_dicts_to_be_stored, key=lambda x: x["updated_to"])

    def store_new_data(self, path, tmp_path,last_file_path, ALL=False,format='%Y-%m-%d'):
        """
        Store new data files by comparing with existing files.

        Parameters:
        path (str): Base path for the new data files.
        tmp_path(str): Path when the temporary files were downloaded
        last_file_path (str): Path to the directory containing the last set of files.
        format (str): Date format used in the file names. Default is '%Y-%m-%d'.
        ALL(bool): Boolean variable to decide if the files we are going to be compared or not

        Returns:
        list: A list of dictionaries containing the download URL, the date to which data is updated, and the file path.
        """
        try:
            print("Starting the process of storing new data files...")
            files_to_store = []
            if ALL:
                files_to_store = os.listdir(tmp_path)
                
            elif not last_file_path or not os.path.exists(last_file_path):
                # No previous download path — treat as first run, store everything
                files_to_store = os.listdir(tmp_path)
            else:
                # Get list of last files and group them by file code
                last_files = os.listdir(last_file_path)
                last_files_dict = defaultdict(list)
                for f in last_files:
                    f_name = os.path.splitext(f)[0]
                    f_code = f_name[10:]
                    last_files_dict[f_code].append(f) 

                # Process new files in the temporary directory
                for file in os.listdir(tmp_path):
                    file_name = os.path.splitext(file)[0]
                    file_date = format_date(file_name[:10])
                    file_code = file_name[10:]

                    # Retrieve last files with the same file code
                    last_file = last_files_dict.get(file_code, [])
                    if not last_file:
                        files_to_store.append(file)
                        continue

                    # Check if the current file is not the latest
                    is_latest = any(file_date <= format_date(os.path.splitext(f)[0][:10]) for f in last_file)
                    if not is_latest:
                        files_to_store.append(file)
                        continue
            
            # If no new files to store, return an empty list
            if not files_to_store:
                print("There is no new data to store.")
                return[]
            
            # Determine the latest date from the new files to store
            if ALL:
                last_date = datetime.today().strftime(format=format)
            else:
                last_date = max(files_to_store)[:10]

             # Create directory structure for the new files
            new_file_path = createDirectoryStruct(
                file_date=last_date,
                base_path=path,
                publication_frequency="diario"
            )
            new_file_path = os.path.join(new_file_path,last_date)
            if not os.path.exists(new_file_path):
                os.makedirs(new_file_path)
            
            # Copy new files to the new directory
            for file in files_to_store:
                src_path = os.path.join(tmp_path,file)
                dest_path = os.path.join(new_file_path,file)
                if os.path.isfile(src_path):
                    shutil.copy(src_path,dest_path)
                elif os.path.isdir(src_path):
                    for index,f in enumerate(os.listdir(src_path)):
                        shutil.copy(os.path.join(src_path,f),f"{dest_path}_dirfile{index}")
                else:
                    raise ValueError(f"There is an error with the file: {file}")
            print(f"There are {len(files_to_store)} new files stored successfully.")

            return [{
                "download_url": "-",
                "updated_to": last_date,
                "datax_file_path": new_file_path
            }]
        
        except Exception as e:
            print(f"An error ocurred: {e}")
            traceback.print_exc()
            return []