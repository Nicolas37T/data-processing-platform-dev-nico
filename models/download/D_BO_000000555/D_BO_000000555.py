import os
import shutil
import json
from playwright.sync_api import sync_playwright
import time
import random
import re
import unicodedata
import traceback
from datetime import date
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side
from models.download.Download_Base import Download_Base

def human_delay():
    delay = random.lognormvariate(0.5, 0.75)  # distribuci�n m�s natural
    delay = min(delay, 8)  # evitar delays absurdos
    time.sleep(delay)

def has_products_data(response):
    """Checks that the GraphQL response actually contains getProductsByCategory data (some category references return HTTP 200 with data: null, e.g. 'categoryPath not found')."""
    return bool(response) and bool(response[0].get("data")) and bool(response[0]["data"].get("getProductsByCategory"))

class D_BO_000000555(Download_Base):
	def check_new_data(self, main_url, updated_to, path, key_words, format = "%Y-%m-%d"):  
		"""
		Extracts data from the main_url dated after update_to date.

		Parameters:
			main_url (str): The URL of the main page.
			updated_to (str): The latest date for which the database contains records.
			path (str): The directory path to store temporary files.
			key_words (str): A string used to name the CSV file.
			format (str): The format of the dates. Default is '%Y-%m-%d'.

		Returns:
			list: A list of dictionaries containing information about the extracted data.
		"""                  
		try:

			list_files=[]
			cod_ref=[]
			product_by_cat = [] 
			total_product_web = 0
			obtained_products_count=0

			# Erase the previous tmp path and create the a new one        
			path_tmp = os.path.join(path, "tmp")

			# Verifed if the folder exist else delete it to create of new
			if os.path.exists(path_tmp):
				shutil.rmtree(path_tmp)
			os.makedirs(path_tmp)            
			
			playwright_ctx = sync_playwright().start()
			browser = playwright_ctx.chromium.launch(headless=True)
			context = browser.new_context(
				user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36',
				extra_http_headers={
					'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
					'Accept-Encoding': 'gzip, deflate, br',
					'Accept-Language': 'en-US,en;q=0.9',
				}
			)
			page = context.new_page()
			first_response = page.goto('https://www.farmaciaschavez.com.bo/')
			print(first_response.status if first_response else 'No status')

			def pw_post(url, payload):
				"""Performs a POST request via playwright's page.evaluate fetch."""
				result = page.evaluate("""
					([url, payload]) => fetch(url, {
						method: 'POST',
						headers: {
							'Content-Type': 'application/json',
							'Origin': 'https://www.farmaciaschavez.com.bo',
							'Referer': 'https://www.farmaciaschavez.com.bo/'
						},
						body: JSON.stringify(payload)
					}).then(r => r.json())
				""", [url, payload])
				return result
			
			# Payload of full-level routes
			payload_get_category_tree =[
				{
					"operationName": "GetCategoryTree",
					"variables": {
					"getCategoryInput": {
						"clientId": "FARMACIAS_CHAVEZ",
						"storeReference": "5406"
					}
					},
					"query": "fragment CategoryFields on CategoryModel {\n  active\n  boost\n  hasChildren\n  categoryNamesPath\n  isAvailableInHome\n  level\n  name\n  path\n  reference\n  slug\n  photoUrl\n  imageUrl\n  shortName\n  isFeatured\n  isAssociatedToCatalog\n  __typename\n}\n\nfragment CategoriesRecursive on CategoryModel {\n  subCategories {\n    ...CategoryFields\n    subCategories {\n      ...CategoryFields\n      subCategories {\n        ...CategoryFields\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\n\nfragment CategoryModel on CategoryModel {\n  ...CategoryFields\n  ...CategoriesRecursive\n  __typename\n}\n\nquery GetCategoryTree($getCategoryInput: GetCategoryInput!) {\n  getCategory(getCategoryInput: $getCategoryInput) {\n    ...CategoryModel\n    __typename\n  }\n}"
				}
			]

			# Send an HTTP POST request to the main URL with the payload as JSON via Playwright
			data_category_tree = pw_post(main_url, payload_get_category_tree)
			print("Category tree fetched successfully")

			# The categories are obtaine
			categories = data_category_tree[0].get("data", {}).get("getCategory", [])
			
			# The levels of each category are extracted: level 1, level 2, and level 3
			for level_1 in categories:
				if level_1.get("level")==1 and not level_1.get("subCategories"):
					cod_ref.append(
						{
							"reference":level_1.get("reference"),
							"level_1": level_1.get("name"),
							"level_2": None,
							"level_3": None
						}
					)
				else:            
					sub1 = level_1.get("subCategories")                            
					name_lv1 = level_1.get("name")
					for level_2 in sub1:
						sub2 = level_2.get("subCategories")    
						name_lv2 = level_2.get("name")    
						for nivel3 in sub2:
							if nivel3.get("level") == 3:
								name_lv3 = nivel3.get("name")                                                                                             
								cod_ref.append(
									{
										"reference":nivel3.get("reference"),
										"level_1": name_lv1,                                    
										"level_2": name_lv2,
										"level_3": name_lv3
									}
								)                               
			print("Extracting the levels or categories...")
			print(f"There are a total of {len(cod_ref)} level paths.")

			# Each category is traversed based on its levels to extract product information
			for path_level in cod_ref:   

				payload_products_by_category= [
					{
						"operationName": "GetProductsByCategory",
						"variables": {
							"getProductsByCategoryInput": {                                                        
								"categoryReference": path_level.get("reference"),
								"categoryId": None,
								"clientId": "FARMACIAS_CHAVEZ",                
								"storeReference": "5429",
								"currentPage": 1,
								"pageSize": 100,
								"filters": {},
								"googleAnalyticsSessionId": "34930170-012c-4afa-b2f3-57da26d34657"
							}
						},
						"query": "fragment CategoryFields on CategoryModel {\n  active\n  boost\n  hasChildren\n  categoryNamesPath\n  isAvailableInHome\n  level\n  name\n  path\n  reference\n  slug\n  photoUrl\n  imageUrl\n  shortName\n  isFeatured\n  isAssociatedToCatalog\n  __typename\n}\n\nfragment CatalogProductTagModel on CatalogProductTagModel {\n  description\n  enabled\n  textColor\n  filter\n  tagReference\n  backgroundColor\n  name\n  __typename\n}\n\nfragment CatalogProductFormatModel on CatalogProductFormatModel {\n  format\n  equivalence\n  unitEquivalence\n  clickMultiplier\n  minQty\n  maxQty\n  __typename\n}\n\nfragment Taxes on ProductTaxModel {\n  taxId\n  taxName\n  taxType\n  taxValue\n  taxSubTotal\n  __typename\n}\n\nfragment PromotionCondition on PromotionCondition {\n  quantity\n  price\n  priceBeforeTaxes\n  taxTotal\n  taxes {\n    ...Taxes\n    __typename\n  }\n  __typename\n}\n\nfragment Promotion on Promotion {\n  type\n  isActive\n  conditions {\n    ...PromotionCondition\n    __typename\n  }\n  description\n  endDateTime\n  startDateTime\n  __typename\n}\n\nfragment PromotedModel on PromotedModel {\n  isPromoted\n  onLoadBeacon\n  onClickBeacon\n  onViewBeacon\n  onBasketChangeBeacon\n  onWishlistBeacon\n  __typename\n}\n\nfragment SpecificationModel on SpecificationModel {\n  title\n  values {\n    label\n    value\n    __typename\n  }\n  __typename\n}\n\nfragment NutritionalDetailsInformation on NutritionalDetailsInformation {\n  servingName\n  servingSize\n  servingUnit\n  servingsPerPortion\n  nutritionalTable {\n    nutrientName\n    quantity\n    unit\n    quantityPerPortion\n    dailyValue\n    __typename\n  }\n  bottomInfo\n  __typename\n}\n\nfragment Promotions on PromotionV2 {\n  type\n  description\n  promotionReference\n  startDateTime\n  endDateTime\n  isActive\n  conditions {\n    field\n    operator\n    values\n    value\n    __typename\n  }\n  benefit {\n    type\n    label\n    value\n    values\n    imagesURL\n    __typename\n  }\n  __typename\n}\n\nfragment CatalogProductModel on CatalogProductModel {\n  name\n  price\n  photosUrl\n  unit\n  subUnit\n  subQty\n  description\n  sku\n  ean\n  maxQty\n  minQty\n  clickMultiplier\n  nutritionalDetails\n  isActive\n  slug\n  brand\n  stock\n  securityStock\n  boost\n  isAvailable\n  location\n  priceBeforeTaxes\n  taxTotal\n  promotion {\n    ...Promotion\n    __typename\n  }\n  taxes {\n    ...Taxes\n    __typename\n  }\n  categories {\n    ...CategoryFields\n    __typename\n  }\n  categoriesData {\n    ...CategoryFields\n    __typename\n  }\n  formats {\n    ...CatalogProductFormatModel\n    __typename\n  }\n  tags {\n    ...CatalogProductTagModel\n    __typename\n  }\n  specifications {\n    ...SpecificationModel\n    __typename\n  }\n  promoted {\n    ...PromotedModel\n    __typename\n  }\n  score\n  relatedProducts\n  ingredients\n  stockWarning\n  nutritionalDetailsInformation {\n    ...NutritionalDetailsInformation\n    __typename\n  }\n  productVariants\n  isVariant\n  isDominant\n  promotions {\n    ...Promotions\n    __typename\n  }\n  seals\n  previousPrice\n  previousPricePerSubUnit\n  pricePerSubUnit\n  hasAgeRestriction\n  type\n  __typename\n}\n\nfragment CategoryWithProductsModel on CategoryWithProductsModel {\n  name\n  reference\n  level\n  path\n  hasChildren\n  active\n  boost\n  isAvailableInHome\n  slug\n  photoUrl\n  categoryNamesPath\n  imageUrl\n  shortName\n  isFeatured\n  products {\n    ...CatalogProductModel\n    __typename\n  }\n  hasAgeRestriction\n  __typename\n}\n\nfragment PaginationTotalModel on PaginationTotalModel {\n  value\n  relation\n  __typename\n}\n\nfragment PaginationModel on PaginationModel {\n  page\n  pages\n  total {\n    ...PaginationTotalModel\n    __typename\n  }\n  __typename\n}\n\nfragment AggregateBucketModel on AggregateBucketModel {\n  min\n  max\n  key\n  docCount\n  __typename\n}\n\nfragment AggregateModel on AggregateModel {\n  name\n  docCount\n  buckets {\n    ...AggregateBucketModel\n    __typename\n  }\n  __typename\n}\n\nfragment BannerModel on BannerModel {\n  id\n  storeId\n  title\n  desktopImage\n  mobileImage\n  targetUrl\n  targetUrlInfo {\n    type\n    url\n    __typename\n  }\n  targetCategory\n  index\n  categoryId\n  __typename\n}\n\nfragment CarouselModel on CarouselModel {\n  id\n  name\n  autoplaySpeed\n  lazyLoading\n  isActive\n  createdAt\n  updatedAt\n  banners {\n    id\n    name\n    webImageUrl\n    tabletImageUrl\n    appImageUrl\n    redirectUrl\n    redirectMode\n    isActive\n    __typename\n  }\n  position\n  __typename\n}\n\nquery GetProductsByCategory($getProductsByCategoryInput: GetProductsByCategoryInput!) {\n  getProductsByCategory(getProductsByCategoryInput: $getProductsByCategoryInput) {\n    category {\n      ...CategoryWithProductsModel\n      __typename\n    }\n    pagination {\n      ...PaginationModel\n      __typename\n    }\n    aggregates {\n      ...AggregateModel\n      __typename\n    }\n    carousels {\n      ...CarouselModel\n      __typename\n    }\n    banners {\n      ...BannerModel\n      __typename\n    }\n    promoted {\n      ...PromotedModel\n      __typename\n    }\n    __typename\n  }\n}"
					}
				]

				# Send an HTTP POST request and verify that the server response is successful
				try:                    
					data_products_by_category = pw_post(main_url, payload_products_by_category)

					if not data_products_by_category:
						# Retry a second time if no data is obtained
						try:
							print("Retrying...")
							time.sleep(60)
							data_products_by_category = pw_post(main_url, payload_products_by_category)
						except Exception as es_1:
							print("error: ", es_1)
							print("Retry failed after waiting 60 seconds.")

				# If the request fails, perform a second retry
				except Exception as e:

					print(f"Connection error: {e}")
					try: 

						print("First attempt failed:", e)
						print("Retrying once more...\n")
						time.sleep(60)
						data_products_by_category = pw_post(main_url, payload_products_by_category)

					except Exception as es2:

						print("The second attempt has failed as well. Error:", es2)
				human_delay()

				# If no valid data was obtained after the retries, skip this category
				if not has_products_data(data_products_by_category):
					print(f"No data obtained for category '{path_level.get('reference')}' after retries. Skipping category...")
					continue

				# The total and actual quantity of products present on the website is obtained
				total_product_by_cat = data_products_by_category[0]["data"]["getProductsByCategory"]["pagination"]["total"]["value"]
				total_product_web = total_product_web + total_product_by_cat

				# All products are obtained based on the category
				products = data_products_by_category[0]["data"]["getProductsByCategory"]["category"]["products"]

				# Information is extracted from each product in the first pagination batch of 100 products.
									
				for product in products:                

					# The discounted price is extracted
					if product["promotion"] is None:
						discount_price = product["promotion"] #None default                                                    
					else:
						discount_price = product["promotion"]["conditions"][0]["price"]

					# The data is stored in an array of products
					product_by_cat.append(
						{
							"level_1": path_level["level_1"],
							"level_2": path_level["level_2"],
							"level_3": path_level["level_3"],
							"name_prod": product["name"],
							"sku":product["sku"],
							"unit": product["unit"],
							"price": product["price"],
							"discount_price": discount_price,
							"description": product["description"],
							"brand": product["brand"],
							"stock": product["stock"],
							"isAvailable": product["isAvailable"],                                                    
						}
					)
					obtained_products_count =  obtained_products_count + 1
					print(f"product {obtained_products_count} obtained")
								
				# Information is extracted from the second product pagination up to the total number of existing pages
				page_nums = data_products_by_category[0]["data"]["getProductsByCategory"]["pagination"]["pages"]
				current_page = 2
				while current_page <= page_nums:
					payload_products_by_category= [
						{
							"operationName": "GetProductsByCategory",
							"variables": {
								"getProductsByCategoryInput": {                                                        
									"categoryReference": path_level.get("reference"),
									"categoryId": None,
									"clientId": "FARMACIAS_CHAVEZ",                
									"storeReference": "5429",
									"currentPage": current_page,
									"pageSize": 100,
									"filters": {},
									"googleAnalyticsSessionId": "34930170-012c-4afa-b2f3-57da26d34657"
								}
							},
							"query": "fragment CategoryFields on CategoryModel {\n  active\n  boost\n  hasChildren\n  categoryNamesPath\n  isAvailableInHome\n  level\n  name\n  path\n  reference\n  slug\n  photoUrl\n  imageUrl\n  shortName\n  isFeatured\n  isAssociatedToCatalog\n  __typename\n}\n\nfragment CatalogProductTagModel on CatalogProductTagModel {\n  description\n  enabled\n  textColor\n  filter\n  tagReference\n  backgroundColor\n  name\n  __typename\n}\n\nfragment CatalogProductFormatModel on CatalogProductFormatModel {\n  format\n  equivalence\n  unitEquivalence\n  clickMultiplier\n  minQty\n  maxQty\n  __typename\n}\n\nfragment Taxes on ProductTaxModel {\n  taxId\n  taxName\n  taxType\n  taxValue\n  taxSubTotal\n  __typename\n}\n\nfragment PromotionCondition on PromotionCondition {\n  quantity\n  price\n  priceBeforeTaxes\n  taxTotal\n  taxes {\n    ...Taxes\n    __typename\n  }\n  __typename\n}\n\nfragment Promotion on Promotion {\n  type\n  isActive\n  conditions {\n    ...PromotionCondition\n    __typename\n  }\n  description\n  endDateTime\n  startDateTime\n  __typename\n}\n\nfragment PromotedModel on PromotedModel {\n  isPromoted\n  onLoadBeacon\n  onClickBeacon\n  onViewBeacon\n  onBasketChangeBeacon\n  onWishlistBeacon\n  __typename\n}\n\nfragment SpecificationModel on SpecificationModel {\n  title\n  values {\n    label\n    value\n    __typename\n  }\n  __typename\n}\n\nfragment NutritionalDetailsInformation on NutritionalDetailsInformation {\n  servingName\n  servingSize\n  servingUnit\n  servingsPerPortion\n  nutritionalTable {\n    nutrientName\n    quantity\n    unit\n    quantityPerPortion\n    dailyValue\n    __typename\n  }\n  bottomInfo\n  __typename\n}\n\nfragment Promotions on PromotionV2 {\n  type\n  description\n  promotionReference\n  startDateTime\n  endDateTime\n  isActive\n  conditions {\n    field\n    operator\n    values\n    value\n    __typename\n  }\n  benefit {\n    type\n    label\n    value\n    values\n    imagesURL\n    __typename\n  }\n  __typename\n}\n\nfragment CatalogProductModel on CatalogProductModel {\n  name\n  price\n  photosUrl\n  unit\n  subUnit\n  subQty\n  description\n  sku\n  ean\n  maxQty\n  minQty\n  clickMultiplier\n  nutritionalDetails\n  isActive\n  slug\n  brand\n  stock\n  securityStock\n  boost\n  isAvailable\n  location\n  priceBeforeTaxes\n  taxTotal\n  promotion {\n    ...Promotion\n    __typename\n  }\n  taxes {\n    ...Taxes\n    __typename\n  }\n  categories {\n    ...CategoryFields\n    __typename\n  }\n  categoriesData {\n    ...CategoryFields\n    __typename\n  }\n  formats {\n    ...CatalogProductFormatModel\n    __typename\n  }\n  tags {\n    ...CatalogProductTagModel\n    __typename\n  }\n  specifications {\n    ...SpecificationModel\n    __typename\n  }\n  promoted {\n    ...PromotedModel\n    __typename\n  }\n  score\n  relatedProducts\n  ingredients\n  stockWarning\n  nutritionalDetailsInformation {\n    ...NutritionalDetailsInformation\n    __typename\n  }\n  productVariants\n  isVariant\n  isDominant\n  promotions {\n    ...Promotions\n    __typename\n  }\n  seals\n  previousPrice\n  previousPricePerSubUnit\n  pricePerSubUnit\n  hasAgeRestriction\n  type\n  __typename\n}\n\nfragment CategoryWithProductsModel on CategoryWithProductsModel {\n  name\n  reference\n  level\n  path\n  hasChildren\n  active\n  boost\n  isAvailableInHome\n  slug\n  photoUrl\n  categoryNamesPath\n  imageUrl\n  shortName\n  isFeatured\n  products {\n    ...CatalogProductModel\n    __typename\n  }\n  hasAgeRestriction\n  __typename\n}\n\nfragment PaginationTotalModel on PaginationTotalModel {\n  value\n  relation\n  __typename\n}\n\nfragment PaginationModel on PaginationModel {\n  page\n  pages\n  total {\n    ...PaginationTotalModel\n    __typename\n  }\n  __typename\n}\n\nfragment AggregateBucketModel on AggregateBucketModel {\n  min\n  max\n  key\n  docCount\n  __typename\n}\n\nfragment AggregateModel on AggregateModel {\n  name\n  docCount\n  buckets {\n    ...AggregateBucketModel\n    __typename\n  }\n  __typename\n}\n\nfragment BannerModel on BannerModel {\n  id\n  storeId\n  title\n  desktopImage\n  mobileImage\n  targetUrl\n  targetUrlInfo {\n    type\n    url\n    __typename\n  }\n  targetCategory\n  index\n  categoryId\n  __typename\n}\n\nfragment CarouselModel on CarouselModel {\n  id\n  name\n  autoplaySpeed\n  lazyLoading\n  isActive\n  createdAt\n  updatedAt\n  banners {\n    id\n    name\n    webImageUrl\n    tabletImageUrl\n    appImageUrl\n    redirectUrl\n    redirectMode\n    isActive\n    __typename\n  }\n  position\n  __typename\n}\n\nquery GetProductsByCategory($getProductsByCategoryInput: GetProductsByCategoryInput!) {\n  getProductsByCategory(getProductsByCategoryInput: $getProductsByCategoryInput) {\n    category {\n      ...CategoryWithProductsModel\n      __typename\n    }\n    pagination {\n      ...PaginationModel\n      __typename\n    }\n    aggregates {\n      ...AggregateModel\n      __typename\n    }\n    carousels {\n      ...CarouselModel\n      __typename\n    }\n    banners {\n      ...BannerModel\n      __typename\n    }\n    promoted {\n      ...PromotedModel\n      __typename\n    }\n    __typename\n  }\n}"
						}
					]
					
					# Send an HTTP POST request and verify that the server response is successful
					try:

						data_products_by_category = pw_post(main_url, payload_products_by_category)

						if not data_products_by_category:
							# Retry a second time if no data is obtained
							try:
								time.sleep(60)
								print("Retrying...")
								data_products_by_category = pw_post(main_url, payload_products_by_category)
							except Exception as es_2:
								print("Error: ", es_2)
								print("Retry failed after waiting 60 seconds.")
					
					# If the request fails, perform a second retry
					except Exception as e:
						print(f"Error de conexi�n: {e}")
						try: 

							print("First attempt failed:", e)
							print("Retrying once more...\n")
							time.sleep(60)
							data_products_by_category = pw_post(main_url, payload_products_by_category)

						except Exception as es2:

							print("The second attempt has failed as well. Error: ", es2)
					human_delay()

					# If no valid data was obtained after the retries, skip the remaining pages of this category
					if not has_products_data(data_products_by_category):
						print(f"No data obtained for category '{path_level.get('reference')}' page {current_page} after retries. Skipping remaining pages...")
						break

					# All products are obtained based on the category
					products = data_products_by_category[0]["data"]["getProductsByCategory"]["category"]["products"]
										
					# Products are obtained from the 2nd pagination onwards
					for product in products:
						if product["promotion"] is None:
							discount_price = product["promotion"]                                           
						else:
							discount_price = product["promotion"]["conditions"][0]["price"]

						product_by_cat.append(
							{
								"level_1": path_level["level_1"],
								"level_2": path_level["level_2"],
								"level_3": path_level["level_3"],
								"name_prod": product["name"],
								"sku":product["sku"],
								"unit": product["unit"],
								"price": product["price"],
								"discount_price": discount_price,
								"description": product["description"],
								"brand": product["brand"],
								"stock": product["stock"],
								"isAvailable": product["isAvailable"],                                  
							}
						)
						obtained_products_count =  obtained_products_count + 1
						print(f"product {obtained_products_count} obtained")                    
					current_page = current_page + 1

			# The total number of products on the website is compared with the total number of products extracted
			if total_product_web == len(product_by_cat):
				
				count=0
				product_data=[]
				
				# Regular expression to extract keys and values from the product description
				pattern = r'<strong>(.*?)\s*:\s*</strong>([^<]*)'
				
				# Format the date in YMD format
				formatted_date = date.today().strftime(format)
				print(formatted_date)

				# A new Excel workbook is created
				wb = Workbook()            
				ws = wb.active
				
				for prod_nam in product_by_cat:                                           
					count = count + 1         
					print(f"Extracting information from product: {count} of {total_product_web} products")

					# Find all matches
					matches = re.findall(pattern, prod_nam["description"])
					
					# Convert to dictionary
					description_data = {description_key.strip(): description_value.strip() for description_key, description_value in matches}                    

					benefits_description = None
					active_ingredient = None
					therapeutic_action = None

					# Extract the keys and values from the description
					for k, v in description_data.items():                        
						
						# Remove the accents from the keys in the description.
						text_sin_acento=unicodedata.normalize('NFKD', k).encode('ASCII', 'ignore').decode('utf-8')                        

						# Verify that the text exists in the key of the text without accents 'descripcion y beneficios'
						if "beneficios" in text_sin_acento.lower():
							benefits_description = v                            

						# Verify that the text exists in the key of the text without accents 'principio activo'
						if "activo" in text_sin_acento.lower():
							active_ingredient = v

						# Verify that the text exists in the key of the text without accents 'accion terapeutica'
						if "terapeutica" in text_sin_acento.lower():
							therapeutic_action = v
					
					# Extract the purchase availability of a product
					if prod_nam["isAvailable"]: # True/False Default
						availability = "Disponible"
					else:
						availability = "No disponible"                
					
					product_data.append(                                        
						[
							prod_nam["level_1"],
							prod_nam["level_2"],
							prod_nam["level_3"],
							prod_nam["name_prod"],
							prod_nam["unit"],
							prod_nam["price"],
							prod_nam["discount_price"],                            
							prod_nam["brand"],
							prod_nam["stock"],
							availability,
							benefits_description,
							active_ingredient,
							therapeutic_action,
							int(prod_nam["sku"]),
							formatted_date
						] 
					)                                    
				
				if product_data:
					ws.title = "Reporte"

					# Add a merged title in row 1 (A1:O1)
					ws.merge_cells('A1:O1')
					ws['A1'] = "Reporte de Productos, Farmacia Ch�vez, D_BO_000000555"
					ws['A1'].font = Font(size=14, bold=True)
					ws['A1'].alignment = Alignment(horizontal='center', vertical='center')                    

					# Merge rows 3 and 4 for the headers
					ws.merge_cells('A3:A4')
					ws.merge_cells('B3:B4')
					ws.merge_cells('C3:C4')
					ws.merge_cells('D3:D4')
					ws.merge_cells('E3:E4')
					ws.merge_cells('F3:F4')
					ws.merge_cells('G3:G4')
					ws.merge_cells('H3:H4')                
					ws.merge_cells('I3:I4')   
					ws.merge_cells('J3:J4')  
					ws.merge_cells('O3:O4')                                           

					# Set values to the header
					ws['A3'] = "Categoria (nv1)"
					ws['B3'] = "SubCategoria (nv2)"
					ws['C3'] = "Item (nv3)"
					ws['D3'] = "Nombre del Producto"
					ws['E3'] = "Unidad"
					ws['F3'] = "Precio (Bs)"
					ws['G3'] = "Precio con Descuento (Bs)"                    
					ws['H3'] = "Marca"
					ws['I3'] = "Unidades Disponibles (stock)"
					ws['J3'] = "Disponibilidad de Compra"

					# Merge K3:N3 for Description
					ws.merge_cells('K3:N3')                    
					ws['K3'] = "Descripcion"

					# Subheaders only for Description" (row 4)
					ws['K4'] = 'Descripci�n y beneficios'
					ws['L4'] = 'Principio activo'
					ws['M4'] = 'Acci�n terap�utica'
					ws['N4'] = 'Sku'                    
					ws['O3'] = "Fecha"

					# Header styles
					bold_font = Font(bold=True)
					center_align = Alignment(horizontal='center', vertical='center')  

					# Applies bold formatting and centers the text for the specified headers and subheaders                  
					for cell in ['A3', 'B3', 'C3', 'D3', 'E3','F3','G3', 'H3', 'I3','J3','k3','K4','L4','M4','N4','O3']:
						ws[cell].font = bold_font
						ws[cell].alignment = center_align

					# Writes the data to the Excel sheet starting from row 5
					for row_idx, product_row in enumerate(product_data, start=5):

						# Iterates through each value starting from column 1
						for col_idx, val in enumerate(product_row, start=1):
							
							# Cleans non-printable or problematic characters using a regular expression
							if isinstance(val,str):
								clean_value = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\uD800-\uDFFF\uFFFE\uFFFF]', '', val)
								ws.cell(row=row_idx, column=col_idx, value=clean_value)
							else:
								ws.cell(row=row_idx, column=col_idx, value=val)
							
					# Adjust column width
					for col in ['A', 'B', 'C', 'D','E','F','G','H','I','J','K','L','M','N','O']:
						ws.column_dimensions[col].width = 12

					# Borders for headers and data
					thin = Side(border_style="thin", color="000000")
					border = Border(top=thin, left=thin, right=thin, bottom=thin)

					# Applies borders to the cells within the table row range
					for excel_row in range(3, len(product_data)+5):
						for col in ['A', 'B', 'C', 'D', 'E','F','G','H','I','J','K','L','M','N','O']:
							ws[f"{col}{excel_row}"].border = border
					
					file_path = os.path.join(path_tmp, f"{key_words}_{formatted_date}.xlsx")

					# Save                    
					wb.save(file_path)

					list_files.append(
						{
							"tmp_path": file_path,
							"updated_to": formatted_date,
							"download_url":'-', 

						}
					)
				
				return list_files
			else:
				print("Not all products could be extracted from the 'Farmacia Chavez' website.")
				print("The number of extracted products does not equal the number of products available on the website")
				print("Number of extracted products: ",len(product_by_cat))
				print("Number of products on the website: ",total_product_web)
				return []

		except Exception as e:
			print(f"An error ocurred: {e}")
			traceback.print_exc()
			return []
		finally:
			try:
				browser.close()
				playwright_ctx.stop()
			except Exception:
				pass

Executor_D_BO_000000555 = D_BO_000000555
Robot = D_BO_000000555
