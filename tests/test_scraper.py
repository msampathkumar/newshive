import pytest
import respx
import httpx
from ai_news_summarizer.scraper import Scraper, ProductLinkDetectedError

@pytest.fixture
def mock_html():
    return """
    <!DOCTYPE html>
    <html>
        <head><title>Test Blog Post</title></head>
        <body>
            <header>
                <nav class="navigation menu">Menu Items Here</nav>
            </header>
            <main>
                <article>
                    <h1>An Artificial Intelligence Breakthrough</h1>
                    <p>Google Cloud today announced new Gemma capabilities.</p>
                    <p>This is expected to help developers worldwide. It is a very long text indeed to make sure trafilatura thinks this is the main content of the page, full of many words about how awesome this new technology is for developers. Here is even more text because trafilatura requires a certain density of text to consider it article content.</p>
                    <p>And even more content to be absolutely sure.</p>
                </article>
            </main>
            <footer class="footer">Copyright 2026. All rights reserved. Follow us on social media.</footer>
        </body>
    </html>
    """

@pytest.fixture
def mock_product_html():
    return """
    <html>
        <head><title>Buy Now - Super App</title></head>
        <body>
            <div class="product-page">
                <h1>Super App - Enterprise Edition</h1>
                <button>Add to Cart</button>
                <p>Buy our software!</p>
            </div>
        </body>
    </html>
    """

@respx.mock
@pytest.mark.asyncio
async def test_scrape_valid_article(mock_html):
    url = "https://example.com/blog/ai-breakthrough"
    respx.get(url).respond(status_code=200, text=mock_html)
    
    scraper = Scraper()
    raw_html, text, links = await scraper.fetch_and_extract(url)
    
    assert raw_html == mock_html
    assert "Google Cloud today announced new Gemma capabilities." in text
    assert "Menu Items Here" not in text # Trafilatura should remove nav
    assert "Copyright 2026" not in text # Trafilatura should remove footer

@respx.mock
@pytest.mark.asyncio
async def test_scrape_product_link_detection(mock_product_html):
    url = "https://example.com/products/super-app"
    respx.get(url).respond(status_code=200, text=mock_product_html)
    
    scraper = Scraper()
    
    with pytest.raises(ProductLinkDetectedError):
        await scraper.fetch_and_extract(url)

@respx.mock
@pytest.mark.asyncio
async def test_fetch_error_handling():
    url = "https://example.com/404"
    respx.get(url).respond(status_code=404)
    
    scraper = Scraper()
    
    with pytest.raises(httpx.HTTPStatusError):
        await scraper.fetch_and_extract(url)
