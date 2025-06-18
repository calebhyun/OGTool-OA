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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re
import csv

# Silence the webdriver-manager logger
logging.getLogger('webdriver_manager').setLevel(logging.WARNING)

logging.basicConfig(filename='log.txt', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s', filemode='w')

def truncate_content(text, max_length=200):
    """Truncates text to a max length, adding an ellipsis."""
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text

def get_driver(url):
    """Gets a selenium driver for a given URL."""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--log-level=3')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])

    # Check if running on Heroku
    if "GOOGLE_CHROME_BIN" in os.environ:
        options.binary_location = os.environ.get("GOOGLE_CHROME_BIN")
        chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
        # Add a log to confirm the path is being read
        print(f"Heroku ChromeDriver Path: {chromedriver_path}")
        service = ChromeService(executable_path=chromedriver_path, log_output=os.devnull)
    else:
        # Local development: import and use webdriver-manager only here
        from webdriver_manager.chrome import ChromeDriverManager
        service = ChromeService(ChromeDriverManager().install(), log_output=os.devnull)
    
    driver = webdriver.Chrome(service=service, options=options)
    driver.get(url)
    try:
        # Wait for body to be present, max 2 seconds.
        WebDriverWait(driver, 2).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
    except Exception:
        # If it times out, just continue. The page might be very slow or simple.
        pass
    return driver

def scrape_sitemap(url):
    """Finds and scrapes URLs from a sitemap. Yields logs, returns items."""
    items = []
    parsed_url = urlparse(url)
    sitemap_url = urlunparse((parsed_url.scheme, parsed_url.netloc, 'sitemap.xml', '', '', ''))
    
    yield f"Trying to find sitemap at: {sitemap_url}"
    yield "(This may take up to 2 seconds if the sitemap doesn't exist...)"
    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.get(sitemap_url, timeout=2)
        response.raise_for_status()
        
        sitemap_soup = BeautifulSoup(response.content, 'xml')
        urls = [loc.text for loc in sitemap_soup.find_all('loc')]
        
        yield f"Found {len(urls)} URLs in sitemap."
        
        # Filter for blog-like URLs from the sitemap
        blog_urls = [u for u in urls if '/blog/' in u or '/post/' in u or '/article/' in u or re.search(r'/\\d{4}/\\d{2}/', u)]

        for blog_url in blog_urls:
            try:
                yield f"Scraping from sitemap URL: {blog_url}"
                page_content = scraper.get(blog_url, timeout=2).text
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
                yield f"Could not process sitemap URL {blog_url}. Reason: {e}"

    except Exception as e:
        yield f"Could not find or process sitemap.xml. Reason: {e}"

    return items


def scrape_url(url, use_selenium=True):
    """
    Scrapes a single URL. 
    First attempts a static scrape. If no articles are found, 
    falls back to Selenium if use_selenium is True.
    Yields logs, returns items.
    """
    items = []

    # --- Step 1: Try Sitemap ---
    yield "Phase 1: Attempting to scrape sitemap..."
    sitemap_scraper = scrape_sitemap(url)
    sitemap_items = []
    try:
        while True:
            log = next(sitemap_scraper)
            if log: yield log
    except StopIteration as e:
        sitemap_items = e.value
    except Exception as e:
        yield f"An error occurred during sitemap scrape: {e}"

    if sitemap_items:
        items.extend(sitemap_items)
        # If sitemap is found and has content, we can often just stop here.
        yield "Sitemap found and processed. Assuming it's comprehensive."
        unique_items = {item['source_url']: item for item in items}.values()
        return list(unique_items)
    
    yield "Sitemap not found or empty."

    # --- Step 2: Static Scrape (No Selenium) ---
    yield "Phase 2: Attempting static scrape..."
    yield "(This may take up to 2 seconds...)"
    processed_urls = set()
    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, timeout=2)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        a_tags = [{'href': a.get('href')} for a in soup.find_all('a') if a.get('href')]
        
        yield f"Found {len(a_tags)} links via static scrape. Processing..."

        for a_tag in a_tags:
            # (Logic for processing links is the same as before)
            link = a_tag['href']
            full_url = urljoin(url, link)
            parsed_url = urlparse(full_url)
            clean_url = parsed_url._replace(query="", fragment="").geturl()

            yield f"Processing link: {clean_url}"

            if clean_url in processed_urls or urlparse(url).netloc != parsed_url.netloc or clean_url == url:
                continue

            # Looser path segment check: check for at least 1 segment and a dash, OR just /articles/
            path_segments = parsed_url.path.strip('/').split('/')
            if not ( (len(path_segments) >= 1 and '-' in path_segments[-1]) or 'articles' in path_segments ):
                continue
            
            processed_urls.add(clean_url)
            try:
                page_content = scraper.get(clean_url, timeout=2).text
                content = trafilatura.extract(page_content)
                if content and len(content) > 200:
                    yield f"Found article (static): {clean_url}"
                    title_soup = BeautifulSoup(page_content, 'html.parser')
                    title = title_soup.title.string if title_soup.title else "No Title Found"
                    items.append({
                        "title": title,
                        "content": md(content, heading_style="ATX"),
                        "content_type": "blog", "source_url": clean_url,
                        "author": "", "user_id": ""
                    })
            except Exception as e:
                yield f"Could not process static link {clean_url}. Reason: {e}"

    except Exception as e:
        yield f"Static scrape failed for base URL {url}. Reason: {e}"

    # --- Step 3: Fallback to Selenium if needed ---
    if not items and use_selenium:
        yield "Phase 3: Static scrape yielded no results. Falling back to Selenium..."
        driver = None
        try:
            yield "Initializing web driver..."
            driver = get_driver(url)
            yield "Web driver initialized successfully."

            article_urls_from_selenium = set()
            
            # Get standard <a> tag links first
            initial_links = driver.find_elements(By.TAG_NAME, 'a')
            for link in initial_links:
                href = link.get_attribute('href')
                if href:
                    article_urls_from_selenium.add(href)
            
            # New logic for SPAs: find clickable elements, click them, get URL
            try:
                article_elements_selector = "div[style*='cursor:pointer']"
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, article_elements_selector))
                )
                
                num_articles = len(driver.find_elements(By.CSS_SELECTOR, article_elements_selector))
                yield f"Found {num_articles} potential JavaScript-driven article links. Discovering URLs..."

                for i in range(num_articles):
                    # Re-find elements each time to avoid staleness
                    current_elements = driver.find_elements(By.CSS_SELECTOR, article_elements_selector)
                    if i >= len(current_elements):
                        break 
                    
                    element_to_click = current_elements[i]
                    
                    try:
                        driver.execute_script("arguments[0].scrollIntoView(true);", element_to_click)
                        time.sleep(0.5)
                        element_to_click.click()
                    except Exception:
                        try:
                            driver.execute_script("arguments[0].click();", element_to_click)
                        except Exception as js_click_error:
                            yield f"Could not click element {i}. Skipping. Error: {js_click_error}"
                            continue

                    WebDriverWait(driver, 10).until(lambda d: d.current_url != url)
                    discovered_url = driver.current_url
                    if discovered_url not in article_urls_from_selenium:
                        yield f"Discovered URL: {discovered_url}"
                        article_urls_from_selenium.add(discovered_url)
                    
                    driver.back()
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, article_elements_selector))
                    )
            except Exception as e:
                yield f"Could not execute JavaScript link discovery. Proceeding with standard links. Reason: {e}"

            a_tags = [{'href': u} for u in article_urls_from_selenium]
            driver.quit() 
            driver = None 

            yield f"Found {len(a_tags)} links via Selenium. Processing..."
            scraper = cloudscraper.create_scraper() # Reuse fast scraper for processing

            for a_tag in a_tags:
                link = a_tag.get('href')

                # Add defensive check for None links
                if not link:
                    yield "[Debug] Skipping a None link found in a_tags."
                    continue
                
                yield f"[Debug] Processing Selenium link: {link}"

                full_url = urljoin(url, link)
                parsed_url = urlparse(full_url)
                clean_url = parsed_url._replace(query="", fragment="").geturl()

                if clean_url in processed_urls or urlparse(url).netloc != parsed_url.netloc or clean_url == url:
                    continue

                path_segments = parsed_url.path.strip('/').split('/')
                if not ( (len(path_segments) >= 1 and '-' in path_segments[-1]) or 'articles' in path_segments ):
                    continue

                processed_urls.add(clean_url)
                try:
                    page_content = scraper.get(clean_url, timeout=15).text
                    content = trafilatura.extract(page_content)
                    if content and len(content) > 200:
                        yield f"Found article (Selenium): {clean_url}"
                        title_soup = BeautifulSoup(page_content, 'html.parser')
                        title = title_soup.title.string if title_soup.title else "No Title Found"
                        items.append({
                            "title": title, "content": md(content, heading_style="ATX"),
                            "content_type": "blog", "source_url": clean_url,
                            "author": "", "user_id": ""
                        })
                except Exception as e:
                    yield f"Could not process Selenium link {clean_url}. Reason: {e}"
        except Exception as e:
            yield f"Could not scrape {url} with Selenium. Reason: {e}"
        finally:
            if driver:
                driver.quit()
    elif not items and not use_selenium:
        yield "Phase 3: Static scrape yielded no results. Selenium is disabled. Stopping."

    # --- Final Step: Deduplicate and Return ---
    yield "Scraping for this source complete. Deduplicating results..."
    unique_items = {item['source_url']: item for item in items}.values()
    return list(unique_items)


