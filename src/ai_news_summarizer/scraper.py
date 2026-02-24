import httpx
import trafilatura
from urllib.parse import urljoin, urldefrag
import lxml.html

class ProductLinkDetectedError(Exception):
    """Raised when a URL appears to be a product page rather than an article."""
    pass

class Scraper:
    """Fetches articles and extracts their clean main text."""
    
    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    async def fetch_and_extract(self, url: str) -> tuple[str, str, set[str]]:
        """
        Fetches the HTML of the URL and extracts the main text and links.
        Returns (raw_html, extracted_text, links).
        Raises httpx.HTTPError for connection issues.
        Raises ProductLinkDetectedError if it looks like a product page.
        """
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            raw_html = response.text
            
            # Use trafilatura to extract the main content
            extracted_text = trafilatura.extract(raw_html, include_links=True)
            
            # Extract links from the page
            found_urls = set()
            try:
                tree = lxml.html.fromstring(raw_html)
                # Convert relative links to absolute
                tree.make_links_absolute(base_url=url)
                for element, attribute, link, pos in tree.iterlinks():
                    if element.tag == "a":
                        # Remove URL fragments (#)
                        clean_link, _ = urldefrag(link)
                        if clean_link.startswith("http://") or clean_link.startswith("https://"):
                            found_urls.add(clean_link)
            except Exception:
                pass # If parsing fails, just return empty link set
            
            if not extracted_text:
                raise ProductLinkDetectedError(f"No meaningful article text found. Might be a product link: {url}")
            
            # Simple heuristic for product pages
            text_lower = extracted_text.lower()
            product_keywords = ["add to cart", "buy now", "pricing", "checkout"]
            
            # If it's short and contains product keywords
            if len(extracted_text) < 1000 and any(kw in text_lower for kw in product_keywords):
                 raise ProductLinkDetectedError(f"Product keywords found in short text: {url}")
                 
            return raw_html, extracted_text, found_urls
