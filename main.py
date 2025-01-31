import os
import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
from geopy.geocoders import Nominatim
import re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def clean_text(text):
    # Replace illegal characters with a space
    if text:
        return re.sub(r'[\x00-\x1F\x7F-\x9F]', ' ', text)
    return text


def get_lat_lon(address):
    geolocator = Nominatim(user_agent="my_geocoder_app")  # Change "my_geocoder_app" to something unique
    try:
        location = geolocator.geocode(address)
        if location:
            return location.latitude, location.longitude
        else:
            return None, None
    except Exception as e:
        return None, None

def get_property_urls(base_url, start_page, end_page):
    property_urls = []
    query_mode = '&page=' if '?' in base_url else '?page='

    for page in range(start_page, end_page + 1):
        print(f"Scraping page {page} for {base_url}")

        current_url = f"{base_url}{query_mode}{page}"
        print(current_url)
        response = requests.get(current_url, headers=headers)

        if response.status_code != 200:
            print(f"Failed to retrieve page {page} from {current_url}, status code: {response.status_code}")
            break

        soup = BeautifulSoup(response.content, 'html.parser')
        page_property_urls = ['https://bf.coinafrique.com' + link.get('href') for link in soup.find_all('a', class_='card-image ad__card-image waves-block waves-light')]

        if not page_property_urls:
            print(f"No more property URLs found on page {page}. Stopping.")
            break

        property_urls.extend(page_property_urls)
        print(f"Collected {len(page_property_urls)} property URLs from page {page}")

    print(f"Total property URLs collected: {len(property_urls)}")
    return property_urls

def scrape_property_data(url):
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to retrieve property data from {url}, status code: {response.status_code}")
        return None
    soup = BeautifulSoup(response.content, 'html.parser')

    try:
        name = soup.find('meta', attrs={'name': 'title'})['content'].strip()
    except AttributeError:
        name = None

    try:
        description_div = soup.find('div', class_='ad__info__box ad__info__box-descriptions')
        description = description_div.find_all('p')[1].text.strip()
    except (AttributeError, IndexError):
        description = None

    try:
        address_tag = soup.find('span', class_='valign-wrapper', attrs={'data-address': True})
        address = address_tag['data-address'].strip() if address_tag else None
    except AttributeError:
        address = None

    try:
        price = soup.find('p', class_='price').text.strip()
    except AttributeError:
        price = None

    try:
        characteristics = {}
        characteristic_items = soup.select('.details-characteristics ul li')
        for item in characteristic_items:
            label = item.find_all('span')[0].text.strip()
            value = item.find_all('span', class_='qt')[0].text.strip()
            characteristics[label] = value
    except AttributeError:
        characteristics = None

    try:
        area = next((value for key, value in characteristics.items() if 'Superficie' in key), None)
    except AttributeError:
        area = None

    try:
        ad_details = soup.find('div', id='ad-details')
        ad_data = json.loads(ad_details['data-ad'])
        property_type = ad_data['category']['name']
    except (AttributeError, KeyError, json.JSONDecodeError):
        property_type = None

    try:
        transaction_type = "rent" if "location" in name.lower() else "buy"
    except AttributeError:
        transaction_type = None

    if address:
        latitude, longitude = get_lat_lon(address)
    else:
        latitude, longitude = None, None

    property_data = {
        'name': clean_text(name),
        'address': clean_text(address),
        'price': clean_text(price),
        'area': clean_text(area),
        'description': clean_text(description),
        'latitude': latitude,
        'longitude': longitude,
        'property_type': clean_text(property_type),
        'transaction_type': clean_text(transaction_type),
        'property_url': clean_text(url),
        'characteristics': {clean_text(k): clean_text(v) for k, v in (characteristics or {}).items()}
    }
    return property_data

def scrape_multiple_urls(urls, start_page, end_page):
    os.makedirs('artifacts', exist_ok=True)  # Create artifacts directory
    for base_url in urls:
        property_urls = get_property_urls(base_url, start_page, end_page)

        properties_data = []
        for index, property_url in enumerate(property_urls):
            print(f"Scraping property {index + 1} of {len(property_urls)} from {base_url}")
            data = scrape_property_data(property_url)
            if data:
                properties_data.append(data)

        df = pd.DataFrame(properties_data)
        excel_file_name = f"artifacts/{base_url.replace('https://', '').replace('/', '_').replace('?', '_').replace('&', '_').replace('=', '_')}.xlsx"
        df.to_excel(excel_file_name, index=False, sheet_name='Properties')

        print(f"Data from {base_url} saved to {excel_file_name}")

# Example usage
urls = [
    "https://bf.coinafrique.com/categorie/immobilier"
]
scrape_multiple_urls(urls, start_page=1, end_page=50)
