import requests
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import pandas as pd
from urllib.parse import urlparse
import os

# Create session
session = requests.Session()
session.cookies.set('SESSION', 'ea04f069536bf20c~3568a688-115d-4eba-9a7c-1536f22023ea', domain='www.idealista.com')
session.cookies.set('contact3568a688-115d-4eba-9a7c-1536f22023ea', "{'maxNumberContactsAllow':10}", domain='www.idealista.com')
session.cookies.set('datadome', 'gL_Z_dgJne3ePs7qLStxbt~QGmtEHcv3gXjjTmFbfrz_fUI6gkNxs_Nlxiup3fUkV_MiTw~7cfBjMkevMw0pGG50A0xZDgyGQFuvTBgIDcLTkyu98VSpsAAP4lWWYfMP', domain='www.idealista.com')
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36",
    "Accept-Encoding": "gzip, deflate",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "DNT": "1",
    "Connection": "close",
    "Upgrade-Insecure-Requests": "1"
}

def get_lat_lon_from_address(address):
    geolocator = Nominatim(user_agent="username")
    try:
        location = geolocator.geocode(address, timeout=10)
        if location:
            return location.latitude, location.longitude
        else:
            return None, None
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"Error: {e}")
        return None, None

def get_anchor_tags(url):
    links = []
    page_number = 1
    while url:
        r = session.get(url, headers=headers)
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, "lxml")
            anchor_tags = soup.find_all('a', class_='item-link')
            page_links = []
            for tag in anchor_tags:
                href = tag.get('href')
                if not href.startswith('http'):
                    href = 'https://www.idealista.com' + href
                page_links.append({'href': href})
            links.extend(page_links)
            print(f"Page {page_number} - Number of anchor tags: {len(page_links)}")

            next_page_tag = soup.find('li', class_='next')
            if next_page_tag:
                next_page_link = next_page_tag.find('a')
                if next_page_link and 'href' in next_page_link.attrs:
                    url = next_page_link['href']
                    if not url.startswith('http'):
                        url = 'https://www.idealista.com' + url
                else:
                    url = None
            else:
                url = None

            page_number += 1
        else:
            print(f"Failed to retrieve the page, status code: {r.status_code}")
            break
    return links

def get_property_type_from_url(base_url):
    keywords = {
        "viviendas": "housing",
        "oficinas": "offices",
        "locales o naves": "premises or warehouses",
        "traspasos": "transfers",
        "garajes": "garage",
        "terrenos": "land",
        "trasteros": "storerooms",
        "edificios": "building"
    }
    for keyword, property_type in keywords.items():
        if keyword in base_url:
            return property_type
    return "unknown"

def get_transaction_type_from_url(base_url):
    if "venta" in base_url:
        return "sale"
    elif "alquiler" in base_url:
        return "rent"
    return "unknown"

def clean_features(features):
    cleaned_features = []
    for feature in features:
        feature = ' '.join(feature.split()).replace(" \n", "").strip()
        cleaned_features.append(feature)
    return cleaned_features

def get_property_details(property_url, transaction_type, property_type):
    r = session.get(property_url, headers=headers)
    if r.status_code == 200:
        soup = BeautifulSoup(r.content, "lxml")
        
        # Name
        name_tag = soup.find('span', class_='main-info__title-main')
        name = name_tag.text.strip() if name_tag else None
        
        # Address
        address_list = []
        header_map = soup.find('div', id='headerMap')
        if header_map:
            for li in header_map.find_all('li', class_='header-map-list'):
                address_list.append(li.get_text(strip=True))
        address = ', '.join(address_list) if address_list else None

        # Price
        price_tag = soup.find('strong', class_='price')
        price = price_tag.text.strip() if price_tag else None

        # Description
        description = None
        comment_tag = soup.find('div', class_='comment')
        if comment_tag:
            description_paragraph = comment_tag.find('p')
            if description_paragraph:
                description = description_paragraph.get_text(separator="\n").strip()

        # Properties
        properties_tag = soup.find('div', class_='details-property')
        properties = []
        if properties_tag:
            for ul in properties_tag.find_all('ul'):
                for li in ul.find_all('li'):
                    properties.append(li.text.strip())

        latitude, longitude = get_lat_lon_from_address(address) if address else (None, None)

        # Features
        features = []
        features_tag = soup.find('div', class_='info-features')
        if features_tag:
            for span in features_tag.find_all('span'):
                features.append(span.text.strip())

        cleaned_features = clean_features(features)

        energy_certificate = {'consumption': None, 'emissions': None}

        return {
            'url': property_url,
            'name': name,
            'address': address,
            'price': price,
            'description': description,
            'properties': properties,
            'features': cleaned_features,
            'transaction_type': transaction_type,
            'property_type': property_type,
            'latitude': latitude,
            'longitude': longitude,
            'energy_certificate': energy_certificate
        }
    else:
        print(f"Failed to retrieve the property page, status code: {r.status_code}")
        return None

def get_base_url(url):
    parsed_url = urlparse(url)
    return parsed_url.netloc

if __name__ == "__main__":
    start_urls = [
       'https://www.idealista.com/en/geo/venta-viviendas/andalucia/',
        # Add more URLs as needed
    ]
    
    for start_url in start_urls:
        base_url = get_base_url(start_url)
        transaction_type = get_transaction_type_from_url(start_url)
        property_type = get_property_type_from_url(start_url)
        all_links = get_anchor_tags(start_url)
        
        data = []
        for link in all_links:
            details = get_property_details(link['href'], transaction_type, property_type)
            if details:
                data.append(details)
        
        # Save data to Excel
        df = pd.DataFrame(data)
        sanitized_url = start_url.replace('https://', '').replace('/', '_').replace('.', '_')
        
        output_directory = os.path.join(os.getcwd(), 'artifacts')  # Save in 'artifacts' directory
        os.makedirs(output_directory, exist_ok=True)
        
        excel_file_path = os.path.join(output_directory, f'{sanitized_url}.xlsx')
        df.to_excel(excel_file_path, index=False)
        print(f"Data saved to {excel_file_path}")
