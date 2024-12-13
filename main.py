import requests
import os
from bs4 import BeautifulSoup
import pandas as pd
import math
import re
import json
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from requests.exceptions import ReadTimeout

# List of URLs to process
urls_to_process = [
    "https://www.realestate.com.kh/buy/",
    # Add more URLs as needed
]

# Function to sanitize the URL for use in a filename
def sanitize_filename(url):
    sanitized = re.sub(r'[^\w\-_. ]', '_', url)
    return sanitized

# Function to create the pagination URL
def create_pagination_url(base_url, page_number):
    transaction_type = "sale" if "search_type=sale" in base_url else "rent"
    
    if page_number == 1:
        return base_url  # First page doesn't need the `page` parameter
    
    # Construct the correct pagination URL
    return re.sub(r"(&page=\d+)?(&search_type=\w+)", f"&page={page_number}&search_type={transaction_type}", base_url)


def clean_text(text):
    """Remove unwanted Unicode characters like icon fonts."""
    # Remove Unicode characters that fall outside the range of normal printable characters
    clean_text = re.sub(r'[^\x20-\x7E]', '', text)
    return clean_text.strip()
# Function to make requests with retries on timeout
def make_request_with_retries(url, retries=3, timeout=10):
    for _ in range(retries):
        try:
            response = requests.get(url, timeout=timeout)
            return response
        except ReadTimeout:
            print(f"ReadTimeout occurred. Retrying for {url}...")
    return None  # If all retries fail

# Function to get latitude and longitude
def get_lat_long(address, retries=3):
    geolocator = Nominatim(user_agent="property_scraper", timeout=10)
    for _ in range(retries):
        try:
            location = geolocator.geocode(address)
            if location:
                return location.latitude, location.longitude
            else:
                return None, None
        except GeocoderTimedOut:
            continue  # Retry on timeout
    return None, None  # If all retries fail

# Function to scrape property details
def scrape_property_details(property_url):
    response = make_request_with_retries(property_url)
    if response is None:
        print(f"Failed to retrieve property details from {property_url} after retries.")
        return None
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Extracting the name
    name = ''
    name_tag = soup.find('h1', class_='headline alone')
    if name_tag:
        name = clean_text(name_tag.get_text(strip=True))


    transaction_type = "sale" if "sale" in name.lower() else "rent"
 
    
    sale_price = '-'
    rent_price = '-'

    # Extracting the price
    if transaction_type == "sale":
        price_tag = soup.find('span', class_='price-value')
        if price_tag:
            sale_price = clean_text(price_tag.get_text(strip=True))

    elif transaction_type == 'rent':
        price_containers = soup.find_all('div', class_='price-container')

        if price_containers:
            # Loop through all price containers and check for rent price
            for container in price_containers:
                price_value_tag = container.find('span', class_='price-value')
                suffix_tag = container.find('span', class_='suffix')

                # Check if both price and suffix exist
                if price_value_tag and suffix_tag:
                    rent_price = clean_text(price_value_tag.get_text(strip=True))
                    suffix_text = clean_text(suffix_tag.get_text(strip=True))
                    rent_price = f"{rent_price} {suffix_text}"
                break  # Stop after finding the first valid rent price


    
    # Determine the transaction type and correct the rent price
 
    # Extracting the description
    description = ''
    description_tag = soup.find('span', class_='css-zrj3zm')
    if description_tag:
        description_div = description_tag.find('div')
        if description_div:
            description = clean_text(description_div.get_text(separator='\n', strip=True))
    
    # Extracting characteristics as key-value pairs
    characteristics = {}
    characteristics_section = soup.find('div', class_='css-r7o7s2 elr7wbp0')
    if characteristics_section:
        characteristics_items = characteristics_section.find_all('div')
        for item in characteristics_items:
            value = item.find('span', class_='value').get_text(strip=True)
            label_tag = item.find('span', class_='text')
            if label_tag:  # Ensure the label exists
                label = clean_text(label_tag.get_text(strip=True))
                characteristics[clean_text(label)] = clean_text(value)

    

    # Extracting the address from the JSON data embedded in the page
    address = '-'
    latitude, longitude = None, None
    script_tag = soup.find('script', id='__NEXT_DATA__', type='application/json')
    if script_tag:
        script_content = script_tag.string
        data = json.loads(script_content)
        listing_data = data.get('props', {}).get('pageProps', {}).get('cacheData', {}).get('listing', {}).get('data', {})
        address = clean_text(listing_data.get('header', {}).get('address', "-"))
        
        # Get latitude and longitude using the geopy library
        latitude, longitude = get_lat_long(address)

    # Extracting the area
    area = None
    floor_area_tag = soup.find('span', text=re.compile(r'Floor Area', re.IGNORECASE))
    if floor_area_tag:
        area_value_tag = floor_area_tag.find_previous('span', class_='value')
        if area_value_tag:
            area = clean_text(area_value_tag.get_text(strip=True))
    
    if area is None:
        land_area_tag = soup.find('span', text=re.compile(r'Land Area', re.IGNORECASE))
        if land_area_tag:
            area_value_tag = land_area_tag.find_previous('span', class_='value')
            if area_value_tag:
                area = clean_text(area_value_tag.get_text(strip=True))

    if area is None:
        area = '-'

      # Extracting property features from the 3rd div with class 'features-block'
    features_blocks = soup.find_all('div', class_='features-block')
    property_features = []
    amenities = []
    property_overview = []

    if len(features_blocks) >= 2:
        # Scrape the 3rd div for property features
        features_section = features_blocks[1]
        features_items = features_section.find_all('span')
        for feature in features_items:
            feature_text = clean_text(feature.get_text(strip=True))
            if feature_text:  # Only include if there's valid text
                property_overview.append(feature_text)


    property_type = "not-residential"
    if property_overview[0] == 'Property type:':
        property_type = property_overview[1]

    
    if len(features_blocks) >= 3:
        # Scrape the 3rd div for property features
        features_section = features_blocks[2]
        features_items = features_section.find_all('span')
        for feature in features_items:
            feature_text = clean_text(feature.get_text(strip=True))
            if feature_text:  # Only include if there's valid text
                property_features.append(feature_text)

    if len(features_blocks) >= 4:
        # Scrape the 4th div for amenities
        amenities_section = features_blocks[3]
        amenities_items = amenities_section.find_all('span')
        for amenity in amenities_items:
            amenity_text = clean_text(amenity.get_text(strip=True))
            if amenity_text:  # Only include if there's valid text
                amenities.append(amenity_text)

    return {
            "URL": property_url,
            "Name": name,
            "Address": address,
            "Sale Price": sale_price,
            "Rent Price": rent_price,
            "Description": description,
            "Area": area,
            "Property Overview":property_overview,
            "Characteristics": {k: clean_text(v) for k, v in characteristics.items()},
            "Property Features" :  property_features,
            "Amenities" : amenities,
            "Property Type": property_type,
            "Transaction Type": transaction_type,
            "Latitude": latitude,
            "Longitude": longitude
        }

