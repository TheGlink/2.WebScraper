from dataclasses import dataclass
from genericpath import exists
from re import sub
from urllib.request import urlretrieve
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import os, json, uuid, time, random, aws

class Scraper:
    def __init__(self, url:str, autoscrape:bool = True):
        self.URL = url
        options = Options()
        options.add_argument("--headless")
        self.driver = Chrome(service=Service(ChromeDriverManager().install()), options = options)
        self.driver.get(self.URL)
        self.wait = WebDriverWait(self.driver, 10)
        self.data_handler = aws.DataHandler('raw_data')
            
        if not exists("raw_data"):
            os.mkdir("raw_data")
        if autoscrape:
            self.run_scraper()

    @dataclass
    class _Holiday():
        details = {
        "url": str,
        "uuid": str,
        "human_id": str,
        "hotel": str,
        "area": str,
        "country": str,
        "price": int,
        "adults/children": list,
        "nights": int,
        "catering": str,
        "next_date": str,
        "rating": float,
        "images": list,
        }

        def get_detail(self, detail:str):
            try:
                return self.details[detail]
            except Exception:
                print(f"Detail not foind: {detail}")

    def _accept_cookies(self, xpath):
        '''
        Finds the Accept Cookies Button, waits for it to be clickable and then clicks it
        '''
        try:
            cookies_XPATH = (By.ID, xpath)
            cookies_btn = self.wait.until(EC.element_to_be_clickable(cookies_XPATH))
            time.sleep(1)
            cookies_btn.click()
            return True
        except Exception:
            return False

    def __remove_dict_keys_from_list(self, dict:dict, list:list):
        '''
        remove all dict entries form a list passed in, this list should be empty keys
        '''
        for i in list:
            dict.pop(i,None)
        return dict

    def _dict_countries(self):
        '''
        Creates a dictionary, using the destination as a key and the URL as the value
        '''
        countries = {}
        elems = self.driver.find_elements(By.XPATH, '//a[@class = "item shadow"]')
        for elem in elems:
            dest_link = elem.get_attribute('href')
            country_name = elem.get_attribute('title')
            countries[country_name] = dest_link
        #logging.debug('countries finished')
        self._save_to_json(countries, 'country_urls.json', 'json_data/')
        return countries
    
    def _get_holidays_from_country(self, dict_of_countries:dict):
        '''
        Takes the country url dict and gets all the holidays hrefs from the urls for the countries
        '''
        #initialize/clear the list of countries without holidays
        countries_without_holidays = []
        #xpaths for the current project. Can be changed per site
        holiday_xpath = '//a[@class = "more color-white bg-yellow font-gotham"]'
        city_xpath = '//a[@class = "item shadow"]'

        holiday_list = list(dict_of_countries.values())
        #loop throught the countries gathered from the site
        for holiday in holiday_list:
            list_of_holidays = []
            try:
                #set the link of the holiday
                dest_link = dict_of_countries[holiday]
                #find the href attributess
                list_of_holidays = self._find_href(dest_link, holiday_xpath)
                #if there are no holidays available try looking for cities (site layout inconsistant)
                if len(list_of_holidays)<1:
                    list_of_cities = self._find_href(dest_link, city_xpath)
                    #if cities are found find holidays within
                    for city in list_of_cities:
                        list_of_holidays = self._find_href(city, holiday_xpath)
                #if there are still no entries, set the 
                if len(list_of_holidays) < 1:
                    countries_without_holidays.append(holiday)
                #assign the list to the current country in the dict
                holiday_list[holiday] = list_of_holidays
            except TypeError:
                return holiday_list
        #remove keys with no values
        holiday_list =  self.__remove_dict_keys_from_list(holiday_list, countries_without_holidays)
        self._save_to_json(holiday_list, "holiday_url_dict.json", "json_data/")
        return holiday_list

    def _find_href(self, url:str, xpath:str):
        '''
        finds hrefs on a given url using the xpath and returns a list of the hrefs 
        '''
        href_list = []
        self.driver.get(url)
        elems = self.driver.find_elements(By.XPATH, f'{xpath}')
        for elem in elems:
            dest_link = elem.get_attribute('href')
            href_list.append(dest_link)
        return href_list

    def _save_to_json(self, data, file_name:str, folder_path:str, ):
        '''
        save a file as a json, with a specific path
        '''
        # get the working directory and append the file name arguemnts
        starting_directory = os.getcwd()
        dir_path = os.path.join(starting_directory,folder_path)
        #create directory if it doesnt exist
        if not os.path.exists(dir_path): #and not os.path.isdir(dir_path):
            os.mkdir(dir_path)
        #attempt to write the data param to a json file
        try:
            os.chdir(dir_path)
            #check that the data is list or dict to dump
            if isinstance(data, (dict, list)):
                with open(file_name, 'w') as outfile:
                    #json_object = json.loads(data)                    
                    json.dump(data, outfile, indent = 4 )
            else:
                with open(file_name, 'w') as outfile:
                    json.write(data)
                #cd to the starting directory
            os.chdir(starting_directory)
        except Exception:
            print(f'Failed to save: {file_name} as JSON')
        
    def _load_from_json(self, file_name:str, expected:type):
        '''
        load data from json for testing scrape
        '''
        with open(file_name) as json_file:
            data = json.load(json_file)
        try:
            if type(data) == expected:
                return data
            else:
                raise TypeError
        except TypeError:
               print("Data retrieval of file: ", file_name, " failed, incorrect type: ", type(data))
          
    def __scrape_per_country(self, dict_of_countries:dict):
        '''
        navigate to the holiday url and create the holiday data object
        gets the datails and assign them to the dict entry
        create the list(dict.fromkeys(countries)path for saving the holiday
        returns nothing
        Scrape the holiday data
        nested for loop is used to set country as it was not reliably scrapable from
        the holiday url itslef
        '''
        scraped_images = aws._images_already_scraped()

        #prep for saving
        holiday_json_name = 'data.json'
        for country in dict_of_countries:
            for url in dict_of_countries[country]:
                # scrapes details
                self.driver.get(dict_of_countries[country][url])
                current_holiday = self._Holiday()
                current_holiday["country"] = country
                scraped_holiday = self._get_holiday_details(current_holiday, country)

                holiday_path = os.path.join("raw_data", f'{current_holiday.get_detail("uuid")}')
                os.mkdir(holiday_path)
                image_path = os.path.join(holiday_path, "images")
                os.mkdir(image_path)
                self._save_to_json(scraped_holiday.details, holiday_json_name, holiday_path)

                #cleaned and uploaded
                json_data = json.dump(scraped_holiday.details, indent = 4)
                cleaner = aws.DataHandler(json_data)
                json_cleaned = aws.clean(json_data)
                if aws.check_database_for_duplicate(json_cleaned):
                    aws.send_to_rds(json_cleaned)
                
                if current_holiday['images'] not in scraped_holiday:
                    self.__scrape_3_images(current_holiday,image_path, scraped_images)
    
    def __scrape_3_images(self, Holiday:object, folder_path, scraped_images:list):
        '''
        Scrape 3 images for each holiday into an image folder within the uuid folder created in scrape_per_country
        '''
        images:list = Holiday.get_detail('images')
        for i in range(3):
            if images[i] in scraped_images[:]:
                image_link = images[i]
                image_name = f"{Holiday.get_detail('uuid')}_{str(i)}.jpg"
                path = os.path.join(folder_path ,image_name)
                urlretrieve(image_link, path)
                time.sleep(random.randint(0,3))
            else:
                continue
        
    def __get_holiday_details(self, holiday:object, country: str):
        '''
        This method collects details from each holiday url

        '''
        #all non details containers (including locations)
        location_container = '//div[@class="hotel-info bg-white shadow"]'
        country_base = '//a[@class="btn bg-yellow color-white"]'
        url = self.driver.current_url
        holiday_id = str(uuid.uuid4())
        deterministic_id = url.replace("https://www.haystravel.co.uk/","")
        hotel = self._find_holiday_detail(location_container, '/h1')
        resort = self._find_holiday_detail(location_container, '/div[2]')
        holiday_country = self._find_holiday_detail(country_base, '//*[@id="destination-one-content"]/div[3]/div/a')

        #detail container fields
        details_container = '//div[@class="text"]'
        holiday_price = self._find_holiday_detail("", '//div[@class="price color-blue"]')
        group_size = self._find_holiday_detail(details_container, '/div[1]//p')
        duration = self._find_holiday_detail(details_container, '/div[2]//p')
        catering_type = self._find_holiday_detail(details_container, '/div[3]//p')
        soonest_departure = self._find_holiday_detail(details_container, '/div[5]//p[1]')
        soonest_date = self._convert_str_to_datetime(soonest_departure)
        star_rating = float(self.driver.find_element(By.XPATH, '//span[@class = "rating-label"]').text.rstrip("/5"))
        images = []
        images_element = self.driver.find_elements(By.XPATH, '//div[@class = "carousel-item"]/img')
        for image in images_element:
            src = image.get_attribute('src')
            images.append(src)

        holiday.details = {
            "url": url,
            "uuid": holiday_id,
            "human_id": deterministic_id,
            "hotel": hotel.capitalize(),
            "area": resort,
            "country": holiday_country,
            "price": self._remove_chars_convert_to_int(holiday_price),
            "adults/children": self._remove_chars_convert_to_int(self._check_family_holiday(group_size)),
            "duration": self._remove_chars_convert_to_int(duration),
            "catering": catering_type,
            "next_date": soonest_date,
            "rating": star_rating,
            "images": images}
        return holiday

    def _convert_str_to_datetime(self, date_string:str):
        '''
        convert string read form XPATH to a datetime format
        '''
        month = {"January": "01",
                 "February": "02",
                 "March": "03",
                 "April": "04",
                 "May": "05",
                 "June": "06",
                 "July": "07",
                 "August": "08",
                 "September": "09",
                 "October": "10",
                 "November": "11",
                 "December": "12"
                }
        try:
            #split string to isolate day, e.g 1st, 22nd, 31st
            new_date = date_string.split(" ")
            #remove characters from the day use dict to change month to number
            #remove date subscripts
            new_date[0] = sub(r'[^\d.]', '', new_date[0]).zfill(2)
            # converts month word
            new_date[1] = month[new_date[1].capitalize()]
            new_date.reverse()
            #convert the month to numberdate
            new_date = "-".join(new_date)            
            return new_date
        except KeyError as e:
            print(f"Date String Failed at {self.driver.current_url()}")
            raise KeyError from e

    def _remove_chars_convert_to_int(self, input):
        '''
        remove characters to convert strings from get_attribute("innerText") to ints
        allowing for easier datacleaning. This is done by subbing all non numeric characters
        leaving us with only numbers which are converted to integers. This handles
        both strings and lists of strings
        '''
        if isinstance(input, list):
            new_int_list = []
            for i in range(len(input)):
                new_int = sub(r'[^\d.]', '', input[i])
                new_int_list.append(new_int)
            return list(map(int, new_int_list))
        else:
            new_int = int(sub(r'[^\d.]', '', input))
            return new_int
            
    def _check_family_holiday(self, no_people:str):
        '''
        if there are Adults and children in a holiday deal split this into a list of 2 entries
        to be converted into ints
        '''
        return no_people.split(' + ')
        
    def _find_holiday_detail(self, container:str, element_xpath:str):
        '''
        Find details by relative xpath given xpath
        '''
        try:
            path = container + element_xpath
            element = self.driver.find_element(By.XPATH, path)
            return element.get_attribute("innerText")
        except Exception:
            print("element not found")
    
    def run_scraper(self):
        '''
        Main Scraping of the program
        '''
        self._accept_cookies('onetrust-accept-btn-handler')
        try:
            country_dict = self._dict_countries()
            url_dict = self._get_holidays_from_country(country_dict)
            self.__scrape_per_country(url_dict)

        finally:
            print("Scrape Complete")
            self.driver.quit()