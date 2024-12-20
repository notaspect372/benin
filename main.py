import os
import requests
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import pandas as pd
import re
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Function to create a requests session with retries
def requests_session_with_retries():
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

# Create a session with retries
session = requests_session_with_retries()

# Headers with more fields to avoid 400 errors
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36',
    'Referer': 'https://www.buysellcyprus.com',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}

# Delay between requests
delay_between_requests = 2  # seconds

def get_property_links_from_page(url):
    """Get property links from a single page."""
    try:
        response = session.get(url, timeout=10, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to retrieve the page {url}. Error: {e}")
        return set()

    soup = BeautifulSoup(response.content, 'html.parser')

    # Find all property links
    property_links = set()
    for div in soup.find_all('div', class_='bs-card-title'):
        a = div.find('a', href=True)
        if a:
            href = a['href']
            if 'property' in href:
                full_url = 'https://www.buysellcyprus.com' + href if href.startswith('/') else href
                property_links.add(full_url)
    return property_links

def get_total_pages(url):
    """Get the total number of pages from the first page."""
    try:
        response = session.get(url, timeout=10, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to retrieve the page {url}. Error: {e}")
        return 1

    soup = BeautifulSoup(response.content, 'html.parser')
    paging_div = soup.find('div', class_='paging-text paging-number')
    if paging_div:
        paging_text = paging_div.get_text(strip=True)
        if 'of' in paging_text:
            total_pages = int(paging_text.split('of')[-1].strip())
            return total_pages
    return 1

def get_property_data(url):
    """Scrape detailed property data from a given property URL."""
    try:
        response = session.get(url, timeout=10, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to retrieve the property page {url}. Error: {e}")
        return None

    soup = BeautifulSoup(response.content, 'html.parser')

    # Extract name
    name_meta = soup.find('meta', property='og:title')
    name = name_meta['content'] if name_meta else 'N/A'

    # Extract price
    price_div = soup.find('div', class_='bs-listing-info-price')
    price = 'N/A'
    if price_div:
        price_span = price_div.find('span', class_='bs-listing-info-price-base')
        price = price_span.get_text(strip=True) if price_span else 'N/A'

    # Extract address
    address_meta = soup.find('meta', itemprop='streetAddress')
    address = address_meta['content'].replace('Cyprus', '').strip() if address_meta else 'N/A'

    # Extract description
    description_div = soup.find('div', class_='bs-listing-info-description-main')
    description = 'N/A'
    if description_div:
        description_p = description_div.find('p', class_='description-text')
        description = description_p.get_text(strip=True) if description_p else 'N/A'

    # Extract characteristics
    characteristics = {}
    characteristics_div = soup.find('div', class_='bs-listing-info-features-main')
    if characteristics_div:
        characteristics_list = characteristics_div.find_all('li')
        for item in characteristics_list:
            key_value = item.get_text(strip=True).split(':')
            if len(key_value) == 2:
                key = key_value[0].strip()
                value = key_value[1].strip()
                characteristics[key] = value

    # Determine property type
    property_type = ''
    keywords = [
        'Apartment', 'House', 'Hotel', 'Land', 'Residential', 'Commercial', 'Industrial', 'Farm'
    ]

    name_lower = name.lower()
    for keyword in keywords:
        if keyword.lower() in name_lower:
            property_type = keyword
            break

    # Extract transaction type from URL
    transaction_type = 'rent' if 'for-rent' in url else 'buy'

    # Extract area
    area = characteristics.get('Total covered area', characteristics.get('Plot', 'N/A'))

    # Get latitude and longitude
    geolocator = Nominatim(user_agent="property_scraper")
    latitude, longitude = 'N/A', 'N/A'
    try:
        location = geolocator.geocode(address, timeout=10)
        if location:
            latitude, longitude = location.latitude, location.longitude
    except GeocoderTimedOut:
        print(f"Geocoding timed out for address: {address}")

    # Combine all data into a dictionary
    property_data = {
        'url': url,
        'name': name,
        'address': address,
        'price': price,
        'description': description,
        'property_type': property_type,
        'transaction_type': transaction_type,
        'area': area,
        'characteristics': characteristics,
        'latitude': latitude,
        'longitude': longitude,
    }
    return property_data

def scrape_properties(base_url):
    total_pages = get_total_pages(base_url.format(1))
    print(f"Total number of pages: {total_pages}")

    all_property_links = set()
    for page in range(1, total_pages + 1):
        page_url = base_url.format(page)
        property_links = get_property_links_from_page(page_url)
        all_property_links.update(property_links)
        print(f"Scraped {len(property_links)} properties from page {page}")
        time.sleep(delay_between_requests)

    all_property_data = []
    for link in all_property_links:
        property_data = get_property_data(link)
        if property_data:
            all_property_data.append(property_data)
            print(f"Scraped data for property: {property_data['name']}")
            time.sleep(delay_between_requests)

    return all_property_data

def main(urls):
    output_dir = "artifacts"
    os.makedirs(output_dir, exist_ok=True)

    for url in urls:
        base_url = re.sub(r'page-\d+', 'page-{}', url)
        property_data = scrape_properties(base_url)

        df = pd.DataFrame(property_data)
        print(df)

        file_name = re.sub(r'\W+', '_', url) + '.xlsx'
        file_path = os.path.join(output_dir, file_name)
        df.to_excel(file_path, index=False)
        print(f"Data saved to {file_path}")

urls = [
    'https://www.buysellcyprus.com/properties-for-rent/cur-usd/no-nearby/type-house/price-0-4450/sort-ru/page-1',
]

if __name__ == "__main__":
    main(urls)