# Process each URL in the list
for base_url in urls_to_process:
    # Send a GET request to the first page with retries
    response = make_request_with_retries(base_url)
    if response is None:
        print(f"Failed to retrieve data from {base_url} after retries.")
        continue
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Find the span element with the class 'status' to get the total number of properties
    status_span = soup.find('span', class_='status')
    if status_span:
        status_text = status_span.get_text()
        number_of_properties = int(''.join(filter(str.isdigit, status_text)))
        print("Number of properties found:", number_of_properties)
    else:
        print("Status span not found")
        number_of_properties = 0

    # Calculate the total number of pages (assuming 20 properties per page)
    properties_per_page = 20
    total_pages = math.ceil(number_of_properties / properties_per_page)
    print("Total Pages:", total_pages)
    
    # Collect all property URLs
    all_property_urls = []
    for page in range(1, total_pages + 1):
        page_url = create_pagination_url(base_url, page)
        print(page_url)
        response = make_request_with_retries(page_url)
        if response is None:
            print(f"Failed to retrieve data from {page_url} after retries.")
            continue
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all articles with the class 'item css-1cpzyck eq4or9x0'
        articles = soup.find_all('div', class_='item css-1cpzyck eq4or9x0')
        property_urls = ["https://www.realestate.com.kh" + article.find('a', href=True)['href'] for article in articles]
        all_property_urls.extend(property_urls)
        
        print(f"Scraped {len(property_urls)} property URLs from page {page}")

    print("Total property URLs found:", len(all_property_urls))
    
    # Prepare to save to Excel
    # Prepare to save to Excel
    all_data = []
    
    for property_url in all_property_urls:
        property_data = scrape_property_details(property_url)
        if property_data:
            all_data.append(property_data)
            # Print property data side by side with the URL
            print(property_data)
    
    # Create a DataFrame with all property data
    df = pd.DataFrame(all_data)
    
    # Ensure the 'artifacts' directory exists
    os.makedirs("artifacts", exist_ok=True)
    
    # Save the DataFrame to the `artifacts` directory with a sanitized filename
    sanitized_filename = sanitize_filename(base_url) + ".xlsx"
    output_path = os.path.join("artifacts", sanitized_filename)
    df.to_excel(output_path, index=False, engine='openpyxl')
    print(f"Data for {base_url} saved to {output_path}")
