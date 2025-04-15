from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
import time

from utils import logger, random_delay
from driver_setup import handle_modals_and_cookies

def scrape_vinted_search(driver, query, max_items=5, catalog_id=None):
    """
    Extracts newest items from Vinted search results
    
    Args:
        driver: Selenium WebDriver instance
        query: Search query string
        max_items: Maximum items to return
        catalog_id: Vinted catalog ID (optional)
        
    Returns:
        list: List of dictionaries with item details
    """
    # Format query for URL (replace spaces with +)
    formatted_query = query.replace(" ", "+")
    
    # Get current timestamp in seconds
    current_time = int(time.time())
    
    # Create URL with the newest items first and personalization disabled
    base_url = f"https://www.vinted.pl/catalog?search_text={formatted_query}&time={current_time}&disabled_personalization=true&page=1&order=newest_first"
    
    # Add catalog filter only if specified
    if catalog_id:
        base_url += f"&catalog[]={catalog_id}"
        
    logger.info(f"Navigating to: {base_url}")
    
    # Navigate to the search page
    driver.get(base_url)
    
    # Initial page load check
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        logger.info("Page loaded successfully")
    except TimeoutException:
        logger.error("Page failed to load completely")
        return []

    # Handle cookies
    handle_modals_and_cookies(driver)
    
    # Wait for main content - simplified to just look for the feed grid
    try:
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "div.feed-grid"))
        )
        logger.info("Feed grid found")
    except Exception:
        logger.warning("Feed grid not found with expected selector")
    
    # Wait a moment for the page to fully load
    time.sleep(2)
    
    # Look for grid items - sticking with what works
    item_selector = "div.feed-grid__item[data-testid='grid-item']"
    try:
        items = driver.find_elements(By.CSS_SELECTOR, item_selector)
        logger.info(f"Found {len(items)} items with selector: {item_selector}")
    except Exception as e:
        logger.warning(f"Error finding items with selector {item_selector}: {e}")
        items = []
    
    # Parse items with BeautifulSoup - this is the approach that works in your original code
    parsed_items = []
    if items:
        logger.info(f"Processing {min(len(items), max_items)} items from Selenium results")
        for idx, item in enumerate(items[:max_items]):
            try:
                # Get HTML of this specific item
                item_html = item.get_attribute('outerHTML')
                item_soup = BeautifulSoup(item_html, 'html.parser')
                
                # Extract data using multiple possible selectors
                item_data = extract_item_data(item_soup)
                if item_data:
                    logger.info(f"Successfully parsed item {idx+1}: {item_data['title']}")
                    parsed_items.append(item_data)
            except Exception as e:
                logger.error(f"Error processing item {idx+1}: {str(e)}")
    
    # If we have items, we're good - don't try alternative parsing methods to save time
    if parsed_items:
        logger.info(f"Total items successfully parsed: {len(parsed_items)}")
        return parsed_items
    
    # If no items found with primary method, try with BeautifulSoup directly (simplified fallback)
    logger.info("Primary extraction failed, trying BeautifulSoup fallback")
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    grid_items = soup.select('div[data-testid="grid-item"]')
    
    if grid_items:
        logger.info(f"Found {len(grid_items)} grid items with BeautifulSoup")
        for idx, item in enumerate(grid_items[:max_items]):
            try:
                item_data = extract_item_data(item)
                if item_data:
                    logger.info(f"Successfully parsed BS item {idx+1}: {item_data['title']}")
                    parsed_items.append(item_data)
            except Exception as e:
                logger.error(f"Error processing BS item {idx+1}: {str(e)}")
    
    logger.info(f"Total items successfully parsed: {len(parsed_items)}")
    return parsed_items


def extract_item_data(item_soup):
    """
    Extract item data from BeautifulSoup object with multiple possible selectors
    
    Args:
        item_soup: BeautifulSoup object containing item HTML
        
    Returns:
        dict: Dictionary with item details or None if extraction failed
    """
    title = None
    url = None
    price = "Price not found"
    image_url = "No image"
    
    # Title and URL extraction based on actual HTML structure
    title_link_selectors = [
        ('a.new-item-box__overlay[data-testid="product-item-id-overlay-link"]', 'title', 'href'),
        ('a[data-testid="product-item-id-overlay-link"]', 'title', 'href'),
        ('a.new-item-box__overlay', 'title', 'href'),
        ('a[class*="new-item-box__overlay"]', 'title', 'href')
    ]
    
    for selector, title_attr, href_attr in title_link_selectors:
        link_tag = item_soup.select_one(selector)
        if link_tag:
            title_raw = link_tag.get(title_attr, '')
            if not title_raw:
                title_raw = link_tag.text
            
            title = title_raw.split(',')[0].strip() if title_raw else None
            url = link_tag.get(href_attr, '')
            break
    
    # Price extraction - focus on the most reliable selector
    price_div = item_soup.select_one('div[data-testid="price"]')
    if price_div:
        price = price_div.text.strip()
    
    # Image URL extraction
    image = item_soup.select_one('div.new-item-box__image img')
    if image:
        image_url = image.get('src', 'No image')
    
    # Only return if we have at least title and URL
    if title and url:
        return {
            'title': title,
            'price': price,
            'url': f"https://www.vinted.pl{url}" if url.startswith('/') else url,
            'image_url': image_url
        }
    return None