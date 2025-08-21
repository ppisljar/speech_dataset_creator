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

# Function to extract total number of pages from pagination
def extract_total_pages(page_html):
    soup = BeautifulSoup(page_html, 'html.parser')
    # Look for the pagination element with "Stran 1 od XX" pattern
    current_page_li = soup.find('li', class_='current')
    if current_page_li:
        text = current_page_li.get_text(strip=True)
        # Parse text like "Si na strani Stran 1 od 11" to extract the total pages
        if 'od' in text:
            try:
                # Split by 'od' and get the number after it
                total_pages = int(text.split('od')[-1].strip())
                return total_pages
            except (ValueError, IndexError):
                print(f"Could not parse total pages from: {text}")
                return None
    return None

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
    
    # Keep the original extension for downloading, but we'll convert to WAV later
    return filename

# Function to convert M4A to WAV using ffmpeg
def convert_m4a_to_wav(input_file, output_file):
    try:
        command = ['ffmpeg', '-i', input_file, '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', output_file, '-y']
        subprocess.run(command, check=True, capture_output=True)
        print(f"Converted {input_file} to {output_file}")
        # Remove the original M4A file after successful conversion
        os.remove(input_file)
        print(f"Removed original file: {input_file}")
    except subprocess.CalledProcessError as e:
        print(f"Error converting {input_file} to WAV: {e}")
    except OSError as e:
        print(f"Error removing {input_file}: {e}")

# Function to download the MP3 file using wget
def download_mp3(url, file_name, override=False):
    try:
        # Determine the final WAV filename
        if file_name.lower().endswith('.wav') or file_name.lower().endswith('.mp3'):
            final_wav_file = file_name
        else:
            # Change extension to .wav for final output
            final_wav_file = file_name.rsplit('.', 1)[0] + '.wav'
        
        # Check if the final WAV file already exists unless override is True
        if not override and os.path.exists(final_wav_file):
            print(f"Skipping {final_wav_file}, already downloaded.")
            return

        # Determine original filename based on URL to preserve extension for download
        original_filename = get_filename_from_url(url)
        if not original_filename:
            # Fallback if we can't determine extension from URL
            original_filename = file_name
        
        # Download with original extension
        temp_file = os.path.join(os.path.dirname(file_name), original_filename)
        
        # Use subprocess to call wget
        command = ['wget', url, '-O', temp_file]
        subprocess.run(command, check=True)
        print(f"Downloaded: {temp_file}")
        
        # Convert to WAV if needed
        if temp_file.lower().endswith('.m4a'):
            convert_m4a_to_wav(temp_file, final_wav_file)
        elif temp_file.lower().endswith('.mp3'):
            convert_mp3_to_wav(temp_file, final_wav_file)
        else:
            # If it's already WAV or unknown format, just rename
            if temp_file != final_wav_file:
                os.rename(temp_file, final_wav_file)
                print(f"Renamed {temp_file} to {final_wav_file}")
            
    except subprocess.CalledProcessError as e:
        print(f"Error downloading {url}: {e}")

# Function to convert MP3 to WAV using ffmpeg  
def convert_mp3_to_wav(input_file, output_file):
    try:
        command = ['ffmpeg', '-i', input_file, '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', output_file, '-y']
        subprocess.run(command, check=True, capture_output=True)
        print(f"Converted {input_file} to {output_file}")
        # Remove the original MP3 file after successful conversion
        os.remove(input_file)
        print(f"Removed original file: {input_file}")
    except subprocess.CalledProcessError as e:
        print(f"Error converting {input_file} to WAV: {e}")
    except OSError as e:
        print(f"Error removing {input_file}: {e}")

def generate_sequential_name(index):
    return f"pod_{index:05d}.wav"

