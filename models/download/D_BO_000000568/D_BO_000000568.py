import os
import re
import shutil
import zipfile
from datetime import datetime

from openpyxl import load_workbook
from playwright.sync_api import sync_playwright

from models.download.Download_Base import Download_Base
from models.download.tools.download_tools import format_date


class D_BO_000000568(Download_Base):

    def check_new_data(
        self,
        main_url: str,
        updated_to: str,
        path: str,
        key_words: str = None,
        format: str = "%Y-%m-%d",
    ) -> list[dict]:
        """Download all Excel and PDF reports newer than ``updated_to``."""
        del key_words
        report_pattern = re.compile(
            r"TC_(?P<day>\d{2})_(?P<month>\d{2})_"
            r"(?P<year>\d{4})\.(?P<extension>xlsx|pdf)$",
            re.IGNORECASE,
        )
        tmp_dir = os.path.join(path, "tmp")
        try:
            if os.path.isdir(tmp_dir):
                shutil.rmtree(tmp_dir)
            os.makedirs(tmp_dir, exist_ok=True)

            start_date = format_date(updated_to, format)
            if not isinstance(start_date, datetime):
                return []
            today = datetime.now()
            reports = {}
            pages_to_visit = [main_url]
            visited_pages = set()

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page()
                try:
                    while pages_to_visit:
                        page_url = pages_to_visit.pop(0)
                        if page_url in visited_pages:
                            continue
                        visited_pages.add(page_url)
                        page.goto(
                            page_url,
                            wait_until="domcontentloaded",
                            timeout=30_000,
                        )
                        links = page.locator("a[href]").evaluate_all(
                            "anchors => anchors.map(anchor => anchor.href)"
                        )
                        page_dates = []
                        for link in links:
                            clean_link = link.split("?")[0]
                            match = report_pattern.search(clean_link)
                            if match:
                                try:
                                    report_date = datetime(
                                        int(match.group("year")),
                                        int(match.group("month")),
                                        int(match.group("day")),
                                    )
                                except ValueError:
                                    continue
                                page_dates.append(report_date)
                                if start_date < report_date <= today:
                                    extension = match.group("extension").lower()
                                    reports[(report_date, extension)] = link
                        if page_dates and min(page_dates) > start_date:
                            for link in links:
                                if "page=" in link and "compvenmonext" in link:
                                    if link not in visited_pages:
                                        pages_to_visit.append(link)
                finally:
                    browser.close()

                if not reports:
                    return []

                payload = []
                request = playwright.request.new_context()
                try:
                    for (report_date, extension), report_url in sorted(
                        reports.items()
                    ):
                        try:
                            response = request.get(report_url, timeout=30_000)
                            if not response.ok:
                                continue
                            filename = os.path.basename(report_url.split("?")[0])
                            file_path = os.path.join(tmp_dir, filename)
                            with open(file_path, "wb") as report_file:
                                report_file.write(response.body())

                            valid_file = False
                            if extension == "xlsx":
                                try:
                                    workbook = load_workbook(
                                        file_path, read_only=True
                                    )
                                    workbook.close()
                                    valid_file = True
                                except (
                                    OSError,
                                    ValueError,
                                    TypeError,
                                    zipfile.BadZipFile,
                                ):
                                    valid_file = False
                            elif extension == "pdf":
                                try:
                                    with open(file_path, "rb") as report_file:
                                        valid_file = report_file.read(4) == b"%PDF"
                                except OSError:
                                    valid_file = False

                            if not valid_file:
                                os.remove(file_path)
                                continue
                            payload.append(
                                {
                                    "tmp_path": file_path,
                                    "updated_to": report_date.strftime(format),
                                    "download_url": report_url,
                                }
                            )
                        except Exception:
                            continue
                finally:
                    request.dispose()
            return payload
        except Exception as e:
            print(f"Error in check_new_data: {e}")
            return []
