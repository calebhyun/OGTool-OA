# Content Scraper for Knowledgebase
TODO: 
frontend
api endpoint
more testing on different blogs 

This project is a scalable content scraper designed to pull technical knowledge from various sources (blogs, guides, books) and format it into a JSON structure for a knowledgebase. It was built to be a reusable and extendable tool, avoiding custom code for specific websites.

## Features

- **Scalable Web Scraping**: Can scrape articles from various blog platforms and websites without site-specific code.
- **Dynamic Content Handling**: Uses Selenium to render JavaScript-heavy sites (like Substack) to access dynamically loaded content.
- **Sitemap Discovery**: Attempts to find and parse `sitemap.xml` for efficient discovery of all pages on a site.
- **PDF Scraping**: Can extract text from PDF files, with an option to limit the number of pages.
- **Markdown Conversion**: Converts extracted HTML content into clean Markdown.
- **Robust Error Handling**: Manages anti-scraping measures and logs errors for debugging.

## Technical Stack

- **Python 3**: The core language for the scraper.
- **Trafilatura**: A powerful library for extracting the main content and metadata from a web page. This is the key to the scraper's scalability, as it intelligently finds the main article text without needing manual configuration of HTML tags.
- **BeautifulSoup4**: Used for parsing HTML and XML (for sitemaps).
- **Selenium & WebDriver Manager**: Used to control a headless browser to render JavaScript on dynamic single-page applications (SPAs), allowing the scraper to see content that isn't in the initial HTML source.
- **Cloudscraper**: A library to bypass Cloudflare's anti-bot protection, making requests appear more like they are coming from a real browser.
- **PyMuPDF (fitz)**: A high-performance library for PDF processing, used here to extract text content.
- **Markdownify**: A library to convert the scraped HTML content into Markdown.

## How to Use

### 1. Setup

First, clone the repository and install the required dependencies from `requirements.txt`:

```bash
git clone <repository-url>
cd <repository-directory>
pip install -r requirements.txt
```

### 2. Running the Scraper

You can run the scraper from the command line, providing the source URL or the path to a local PDF file. The script will print its progress to the console and save a detailed log to `log.txt`.

**Syntax:**
```bash
python scraper.py <source> [options]
```

**Arguments:**
- `source`: The URL of the website/blog or the local path to a PDF file.
- `--team_id`: (Optional) The team ID for the output. Defaults to `aline123`.
- `-o`, `--output`: (Optional) The name of the output JSON file. Defaults to `output.json`.

**Examples:**

- **Scrape a blog index page:**
  ```bash
  python scraper.py https://interviewing.io/blog
  ```
- **Scrape a Substack blog:**
  ```bash
  python scraper.py https://shreycation.substack.com
  ```
- **Scrape a PDF file (first 8 pages):**
  ```bash
  python scraper.py /path/to/your/book.pdf
  ```
- **Scrape a blog that requires JavaScript:**
  ```bash
  python scraper.py https://quill.co/blog
  ```
  *(Note: See limitations below regarding this specific site)*

### 3. Output

The scraper will generate a JSON file (e.g., `output.json`) in the specified format:

```json
{
  "team_id": "aline123",
  "items": [
    {
      "title": "Item Title",
      "content": "Markdown content",
      "content_type": "blog|book|...",
      "source_url": "optional-url",
      "author": "",
      "user_id": ""
    }
  ]
}
```

## Thinking Process & Architecture

The primary goal was to build a *scalable* and *reusable* scraper, as requested in the assignment. This meant intentionally avoiding solutions that would require writing custom code for each new data source. The development process was iterative, adapting to the challenges presented by different websites.

1.  **Initial Approach & The Scalability Trap**: A naive approach would be to use `requests` to fetch HTML and `BeautifulSoup` to parse it, writing custom rules to find content (e.g., find all `<h1>` tags for titles, `<p>` for content). I recognized this as the "trap" mentioned in the assignment. This method is brittle; it would break with any website redesign and would require a new set of rules for every new customer.

2.  **Generic Content Extraction with `trafilatura`**: To solve the scalability problem, I chose `trafilatura`. This library is the core of the scraper's intelligence. It analyzes the structure of a webpage and uses heuristics to extract the main article text, title, and other metadata, without needing any site-specific selectors. This decision immediately made the scraper compatible with a vast number of websites.

3.  **Bypassing Anti-Scraping with `cloudscraper`**: Early tests on sites like `interviewing.io` resulted in `403 Forbidden` errors. This indicated the presence of anti-bot measures like Cloudflare. I integrated the `cloudscraper` library, which modifies request headers to mimic a real web browser, successfully bypassing these initial hurdles.

4.  **Handling the Modern Web with `selenium`**: The next challenge was modern Single-Page Applications (SPAs) like Substack and `quill.co/blog`. These sites load their content with JavaScript after the initial page load. A simple HTTP request only sees an empty HTML shell. To handle this, I integrated `selenium` and `webdriver-manager`. `selenium` controls a headless Chrome browser to fully render the page, executing all JavaScript. This allows the scraper to see the page exactly as a user does, providing access to the dynamically loaded content.

5.  **Efficient Link Discovery with Sitemaps**: To reliably find all articles on a site without manually crawling every link, I added a `sitemap.xml` discovery phase. Sitemaps are designed for search engines and provide a direct, comprehensive list of a site's URLs. The scraper now checks for a sitemap first, which is a much more efficient and robust method for discovering content. If a sitemap isn't found, it falls back to the dynamic crawling method.

6.  **Performance Optimization**: The initial `selenium` implementation was slow because it launched a new browser for every link it followed. I refactored the code to reuse a single browser instance when scraping a dynamic site, which significantly improved performance.

7.  **PDF Handling**: For offline content like Aline's book, I used `PyMuPDF` to extract text from PDF files. It's efficient and handles the requirement of chunking the content (by limiting the scrape to the first 8 pages).

8.  **Graceful Failure and Acknowledging Limits**: The struggle with `quill.co/blog` was an important part of the process. After multiple attempts with increasingly sophisticated techniques, it became clear that the site uses advanced anti-scraping measures. Instead of building a fragile, site-specific hack (which would violate the project's core principle), I chose to document this as a known limitation. A truly scalable tool must recognize when a target is explicitly hostile to its operation and fail gracefully rather than becoming a collection of custom patches.

This iterative process of identifying a problem, selecting the right tool, and refining the approach resulted in a robust, scalable, and easy-to-use scraper that fulfills the assignment's requirements.

## Known Limitations

- **`quill.co/blog`**: This site proved particularly challenging. It appears to use advanced anti-scraping techniques that even `selenium` could not reliably bypass during development. The scraper currently cannot extract the individual blog posts from this site. This is a good example of a site that would likely require a more specialized (and brittle) scraping solution, which was intentionally avoided in this project to maintain scalability.
- **Performance on Dynamic Sites**: While `selenium` is powerful, it is inherently slower than static HTML parsing because it needs to launch and control a full web browser. The scraper has been optimized to reuse a single browser instance when scraping multiple links from the same dynamic site to mitigate this.
- **PDF Content Structure**: The PDF scraper extracts raw text content. It does not currently interpret complex layouts, tables, or images within the PDF. For the provided task, it is set to extract the first 8 pages, simulating the first 8 chapters of a book.

This project successfully addresses the core problem of importing technical knowledge into a knowledgebase in a scalable way, keeping the end-user experience simple and effective. 
