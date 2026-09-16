import sys, os, csv, scrapy
sys.path.append("..")
from bs4 import BeautifulSoup
from scrapy.crawler import CrawlerProcess
from models.download.tools.download_tools import format_date
from models.download.Download_Base import Download_Base

class Spider(scrapy.Spider):
    name = 'D_BO_000000050'

    def __init__(self, start_url=None,path=None, *args, **kwargs):
        super(Spider, self).__init__(*args, **kwargs)
        self.start_urls = start_url
        self.path = path

    def start_requests(self):
        main_url = self.start_urls

        yield scrapy.Request(url=main_url,callback=self.parse_links)

    def parse_links(self, response):
        base_url = 'https://www.investing.com'
        links = response.xpath('//td[@class="bold left noWrap elp plusIconTd"]//a/@href').getall()
        links = [base_url + link for link in links]
        for link in links:
            yield scrapy.Request(url=link, callback=self.parse_historical_link)
    
    def parse_historical_link(self, response):
        base_url = 'https://www.investing.com'
        historical_button = response.css('li[data-test="Historical Data"] > a::attr(href)').get()
        if not historical_button:
            historical_button = response.css('a:contains("Historical Data")').attrib['href']
        historical_link = base_url + historical_button
        yield scrapy.Request(url=historical_link, callback=self.parse_page)
    
    def parse_page(self, response):
        title = response.xpath('//h1/text()').get().replace("/","-")
        print(title)
        rows = response.xpath('//tbody//tr[@class="relative h-[41px] after:absolute after:bottom-0 after:left-0 after:right-0 after:h-px after:bg-[#ECEDEF] hover:bg-[#F5F5F5] historical-data-v2_price__atUfP"]')
        if not rows:
            rows = response.xpath('//table[4]//tbody//tr')

        rows = [row.xpath('./td//text()').getall() for row in rows]

        rows.reverse()
        print(rows[-1])
        
        
        file_name = title + '.csv'
        file_path = os.path.join(self.path, file_name)
        file_exists = os.path.isfile(file_path)
        with open(file_path, mode='w',newline='') as csv_file:
            writer = csv.writer(csv_file)
    
            if not file_exists:
                writer.writerow(["Fecha", "Ultimo", "Apertura", "Maximo", "Minimo", "%var."])
            
            for row in rows:
                writer.writerow(row)

class D_BO_000000050(Download_Base):

    def check_new_data(self, main_url, updated_to,path, format='%Y-%m-%d'):
        # settings = get_project_settings()

        process = CrawlerProcess(settings={
            "ROBOTSTXT_OBEY":True,
            "LOG_FILE": "050.log",
            "LOG_LEVEL":'INFO'
        })

        process.crawl(Spider,start_url=main_url,path=path)

        process.start()             
       

    def compare_files(self, files_paths, updated_to, format='%Y-%m-%d'):
        """
        Compares a list of files with a last file, extracts dates from the new files,
        and filters out the files based on the provided date criteria.

        Parameters:
            files_paths (list): List of dictionaries containing information about files.
            updated_to (str): The latest date for which the database contains records.

        Returns:
            list: List of dictionaries containing information about files that meet the criteria.
        """
        print("Comparing files...")
        # List to store file dictionaries
        files_dicts = []

        # Convert updated_to string to datetime object
        updated_to = format_date(updated_to)

        # Iterate over each file path
        for file in files_paths:
            print(f"Comparing file: {file['tmp_path']}")

# if __name__ == "__main__":
#     robot = D_BO_000000050()
#     # asyncio.run(robot.check_new_data(main_url="https://www.investing.com/commodities/", updated_to="2023-12-21"))
# 
#     x = robot.check_new_data(main_url="https://www.investing.com/indices/world-indices?&majorIndices=on&primarySectors=on&additionalIndices=on&otherIndices=on",updated_to="2023-12-21",path = r"\\10.0.0.9\spim\INVESTING\INDICES SECTORIALES-DIARIOS\robot")
#     print(x)
#     # x = robot.check_new_data1(main_url="https://www.investing.com/rates-bonds/",updated_to="2023-12-21")
#     # print(x)
#     # y = robot.compare_files(files_paths=[{"tmp_path": r"C:\Users\Kevin Padilla\Downloads\01.03.xlsx"}],updated_to="2023-01-21")
#     # print(y)

Executor_D_BO_000000050 = D_BO_000000050
Robot = D_BO_000000050
