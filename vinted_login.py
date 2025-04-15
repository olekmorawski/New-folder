from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import random

from utils import logger, random_delay
from driver_setup import handle_modals_and_cookies

def login_to_vinted(driver, email, password):
    """
    Logs into Vinted using provided credentials
    
    Args:
        driver: Selenium WebDriver instance
        email: User's email address
        password: User's password
        
    Returns:
        bool: True if login was successful, False otherwise
    """
    try:
        logger.info("Navigating to Vinted homepage...")
        driver.get("https://www.vinted.pl/")
        random_delay(2, 4)
        
        # Handle cookies first
        handle_modals_and_cookies(driver)
        
        # Look for the login/register button and click it
        logger.info("Looking for login/register button...")
        login_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-testid='header--login-button']"))
        )
        driver.execute_script("arguments[0].click();", login_button)
        logger.info("Clicked login/register button")
        random_delay(1, 2)
        
        # Wait for the modal to appear and click "Zaloguj się" (Login) link
        logger.info("Looking for 'Zaloguj się' link in the modal...")
        try:
            # First, try to find the switch link at the bottom of the modal
            login_switch = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "span[data-testid='auth-select-type--register-switch']"))
            )
            driver.execute_script("arguments[0].click();", login_switch)
            logger.info("Clicked 'Zaloguj się' switch link")
        except Exception as e:
            logger.warning(f"Could not find the switch link: {e}")
            # If we can't find the switch link, we might already be on the login tab
            pass
            
        random_delay(1, 2)
        
        # Now we need to click on the "E-mail" option to proceed to the email form
        logger.info("Looking for 'E-mail' option...")
        try:
            email_option = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "span[data-testid='auth-select-type--register-email'], span[data-testid='auth-select-type--login-email']"))
            )
            driver.execute_script("arguments[0].click();", email_option)
            logger.info("Clicked 'E-mail' option")
        except Exception as e:
            logger.warning(f"Could not find 'E-mail' option: {e}")
            # We might be on the email form already
            pass
            
        random_delay(1, 2)
        
        # Wait for the email input field to appear
        logger.info("Waiting for username field...")
        username_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        
        # Clear any existing text and enter email with human-like typing
        username_field.clear()
        for char in email:
            username_field.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
        logger.info("Entered email")
        random_delay(0.5, 1.5)
        
        # Continue to password page by clicking the submit button
        continue_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
        )
        driver.execute_script("arguments[0].click();", continue_button)
        logger.info("Clicked continue button")
        random_delay(1, 2)
        
        # Wait for password field
        logger.info("Waiting for password field...")
        password_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
        )
        
        # Enter password with human-like typing
        password_field.clear()
        for char in password:
            password_field.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
        logger.info("Entered password")
        random_delay(0.5, 1.5)
        
        # Submit the form
        submit_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
        )
        driver.execute_script("arguments[0].click();", submit_button)
        logger.info("Submitted login form")
        
        # Wait for login to complete and verify successful login
        try:
            # First check for error messages
            error_message = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.error-message, div[class*='error']"))
            )
            logger.error(f"Login failed - error message displayed: {error_message.text}")
            return False
        except TimeoutException:
            # No error message found, continue checking for successful login
            pass
            
        # Check for successful login indicators
        try:
            # Wait for page to load after login
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.u-flexbox"))
            )
            
            # Look for user-specific elements that appear after login
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/member/'], div.avatar, button[class*='user-menu']"))
            )
            logger.info("Login successful!")
            return True
        except Exception as e:
            logger.error(f"Login verification failed: {e}")
            return False
        
    except Exception as e:
        logger.error(f"Error during login process: {e}", exc_info=True)
        return False