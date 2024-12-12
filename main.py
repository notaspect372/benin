import os
import requests
from bs4 import BeautifulSoup
import pandas as pd
import math
import re
import json
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from requests.exceptions import ReadTimeout

# Ensure the artifacts directory exists
os.makedirs("artifacts", exist_ok=True)

# List of URLs to process
urls_to_process = [
    "https://www.realestate.com.kh/rent/?active_tab=popularLocations&bedrooms__gte=1&bedrooms__lte=1&order_by=relevance&property_type=residential&rent_min__gte=200&rent_min__lte=200&search_type=rent",
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
# ... [Omitted for brevity: Keep the full function definition of scrape_property_details as it is in your script] ...

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
    all_data = []

    for property_url in all_property_urls:
        property_data = scrape_property_details(property_url)
        if property_data:
            all_data.append(property_data)
            # Print property data side by side with the URL
            print(property_data)

    # Create a DataFrame with all property data
    df = pd.DataFrame(all_data)

    # Save the DataFrame to the `artifacts` directory with a sanitized filename
    sanitized_filename = sanitize_filename(base_url) + ".xlsx"
    output_path = os.path.join("artifacts", sanitized_filename)
    df.to_excel(output_path, index=False, engine='openpyxl')
    print(f"Data for {base_url} saved to {output_path}")
