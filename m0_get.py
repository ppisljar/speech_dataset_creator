import os
import subprocess
import asyncio
import aiohttp
import sys
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

# Base URL for the podcast site
BASE_URL = 'https://podcasti.si/{podcast}/?page={page_num}'

# Function to fetch the HTML content of the page
async def fetch_page(session, url):
    async with session.get(url) as response:
        return await response.text()

# Function to extract MP3 links from a single page
def extract_mp3_links(page_html):
    soup = BeautifulSoup(page_html, 'html.parser')
    # Find all audio buttons with data-audio attribute
    mp3_urls = [button['data-audio'] for button in soup.find_all('button', {'data-audio': True})]
    return mp3_urls

# Function to sanitize URL and get the file name without query params
def get_filename_from_url(url):
    parsed_url = urlparse(url)
    filename = os.path.basename(parsed_url.path)  # Get the filename from the URL path
    # Remove any query parameters (everything after '?')
    if '?' in filename:
        filename = filename.split('?')[0]
    return filename

# Function to download the MP3 file using wget
def download_mp3(url, file_name):
    try:
        # Check if the file already exists
        if os.path.exists(file_name):
            print(f"Skipping {file_name}, already downloaded.")
            return
        
        
        # Use subprocess to call wget
        command = ['wget', url, '-O', file_name]
        subprocess.run(command, check=True)
        print(f"Downloaded: {file_name}")
    except subprocess.CalledProcessError as e:
        print(f"Error downloading {url}: {e}")

# Main function to scrape and download MP3s from all pages
async def get_podcasts(base_url, output_dir='./aidea', max_pages=10):
    # Create the 'aidea' folder if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        # Loop through pages 1 to 10
        for page_num in range(1, max_pages + 1):
            page_url = BASE_URL.format(podcast=base_url, page_num=page_num)
            print(f"Fetching page {page_num}...")
            page_html = await fetch_page(session, page_url)
            mp3_urls = extract_mp3_links(page_html)
            
            # Download each MP3 file found on the page
            for mp3_url in mp3_urls:
                # Get sanitized filename (without query parameters)
                mp3_name = get_filename_from_url(mp3_url)
                mp3_path = os.path.join(output_dir, mp3_name)
                download_mp3(mp3_url, mp3_path)

# Run the main function
if __name__ == '__main__':
    # Check if podcast name is provided as command line argument
    if len(sys.argv) != 2:
        print("Usage: python m0_get.py <podcast_name>")
        print("Example: python m0_get.py aidea")
        sys.exit(1)
    
    podcast_name = sys.argv[1]
    output_dir = f'./{podcast_name}'
    
    print(f"Downloading podcasts from '{podcast_name}' to '{output_dir}' directory...")
    asyncio.run(get_podcasts(podcast_name, output_dir))