# Main function to scrape and download MP3s from all pages
async def get_podcasts(base_url, output_dir='./aidea', max_pages=10, use_custom_names=False, override=False):
    # Create the 'aidea' folder if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        file_index = 1
        total_pages = None
        
        # First, fetch the first page to determine total number of pages
        first_page_url = BASE_URL.format(podcast=base_url, page_num=1)
        print(f"Fetching first page to determine total number of pages...")
        first_page_html = await fetch_page(session, first_page_url)
        
        if first_page_html is None:
            print("Error: Could not fetch the first page.")
            return
            
        # Extract total pages from the first page
        total_pages = extract_total_pages(first_page_html)
        if total_pages:
            print(f"Found {total_pages} total pages to process.")
            # Use the actual total pages, but don't exceed max_pages if specified
            pages_to_process = min(total_pages, max_pages)
        else:
            print(f"Could not determine total pages, using max_pages={max_pages} as fallback.")
            pages_to_process = max_pages
        
        # Process the first page (we already have its HTML)
        print(f"Processing page 1...")
        mp3_urls = extract_mp3_links(first_page_html)
        
        # Download each MP3 file found on the first page
        for mp3_url in mp3_urls:
            if use_custom_names:
                file_name = generate_sequential_name(file_index)
                file_index += 1
            else:
                # Get sanitized filename and ensure WAV extension for output
                original_name = get_filename_from_url(mp3_url)
                if original_name.lower().endswith(('.mp3', '.m4a')):
                    file_name = original_name.rsplit('.', 1)[0] + '.wav'
                else:
                    file_name = original_name + '.wav'
            file_path = os.path.join(output_dir, file_name)
            download_mp3(mp3_url, file_path, override=override)

        # Loop through remaining pages (2 to total_pages)
        for page_num in range(2, pages_to_process + 1):
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
                    file_name = generate_sequential_name(file_index)
                    file_index += 1
                else:
                    # Get sanitized filename and ensure WAV extension for output
                    original_name = get_filename_from_url(mp3_url)
                    if original_name.lower().endswith(('.mp3', '.m4a')):
                        file_name = original_name.rsplit('.', 1)[0] + '.wav'
                    else:
                        file_name = original_name + '.wav'
                file_path = os.path.join(output_dir, file_name)
                download_mp3(mp3_url, file_path, override=override)

# New function to download individual URLs
async def download_urls(urls, output_dir='./raw', override=False):
    """Download individual URLs to the specified directory"""
    os.makedirs(output_dir, exist_ok=True)
    
    downloaded_files = []
    failed_files = []
    
    for url in urls:
        url = url.strip()
        if not url:
            continue
            
        try:
            print(f"Downloading {url}...")
            
            # Get sanitized filename and ensure WAV extension for output
            original_name = get_filename_from_url(url)
            if original_name.lower().endswith(('.mp3', '.m4a')):
                file_name = original_name.rsplit('.', 1)[0] + '.wav'
            else:
                file_name = original_name + '.wav' if not original_name.lower().endswith('.wav') else original_name
            
            file_path = os.path.join(output_dir, file_name)
            
            # Check if file exists and skip if not overriding
            if not override and os.path.exists(file_path):
                print(f"Skipping {file_name}, already exists.")
                downloaded_files.append(file_name)
                continue
            
            download_mp3(url, file_path, override=override)
            downloaded_files.append(file_name)
            print(f"Successfully downloaded: {file_name}")
            
        except Exception as e:
            print(f"Failed to download {url}: {str(e)}")
            failed_files.append({"url": url, "error": str(e)})
    
    return {
        "downloaded": downloaded_files,
        "failed": failed_files,
        "total": len(urls)
    }

# Run the main function
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Download podcasts.")
    parser.add_argument("podcast_name", help="Name of the podcast to download.")
    parser.add_argument("--name", action="store_true", help="Generate sequential names for saved files.")
    parser.add_argument("--override", action="store_true", help="Override existing files.")
    args = parser.parse_args()

    podcast_name = args.podcast_name
    output_dir = f'./projects/{podcast_name}/raw'

    print(f"Downloading podcasts from '{podcast_name}' to '{output_dir}' directory...")

    asyncio.run(get_podcasts(podcast_name, output_dir, use_custom_names=args.name, override=args.override))
