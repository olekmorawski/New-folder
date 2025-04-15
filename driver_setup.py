from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException
import undetected_chromedriver as uc
import time
import random
import os

from utils import logger, random_delay
from proxy_manager import ProxyManager

# Initialize the proxy manager as a global instance
proxy_manager = ProxyManager()

def initialize_proxies(proxy_sources=None):
    """
    Initialize the proxy manager with proxies from various sources
    
    Args:
        proxy_sources: Dictionary with proxy source configurations
    """
    global proxy_manager
    
    # Default proxy sources if none provided
    if proxy_sources is None:
        proxy_sources = {
            'files': ['proxies.txt'],
            'api': {
                'enabled': False,
                'url': '',
                'api_key': '',
                'headers': {},
                'format': 'json',
                'path': 'data'
            },
            'verify': True,
            'verification_url': 'https://httpbin.org/ip',
            'timeout': 10,
            'max_check': 50  # Limit how many to check for speed
        }
    
    # Load proxies from files
    for file_path in proxy_sources.get('files', []):
        if os.path.exists(file_path):
            if file_path.endswith('.json'):
                proxy_manager.load_from_json(file_path)
            else:
                proxy_manager.load_from_file(file_path)
    
    # Load proxies from API if enabled
    api_config = proxy_sources.get('api', {})
    if api_config.get('enabled', False) and api_config.get('url'):
        proxy_manager.load_from_api(
            api_url=api_config['url'],
            headers=api_config.get('headers'),
            api_key=api_config.get('api_key'),
            response_format=api_config.get('format', 'json'),
            proxy_path=api_config.get('path', 'data')
        )
    
    # Verify proxies if enabled
    if proxy_sources.get('verify', True):
        proxy_manager.verify_proxies(
            test_url=proxy_sources.get('verification_url', 'https://httpbin.org/ip'),
            timeout=proxy_sources.get('timeout', 10),
            max_proxies=proxy_sources.get('max_check')
        )
    
    logger.info(f"Proxy initialization complete. {proxy_manager.get_proxy_count()}")

def setup_driver_with_proxy(use_proxy=True, proxy_type='http'):
    """
    Configure and return an undetected Chrome WebDriver with proxy support
    
    Args:
        use_proxy: Whether to use a proxy
        proxy_type: Type of proxy (http, https, socks4, socks5)
        
    Returns:
        Configured undetected_chromedriver instance
    """
    global proxy_manager
    
    # Define a comprehensive list of user agents
    user_agents = [
        # Windows + Chrome
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        # Windows + Firefox
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        # Windows + Edge
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
        # macOS + Safari
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
        # macOS + Chrome
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        # Linux + Firefox
        "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
        # Mobile user agents (for variety)
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPad; CPU OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    ]
    
    # Select a random user agent
    selected_user_agent = random.choice(user_agents)
    logger.info(f"Using user agent: {selected_user_agent}")
    
    # Using undetected_chromedriver (more resistant to detection)
    logger.info("Using undetected_chromedriver with proxy support")
    options = uc.ChromeOptions()
    
    # Basic configuration (undetected_chromedriver handles most anti-detection internally)
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # Additional settings that work with undetected-chromedriver
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-web-security")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--no-first-run")
    
    # Set random user agent
    options.add_argument(f"user-agent={selected_user_agent}")
    
    # Enable additional privacy settings
    options.add_argument("--incognito")
    
    # Randomize window size for unique fingerprint
    width = random.randint(1280, 1920)
    height = random.randint(800, 1080)
    options.add_argument(f"--window-size={width},{height}")
    
    # Add proxy if requested
    if use_proxy and proxy_manager.get_proxy_count()['total'] > 0:
        proxy = proxy_manager.get_proxy_server_arg(proxy_type)
        if proxy:
            logger.info(f"Using proxy: {proxy}")
            options.add_argument(f'--proxy-server={proxy}')
    
    # Create and configure the undetected driver
    try:
        # First, try with the specified Chrome binary location
        driver = uc.Chrome(
            options=options,
            driver_executable_path=ChromeDriverManager().install(),
            browser_executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            use_subprocess=True,  # Helps with detection avoidance
            headless=False        # Headless mode is more easily detected
        )
    except Exception as e:
        # Fallback to letting undetected_chromedriver find Chrome automatically
        logger.warning(f"Failed to initialize with specific Chrome path: {e}. Trying automatic detection.")
        driver = uc.Chrome(
            options=options,
            driver_executable_path=ChromeDriverManager().install(),
            use_subprocess=True,
            headless=False
        )
    
    # Set page load timeout
    driver.set_page_load_timeout(30)
    
    return driver

def handle_modals_and_cookies(driver):
    """Handle cookie consent and other modal popups with randomized delays and behavior"""
    # Randomize the order of operations slightly
    if random.random() > 0.3:
        # Look for and accept cookies with multiple selector strategies
        try:
            # List of common cookie acceptance button selectors
            cookie_selectors = [
                (By.ID, "onetrust-accept-btn-handler"),
                (By.CSS_SELECTOR, "button[id*='accept'], button[class*='accept']"),
                (By.CSS_SELECTOR, ".cookie-consent button, .cookies button"),
                (By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'Akceptuj')]"),
                (By.CSS_SELECTOR, "button.consent, .consent-btn, .cookie-btn")
            ]
            
            # Try different selectors with a timeout
            for selector_type, selector in cookie_selectors:
                try:
                    cookie_button = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((selector_type, selector))
                    )
                    # Random delay before clicking
                    time.sleep(random.uniform(0.5, 1.5))
                    
                    # Randomize click method
                    if random.random() > 0.5:
                        cookie_button.click()
                    else:
                        driver.execute_script("arguments[0].click();", cookie_button)
                        
                    logger.info(f"Accepted cookies using selector: {selector}")
                    time.sleep(random.uniform(0.5, 1.2))
                    break
                except Exception:
                    continue
        except Exception as e:
            logger.info(f"Cookie handling failed or not needed: {e}")
    
    # Sometimes scroll a bit (like a human would)
    if random.random() > 0.7:
        try:
            scroll_amount = random.randint(100, 300)
            driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            time.sleep(random.uniform(0.3, 0.8))
        except:
            pass
            
def rotate_proxy_if_needed(driver):
    """
    Check if we should rotate to a new proxy, and if so, create a new driver instance
    
    Args:
        driver: Current driver instance
        
    Returns:
        Either the existing driver or a new one with a different proxy
    """
    global proxy_manager
    
    if proxy_manager.should_rotate():
        logger.info("Rotation interval reached, switching to a new proxy")
        try:
            # Quit the current driver
            driver.quit()
        except:
            pass
            
        # Create a new driver with a fresh proxy
        return setup_driver_with_proxy()
    
    return driver

# For backward compatibility
def setup_driver():
    """Legacy function that calls setup_driver_with_proxy"""
    return setup_driver_with_proxy(use_proxy=True)