def scrape_pdf(file_path):
    """Scrapes a PDF file. Yields logs, returns items."""
    items = []
    yield f"Scraping PDF: {file_path}"
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
                "content": content, # PDF content is already text
                "content_type": "book",
                "source_url": "",
                "author": "",
                "user_id": ""
            })
    except Exception as e:
        yield f"Could not process PDF {file_path}. Reason: {e}"
    return items

def run_scraper(sources, team_id="aline123", use_selenium=True):
    """Main scraping logic. Yields logs and individual JSON items."""
    total_items_found = 0
    for s in sources:
        yield f"Scraping {s}..."
        scraper_gen = None
        if s.startswith('http://') or s.startswith('https://'):
            scraper_gen = scrape_url(s, use_selenium=use_selenium)
        elif os.path.isfile(s) and s.lower().endswith('.pdf'):
            scraper_gen = scrape_pdf(s)
        else:
            yield f"Unsupported source type for {s}. Skipping."
            continue

        if scraper_gen:
            items = []
            try:
                while True:
                    # This will yield logs from the sub-scraper
                    yield next(scraper_gen)
            except StopIteration as e:
                # The generator returns the items when it's done.
                items = e.value
            except Exception as e:
                yield f"A critical error occurred while processing {s}: {e}"
                continue
            
            if items:
                for item in items:
                    # Yield each found item as its own JSON message
                    yield f"___JSON_ITEM___{json.dumps(item)}"
                    total_items_found += 1
    
    yield f"Scraping complete. Found {total_items_found} total items. You can now download the results."

def main():
    """Main function to run the scraper."""
    parser = argparse.ArgumentParser(description="Scrape content from websites and PDFs into a knowledgebase format.")
    parser.add_argument("source", help="The URL of the website, path to a PDF file, or path to a CSV file of sources.")
    parser.add_argument("--team_id", default="aline123", help="The team ID for the knowledgebase.")
    parser.add_argument("--no-selenium", action="store_true", help="Disable the use of Selenium for scraping.")
    
    args = parser.parse_args()
    source = args.source
    team_id = args.team_id
    use_selenium = not args.no_selenium

    sources_to_scrape = []

    if source.lower().endswith('.csv'):
        print(f"Reading sources from {source}")
        with open(source, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                sources_to_scrape.append(row['url'])
    else:
        sources_to_scrape.append(source)
    
    # To see logs in console when running from command line
    for log in run_scraper(sources_to_scrape, team_id=team_id, use_selenium=use_selenium):
        # Don't print the JSON payload to the console, just the logs.
        if not log.startswith('___JSON_ITEM___'):
            print(log)

if __name__ == "__main__":
    main() 