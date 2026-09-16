import imaplib
import shutil
import traceback
import re
import os
import time
import email
import zipfile
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date, text_extract
from models.download.Download_Base import Download_Base
from dotenv import load_dotenv

load_dotenv()

class D_BO_000000560(Download_Base):
        
    def get_verification_code_from_email(self, timeout=60):
        """Fetch Microsoft verification code from email inbox."""
        print("[EMAIL] Starting verification code retrieval...")

        mail = imaplib.IMAP4_SSL("mail.datax.com.bo", 993)
        mail.login(self.email_user, self.email_pass)
        mail.select("inbox")

        start_time = time.time()
        since_date = (datetime.now() - timedelta(days=1)).strftime("%d-%b-%Y")

        print(f"[EMAIL] Searching emails since: {since_date}")

        while time.time() - start_time < timeout:
            # Search for unseen emails from Microsoft
            status, search_data = mail.search(None, '(FROM "microsoft" UNSEEN)')
            email_ids = search_data[0].split()

            print(f"[EMAIL] Found {len(email_ids)} unseen Microsoft emails")

            for e_id in reversed(email_ids):  # Process newest first
                print(f"[EMAIL] Processing email ID: {e_id.decode()}")

                _, msg_data = mail.fetch(e_id, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])

                # Extract email body
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/html":
                            body = part.get_payload(decode=True).decode(errors="ignore")
                            break
                else:
                    body = msg.get_payload(decode=True).decode(errors="ignore")

                # Search for verification code (8 digits)
                code_match = re.search(r'\d{8}', body)

                if code_match:
                    code = code_match.group()
                    print(f"[EMAIL] Verification code found: {code}")

                    mail.close()
                    mail.logout()
                    return code

            print("[EMAIL] Code not found yet, retrying in 5 seconds...")
            time.sleep(5)

        mail.close()
        mail.logout()
        raise Exception("[EMAIL] Verification code not found within timeout")


    def verify_download(self, main_url, updated_to, path, format='%Y-%m-%d'):
        """
        Verifies and downloads files newer than a given date.

        Returns:
            list: List of dicts with downloaded file paths.
        """

        print("[INIT] Starting download verification process...")

        # Reset temporary directory
        path = './'
        path = os.path.join(path, 'tmp')

        if os.path.exists(path):
            print(f"[FS] Cleaning existing temp directory: {path}")
            shutil.rmtree(path)

        os.makedirs(path)
        print(f"[FS] Temp directory ready: {path}")

        # Load credentials
        self.email_user = os.getenv("BBV_EMAIL_USER", "")
        self.email_pass = os.getenv("BBV_EMAIL_PASS", "")
        updated_to = format_date(updated_to)

        print(f"[CONFIG] Filtering files newer than: {updated_to}")

        try:
            with sync_playwright() as p:
                print("[BROWSER] Launching browser...")

                browser = p.chromium.launch(headless=False)
                context = browser.new_context()
                page = context.new_page()

                print(f"[NAV] Navigating to: {main_url}")
                page.goto(main_url)

                # Handle email login
                if page.is_visible('#txtTOAAEmail'):
                    print("[AUTH] Email input detected, submitting email...")
                    page.fill('#txtTOAAEmail', self.email_user)
                    page.click('#btnSubmitEmail')

                # Handle password input
                if page.is_visible('input[type="password"]'):
                    print("[AUTH] Please enter your password manually...")
                    input("Press ENTER after entering password...")

                print("[AUTH] Waiting for verification code screen...")
                page.wait_for_selector('.sharing-form', timeout=30000)

                # Retrieve verification code
                code = self.get_verification_code_from_email()

                print("[AUTH] Submitting verification code...")
                page.fill('#txtTOAACode', code)
                page.click('#btnSubmitCode')

                page.wait_for_load_state("networkidle")
                print("[AUTH] Authentication successful")

                print("[FILES] Loading file list...")
                page.wait_for_selector('//div[@role="row"]')

                print("[FILES] Sorting files by modified date (desc)...")
                page.locator('//div[@title="Modified"]').click()
                page.wait_for_timeout(3000)
                page.locator('//button[@data-automationid="sortDesc"]').click()
                page.wait_for_timeout(3000)

                files_list = page.locator('//div[@role="row"]')
                total_files = len(files_list.all())

                print(f"[FILES] Total files detected: {total_files}")

                selected_files = 0

                for file in files_list.all():
                    text = file.inner_text()

                    match = re.search(r"(\d{4})\D(\d{1,2})\D(\d{1,2})", text)
                    if match:
                        file_date = format_date(f"{match.group(1)}-{match.group(2)}-{match.group(3)}")

                        if file_date > updated_to:
                            file.locator('//div[@role="gridcell"]').first.click()
                            selected_files += 1

                print(f"[FILES] Selected {selected_files} files for download")
                if selected_files == 0:
                    return []

                page.wait_for_selector('//button[@data-id="download"]', state='visible')

                print("[DOWNLOAD] Starting download...")
                with page.expect_download(timeout=60000) as download_info:
                    page.locator('//button[@data-id="download"]').click()

                download = download_info.value
                download_path = os.path.join(path, download.suggested_filename)

                print(f"[DOWNLOAD] Saving file to: {download_path}")
                download.save_as(download_path)

                file_paths = []

                # Handle ZIP files
                if download_path.lower().endswith('.zip'):
                    print("[PROCESS] ZIP file detected, extracting...")

                    extract_path = os.path.join(path, "extracted")
                    os.makedirs(extract_path, exist_ok=True)

                    with zipfile.ZipFile(download_path, 'r') as zip_ref:
                        zip_ref.extractall(extract_path)

                    extracted_count = 0
                    for root, _, files in os.walk(extract_path):
                        for f in files:
                            file_paths.append({
                                "download_url": "-",
                                "tmp_path": os.path.join(root, f)
                            })
                            extracted_count += 1

                    print(f"[PROCESS] Extracted {extracted_count} files")

                # Handle PDF files
                elif download_path.lower().endswith('.pdf'):
                    print("[PROCESS] PDF file detected")

                    file_paths.append({
                        "download_url": "-",
                        "tmp_path": download_path
                    })

                print(f"[RESULT] Total files ready: {len(file_paths)}")
                return file_paths

        except Exception as e:
            print(f"[ERROR] An error occurred: {e}")
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
        re_date = r"\b(\d{1,2}/\d{1,2}/\d{4})"

        # Iterate over each file path
        for file in files_paths:
            print(f"Comparing file: {file['tmp_path']}")

            # Extract date from the file
            print("Extracting date from the file...")
            #delete_hidden_sheets(file=file["tmp_path"])
            
            lines = text_extract(file["tmp_path"])
            dates = [re.search(re_date, line) for line in lines if re.search(re_date, line)]
            date = dates[0].group(1)

            date_formated = format_date(date, "%d/%m/%Y")
                
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
#     robot = Executor_D_BO_000000481()
#     x =robot.get_file_url(main_url="https://www.bbv.com.bo/Media/Default/Home/Resumen.pdf",updated_to='2017-05-03')
#     print(len(x))
#     print(x)
#     # files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"/opt/airflow/models/download/D_BO_000000481/Resumen.pdf"}]
    # y = robot.compare_files(files_paths=files,updated_to="2024-08-03")
    # print(y)


Executor_D_BO_000000560 = D_BO_000000560
Robot = D_BO_000000560
