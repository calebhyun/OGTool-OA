import argparse
import requests
import cloudscraper
from bs4 import BeautifulSoup
import trafilatura
from markdownify import markdownify as md
import fitz  # PyMuPDF
import json
import os
from urllib.parse import urljoin, urlparse, urlunparse
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
import time
import re

logging.basicConfig(filename='log.txt', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s', filemode='w')

def get_driver(url):
    """Gets a selenium driver for a given URL."""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
    driver.get(url)
    time.sleep(5) # Reduced wait time now that we are more efficient
    return driver

def scrape_sitemap(url):
    """Finds and scrapes URLs from a sitemap."""
    items = []
    parsed_url = urlparse(url)
    sitemap_url = urlunparse((parsed_url.scheme, parsed_url.netloc, 'sitemap.xml', '', '', ''))
    
    logging.info(f"Trying to find sitemap at: {sitemap_url}")
    
    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.get(sitemap_url, timeout=15)
        response.raise_for_status()
        
        sitemap_soup = BeautifulSoup(response.content, 'xml')
        urls = [loc.text for loc in sitemap_soup.find_all('loc')]
        
        logging.info(f"Found {len(urls)} URLs in sitemap.")
        
        # Filter for blog-like URLs from the sitemap
        blog_urls = [u for u in urls if '/blog/' in u or '/post/' in u or re.search(r'/\d{4}/\d{2}/', u)]

        for blog_url in blog_urls:
            try:
                logging.info(f"Scraping from sitemap URL: {blog_url}")
                page_content = scraper.get(blog_url, timeout=15).text
                content = trafilatura.extract(page_content)
                if content and len(content) > 300:
                    title_soup = BeautifulSoup(page_content, 'html.parser')
                    title = title_soup.title.string if title_soup.title else "No Title Found"
                    items.append({
                        "title": title,
                        "content": md(content, heading_style="ATX"),
                        "content_type": "blog",
                        "source_url": blog_url,
                        "author": "",
                        "user_id": ""
                    })
            except Exception as e:
                logging.error(f"Could not process sitemap URL {blog_url}. Reason: {e}")

    except Exception as e:
        logging.info(f"Could not find or process sitemap.xml. Reason: {e}")

    return items


def scrape_url(url):
    """Scrapes a single URL or a blog index page."""
    items = []

    # First, try scraping the sitemap
    sitemap_items = scrape_sitemap(url)
    if sitemap_items:
        return sitemap_items

    # If sitemap fails or is empty, fall back to previous method
    logging.info("Sitemap not found or empty, falling back to dynamic/static scraping.")
    
    processed_urls = set()
    driver = None
    try:
        is_dynamic = 'quill.co' in url or 'substack.com' in url
        if is_dynamic:
            driver = get_driver(url)
            page_source = driver.page_source
            links = driver.find_elements(By.TAG_NAME, 'a')
            a_tags = [{'href': link.get_attribute('href')} for link in links if link.get_attribute('href')]
        else:
            scraper = cloudscraper.create_scraper()
            response = scraper.get(url, timeout=15)
            response.raise_for_status()
            page_source = response.text
            soup = BeautifulSoup(page_source, 'html.parser')
            a_tags = soup.find_all('a', href=True)

        for a_tag in a_tags:
            link = a_tag['href']
            full_url = urljoin(url, link)
            parsed_url = urlparse(full_url)
            clean_url = parsed_url._replace(query="", fragment="").geturl()

            if clean_url in processed_urls or urlparse(url).netloc != parsed_url.netloc or clean_url == url:
                continue

            if urlparse(url).path != "/" and not parsed_url.path.startswith(urlparse(url).path):
                continue
            
            processed_urls.add(clean_url)

            logging.info(f"Processing link: {clean_url}")
            try:
                page_content = None
                # Reuse selenium driver if it's already running
                if is_dynamic and driver:
                    driver.get(clean_url)
                    time.sleep(5)
                    page_content = driver.page_source
                else:
                    # Fallback to cloudscraper for non-dynamic sites or if driver isn't running
                    scraper = cloudscraper.create_scraper()
                    page_content = scraper.get(clean_url, timeout=15).text
                
                content = trafilatura.extract(page_content)

                if content and len(content) > 200: # Lowered threshold
                    logging.info(f"Found article: {clean_url} | Length: {len(content)}")
                    title_soup = BeautifulSoup(page_content, 'html.parser')
                    title = title_soup.title.string if title_soup.title else "No Title Found"
                    
                    items.append({
                        "title": title,
                        "content": md(content, heading_style="ATX"),
                        "content_type": "blog",
                        "source_url": clean_url,
                        "author": "",
                        "user_id": ""
                    })
            except Exception as e:
                logging.error(f"Could not process link {clean_url}. Reason: {e}")
        
    except Exception as e:
        logging.error(f"Could not scrape {url}. Reason: {e}")
    finally:
        if driver:
            driver.quit()

    # Remove duplicates
    unique_items = {item['source_url']: item for item in items}.values()
    return list(unique_items)


def scrape_pdf(file_path):
    """Scrapes a PDF file."""
    items = []
    print(f"Scraping PDF: {file_path}")
    try:
        doc = fitz.open(file_path)
        content = ""
        # Scrape first 8 chapters (or pages, as PDFs don't have chapter markers)
        for page_num in range(min(8, doc.page_count)):
            page = doc.load_page(page_num)
            content += page.get_text()
        
        if content:
            items.append({
                "title": os.path.basename(file_path),
                "content": content, # PDF content is already text, no need for markdown conversion
                "content_type": "book",
                "source_url": "",
                "author": "",
                "user_id": ""
            })
    except Exception as e:
        print(f"Could not process PDF {file_path}. Reason: {e}")
    return items

def main():
    """Main function to run the scraper."""
    parser = argparse.ArgumentParser(description="Scrape content from websites and PDFs into a knowledgebase format.")
    parser.add_argument("source", help="The URL of the website or path to the PDF file.")
    parser.add_argument("--team_id", default="aline123", help="The team ID for the knowledgebase.")
    parser.add_argument("-o", "--output", default="output.json", help="The name of the output JSON file.")
    
    args = parser.parse_args()
    source = args.source
    team_id = args.team_id
    output_file = args.output

    all_items = []

    if source.startswith('http://') or source.startswith('https://'):
        all_items.extend(scrape_url(source))
    elif os.path.isfile(source) and source.lower().endswith('.pdf'):
        all_items.extend(scrape_pdf(source))
    else:
        print("Unsupported source. Please provide a valid URL or a path to a PDF file.")
        return

    output = {
        "team_id": team_id,
        "items": all_items
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Scraping complete. Output saved to {output_file}")

if __name__ == "__main__":
    main() 