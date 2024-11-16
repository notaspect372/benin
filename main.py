import requests
from bs4 import BeautifulSoup
import json
import math
import re
import pandas as pd
import os
from urllib.parse import urlparse, urljoin

# Function to scrape property URLs from a base URL
def scrape_property_urls(base_url):
    response = requests.get(base_url)
    soup = BeautifulSoup(response.content, "html.parser")

    # Find the number of listings to calculate pagination
    search_subtitle_div = soup.find("div", class_="a-search-subtitle search-results-nb")
    if search_subtitle_div:
        number_of_listings = int(search_subtitle_div.find("span").text.strip().replace(" ", ""))
    else:
        print("Could not find the number of listings.")
        number_of_listings = 1

    # Calculate the total number of pages (assuming 20 listings per page)
    listings_per_page = 20
    total_pages = math.ceil(number_of_listings / listings_per_page)
    print(f"Total pages: {total_pages}")

    # Initialize a set to store all property URLs (to remove duplicates)
    all_property_urls = set()

    # Iterate through each page and scrape property URLs
    for page in range(1, total_pages + 1):
        page_url = f"{base_url}?page={page}"
        print(page_url)
        page_response = requests.get(page_url)
        page_soup = BeautifulSoup(page_response.content, "html.parser")

        # Find all divs with class "hot__item" and extract href from <a> tags
        for item in page_soup.find_all("div", class_="hot__item"):
            anchor_tag = item.find("a", href=True)
            if anchor_tag:
                property_url = urljoin(base_url, anchor_tag["href"])
                all_property_urls.add(property_url)

    return all_property_urls

# Function to scrape data from each property URL
def scrape_property_data(property_urls):
    property_data = []

    for property_url in property_urls:
        property_response = requests.get(property_url)
        property_soup = BeautifulSoup(property_response.content, "html.parser")

        # Extract JSON data from <script id="jsdata"> tag
        script_tag = property_soup.find("script", id="jsdata")
        if script_tag:
            script_text = script_tag.string.strip()
            json_str = re.search(r"window\.data\s*=\s*({.*});", script_text)
            if json_str:
                json_data = json.loads(json_str.group(1))
                
                # Extract required details
                advert = json_data.get("advert", {})
                map_data = advert.get("map", {})
                address_data = advert.get("address", {})

                name = advert.get("title")
                address = f"{address_data.get('city')}, {address_data.get('street')} {address_data.get('house_num')}"
                price = advert.get("price")
                latitude = map_data.get("lat")
                longitude = map_data.get("lon")
                property_type = advert.get("categoryAlias")
                transaction_type = advert.get("sectionAlias")
                area = advert.get("square")
                characteristics = f"Rooms: {advert.get('rooms')}"

                # Scrape description from <meta name="description">
                meta_description_tag = property_soup.find("meta", attrs={"name": "description"})
                description = meta_description_tag["content"] if meta_description_tag else "No description available"

                details_div = property_soup.find("div", class_="offer__short-description")
                property_details = {}
                if details_div:
                    for item in details_div.find_all("div", class_="offer__info-item"):
                        title = item.find("div", class_="offer__info-title").text.strip()
                        value = item.find("div", class_="offer__advert-short-info").text.strip()
                        property_details[title] = value

                # Append scraped data to property_data list
                property_data.append({
                    "URL": property_url,
                    "Name": name,
                    "Address": address,
                    "Price": price,
                    "Description": description,
                    "Latitude": latitude,
                    "Longitude": longitude,
                    "Property Type": property_type,
                    "Transaction Type": transaction_type,
                    "Area": area,
                    "Characteristics": characteristics,
                    "Properties": property_details
                })
            else:
                print(f"Failed to extract JSON from script content on {property_url}")
        else:
            print(f"No 'jsdata' script tag found on {property_url}")

    return property_data

# Main function to scrape URLs and data
def main():
    base_url = "https://krisha.kz/arenda/garazhi/"
    property_urls = scrape_property_urls(base_url)

    if property_urls:
        print(f"Total unique property URLs found: {len(property_urls)}")
        property_data = scrape_property_data(property_urls)
        print(property_data)

        # Convert data into a DataFrame and save to Excel
        df = pd.DataFrame(property_data)
        parsed_url = urlparse(base_url)
        safe_url_name = parsed_url.netloc.replace(".", "_") + parsed_url.path.replace("/", "_")
        excel_filename = f"{safe_url_name}.xlsx"

        # Save Excel file to the 'artifacts' directory
        os.makedirs("artifacts", exist_ok=True)
        excel_path = os.path.join("artifacts", excel_filename)
        df.to_excel(excel_path, index=False)
        print(f"Data saved to {excel_path}")
    else:
        print("No property URLs found.")

# Run the main function
if __name__ == "__main__":
    main()
