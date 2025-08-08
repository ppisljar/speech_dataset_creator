import os
import subprocess
import asyncio
import aiohttp
import sys
import argparse
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, unquote

# Base URL for the podcast site
BASE_URL = 'https://podcasti.si/{podcast}/?page={page_num}'

# Function to fetch the HTML content of the page
async def fetch_page(session, url):
    async with session.get(url) as response:
        if response.status == 404:
            return None  # Return None for 404 errors to indicate end of pages
        response.raise_for_status()  # Raise an exception for other HTTP errors
        return await response.text()

# Function to extract MP3 links from a single page
def extract_mp3_links(page_html):
    soup = BeautifulSoup(page_html, 'html.parser')
    # Find all audio buttons with data-audio attribute
    mp3_urls = [button['data-audio'] for button in soup.find_all('button', {'data-audio': True})]
    return mp3_urls

# Function to sanitize URL and get the file name without query params
def get_filename_from_url(url):
    # Parse the URL to get the path
    parsed_url = urlparse(url)
    
    # Get the full path and decode URL-encoded characters
    decoded_path = unquote(parsed_url.path)
    
    # Extract just the filename from the path
    filename = os.path.basename(decoded_path)
    
    # Remove any query parameters (everything after '?')
    if '?' in filename:
        filename = filename.split('?')[0]
    
    # Replace any remaining slashes and other problematic characters with underscores
    filename = filename.replace('/', '_').replace('\\', '_')
    
    # Remove or replace other characters that might be problematic in filenames
    problematic_chars = ['<', '>', ':', '"', '|', '*']
    for char in problematic_chars:
        filename = filename.replace(char, '_')
    
    return filename

# Function to download the MP3 file using wget
def download_mp3(url, file_name, override=False):
    try:
        # Check if the file already exists unless override is True
        if not override and os.path.exists(file_name):
            print(f"Skipping {file_name}, already downloaded.")
            return

        # Use subprocess to call wget
        command = ['wget', url, '-O', file_name]
        subprocess.run(command, check=True)
        print(f"Downloaded: {file_name}")
    except subprocess.CalledProcessError as e:
        print(f"Error downloading {url}: {e}")

def generate_sequential_name(index):
    return f"pod_{index:05d}.mp3"

# Main function to scrape and download MP3s from all pages
async def get_podcasts(base_url, output_dir='./aidea', max_pages=100, use_custom_names=False, override=False):
    # Create the 'aidea' folder if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        file_index = 1
        # Loop through pages 1 to max_pages
        for page_num in range(1, max_pages + 1):
            page_url = BASE_URL.format(podcast=base_url, page_num=page_num)
            print(f"Fetching page {page_num}...")
            page_html = await fetch_page(session, page_url)
            
            # If page_html is None, it means we got a 404 - this is the last page
            if page_html is None:
                print(f"Reached the end (404 error on page {page_num}). Stopping.")
                break
                
            mp3_urls = extract_mp3_links(page_html)

            # Download each MP3 file found on the page
            for mp3_url in mp3_urls:
                if use_custom_names:
                    mp3_name = generate_sequential_name(file_index)
                    file_index += 1
                else:
                    # Get sanitized filename (without query parameters)
                    mp3_name = get_filename_from_url(mp3_url)
                mp3_path = os.path.join(output_dir, mp3_name)
                download_mp3(mp3_url, mp3_path, override=override)

# Run the main function
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Download podcasts.")
    parser.add_argument("podcast_name", help="Name of the podcast to download.")
    parser.add_argument("--name", action="store_true", help="Generate sequential names for saved files.")
    parser.add_argument("--override", action="store_true", help="Override existing files.")
    args = parser.parse_args()

    podcast_name = args.podcast_name
    output_dir = f'./{podcast_name}'

    print(f"Downloading podcasts from '{podcast_name}' to '{output_dir}' directory...")

    asyncio.run(get_podcasts(podcast_name, output_dir, use_custom_names=args.name, override=args.override))
