import getpass
import json
import time
import threading
import os
import sys
import argparse
import random
from concurrent.futures import ThreadPoolExecutor

from utils import logger
from driver_setup import setup_driver, setup_driver_with_proxy
from vinted_login import login_to_vinted
from item_scraper import scrape_vinted_search
from monitor import monitor_for_new_items
from credentials import load_credentials, save_credentials

# Global variables for multi-instance tracking
active_drivers = []
results_lock = threading.Lock()
all_results = []
seen_items = {}

def create_accounts_file():
    """Create accounts.json file if it doesn't exist"""
    if os.path.exists('accounts.json'):
        return
        
    logger.info("Creating accounts.json template. Please edit with your actual accounts.")
    accounts = [
        {
            "email": "account1@example.com",
            "password": "your_password1"
        },
        {
            "email": "account2@example.com",
            "password": "your_password2"
        }
    ]
    
    with open('accounts.json', 'w') as f:
        json.dump(accounts, f, indent=2)

def load_accounts():
    """Load all accounts from accounts.json"""
    try:
        with open('accounts.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("accounts.json not found. Creating template.")
        create_accounts_file()
        return []
    except json.JSONDecodeError:
        logger.error("Error parsing accounts.json.")
        return []

def instance_worker(instance_id, account, search_query, catalog_id, check_interval, max_results, monitor_mode=False, use_proxy=False):
    """Worker function for each browser instance"""
    global active_drivers, all_results, seen_items
    
    logger.info(f"Instance {instance_id}: Starting with account {account['email']}")
    
    # Create a unique data directory for each Chrome instance
    chrome_data_dir = f"chrome_data_{instance_id}"
    os.makedirs(chrome_data_dir, exist_ok=True)
    
    # Create a new driver with unique user data directory
    try:
        import undetected_chromedriver as uc
        
        # Create options with unique user data directory
        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={os.path.abspath(chrome_data_dir)}")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        
        # Random window position to avoid windows stacking
        x_pos = random.randint(0, 300)
        y_pos = random.randint(0, 300)
        options.add_argument(f"--window-position={x_pos},{y_pos}")
        
        # Add proxy if requested
        if use_proxy:
            try:
                from proxy_manager import ProxyManager
                proxy_manager = ProxyManager()
                
                # Try to load proxies
                if os.path.exists('proxies.txt'):
                    proxy_manager.load_from_file('proxies.txt')
                
                if proxy_manager.proxies:
                    proxy = proxy_manager.get_proxy_server_arg()
                    if proxy:
                        options.add_argument(f"--proxy-server={proxy}")
                        logger.info(f"Instance {instance_id}: Using proxy {proxy}")
            except Exception as e:
                logger.warning(f"Instance {instance_id}: Error setting up proxy: {e}")
        
        # Create the driver
        driver = uc.Chrome(
            options=options,
            use_subprocess=True,
            headless=False
        )
        
        # Set timeout
        driver.set_page_load_timeout(30)
        
        logger.info(f"Instance {instance_id}: Created Chrome instance with unique profile")
    except Exception as e:
        logger.error(f"Instance {instance_id}: Error creating Chrome with unique profile: {e}")
        # Fall back to regular setup
        logger.info(f"Instance {instance_id}: Falling back to default setup")
        driver = setup_driver_with_proxy(use_proxy=use_proxy) if use_proxy else setup_driver()
    
    # Add to active drivers list
    with results_lock:
        active_drivers.append(driver)
    
    try:
        # Login with the account
        login_result = login_to_vinted(driver, account['email'], account['password'])
        if not login_result:
            logger.warning(f"Instance {instance_id}: Login failed for {account['email']}")
            return  # Exit this instance worker
            
        logger.info(f"Instance {instance_id}: Login successful for {account['email']}")
        
        # Run in monitor mode or do a single search
        if monitor_mode:
            # Create a thread-local dictionary for seen items
            local_seen_items = {}
            
            while True:
                logger.info(f"Instance {instance_id}: Checking for new items")
                
                try:
                    # Perform search
                    results = scrape_vinted_search(driver, search_query, max_results, catalog_id)
                    
                    # Process new items
                    new_items = []
                    for item in results:
                        try:
                            # Get item ID from URL
                            item_id = item['url'].split('/')[-1].split('-')[0]
                            
                            # Check if this is a new item for this instance
                            if item_id not in local_seen_items:
                                local_seen_items[item_id] = item
                                
                                # Check if it's a new item globally
                                with results_lock:
                                    if item_id not in seen_items:
                                        seen_items[item_id] = item
                                        new_items.append(item)
                        except Exception as e:
                            logger.warning(f"Instance {instance_id}: Error processing item: {e}")
                    
                    # Report new items
                    if new_items:
                        with results_lock:
                            # Save to file with instance ID
                            timestamp = time.strftime("%Y%m%d-%H%M%S")
                            filename = f"instance{instance_id}_new_items_{timestamp}.json"
                            with open(filename, 'w', encoding='utf-8') as f:
                                json.dump(new_items, f, indent=2, ensure_ascii=False)
                            
                            logger.info(f"Instance {instance_id}: Found {len(new_items)} new items! Saved to {filename}")
                    else:
                        logger.info(f"Instance {instance_id}: No new items found")
                    
                    # Check for access blocked
                    if "Access blocked" in driver.page_source or "unusual activity" in driver.page_source:
                        logger.warning(f"Instance {instance_id}: Access blocked! Taking screenshot.")
                        driver.save_screenshot(f"instance{instance_id}_blocked.png")
                        
                        # If using proxies, we could implement proxy rotation here
                        # For now, just exit this instance worker
                        logger.error(f"Instance {instance_id}: Shutting down due to blocked access")
                        break
                        
                except Exception as e:
                    logger.error(f"Instance {instance_id}: Error during search: {e}")
                
                # Wait before next check - randomize slightly to avoid patterns
                actual_interval = check_interval + random.randint(-5, 5)
                logger.info(f"Instance {instance_id}: Waiting {actual_interval} seconds until next check...")
                time.sleep(actual_interval)
                
        else:
            # Single search mode
            logger.info(f"Instance {instance_id}: Performing single search for '{search_query}'")
            results = scrape_vinted_search(driver, search_query, max_results, catalog_id)
            
            with results_lock:
                if results:
                    # Save to instance-specific file
                    filename = f"instance{instance_id}_results.json"
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(results, f, indent=2, ensure_ascii=False)
                        
                    # Add to global results
                    all_results.extend(results)
                    
                    logger.info(f"Instance {instance_id}: Found {len(results)} items. Saved to {filename}")
                else:
                    logger.warning(f"Instance {instance_id}: No results found")
    
    except Exception as e:
        logger.error(f"Instance {instance_id}: Fatal error: {e}", exc_info=True)
    finally:
        logger.info(f"Instance {instance_id}: Shutting down")
        driver.quit()
        
        # Remove from active drivers
        with results_lock:
            if driver in active_drivers:
                active_drivers.remove(driver)

def multi_instance_main():
    """Main function for multi-instance operation"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Vinted Multi-Instance Scraper")
    parser.add_argument("--instances", "-i", type=int, default=2, help="Number of browser instances (default: 2)")
    parser.add_argument("--search", "-s", type=str, default="books", help="Search query (default: books)")
    parser.add_argument("--catalog", "-c", type=str, help="Vinted catalog ID (optional)")
    parser.add_argument("--interval", "-t", type=int, default=60, help="Check interval in seconds (default: 60)")
    parser.add_argument("--max-items", "-m", type=int, default=5, help="Max items per check (default: 5)")
    parser.add_argument("--monitor", "-w", action="store_true", help="Run in continuous monitoring mode")
    parser.add_argument("--use-proxy", "-p", action="store_true", help="Use proxy rotation")
    args = parser.parse_args()
    
    # Load accounts
    accounts = load_accounts()
    if not accounts:
        logger.error("No accounts found in accounts.json. Please add your accounts and try again.")
        return
        
    # Check if we have enough accounts
    if len(accounts) < args.instances:
        logger.warning(f"Only {len(accounts)} accounts available, but {args.instances} instances requested.")
        logger.warning(f"Will use {len(accounts)} instances instead.")
        args.instances = len(accounts)
    
    logger.info(f"\n{'='*40}")
    logger.info(f"Starting Vinted Multi-Instance Scraper with {args.instances} browsers")
    logger.info(f"{'='*40}\n")
    
    logger.info(f"Configuration:")
    logger.info(f"Instances: {args.instances}")
    logger.info(f"Search Query: '{args.search}'")
    if args.catalog:
        logger.info(f"Catalog ID: {args.catalog}")
    else:
        logger.info(f"Catalog ID: Not specified (searching all categories)")
    logger.info(f"Check interval: {args.interval} seconds")
    logger.info(f"Max items per check: {args.max_items}")
    logger.info(f"Monitor mode: {'Enabled' if args.monitor else 'Disabled'}")
    logger.info(f"Using proxies: {'Yes' if args.use_proxy else 'No'}")
    logger.info(f"{'='*40}\n")
    
    # Create and start worker threads for each instance
    workers = []
    for i in range(args.instances):
        # Get account for this instance
        account = accounts[i]
        
        # Create and start the worker thread
        worker = threading.Thread(
            target=instance_worker,
            args=(i+1, account, args.search, args.catalog, args.interval, args.max_items, args.monitor, args.use_proxy),
            daemon=True
        )
        workers.append(worker)
        worker.start()
        
        # Small delay between starting instances to avoid overwhelming the system
        time.sleep(3)
    
    # Wait for all workers to finish (they'll run indefinitely in monitor mode)
    try:
        for worker in workers:
            worker.join()
    except KeyboardInterrupt:
        logger.info("\nKeyboard interrupt received. Shutting down all instances...")
    finally:
        # Cleanup - close all remaining browser instances
        for driver in active_drivers:
            try:
                driver.quit()
            except:
                pass
        
        # Save combined results if not in monitor mode
        if not args.monitor and all_results:
            with open('all_results.json', 'w', encoding='utf-8') as f:
                json.dump(all_results, f, indent=2, ensure_ascii=False)
            logger.info(f"All results saved to all_results.json")
        
        logger.info("All instances have been shut down.")

def single_instance_main():
    """Original main function for backward compatibility"""
    logger.info(f"\n{'='*40}")
    logger.info(f"Starting Vinted Item Monitor with Login")
    logger.info(f"{'='*40}\n")
    
    # Get user credentials
    email, password = load_credentials()
    if not email or not password:
        print("\nVinted Login")
        print("------------")
        email = input("Enter your Vinted email: ").strip()
        password = getpass.getpass("Enter your Vinted password: ")
        save_option = input("Save credentials for next time? (y/n): ").strip().lower()
        if save_option == 'y':
            save_credentials(email, password)
    
    driver = setup_driver()
    try:
        # Login first
        login_result = login_to_vinted(driver, email, password)
        if not login_result:
            logger.warning("Login was not successful. Continuing without login.")
            
        print("\nVinted New Item Monitor")
        print("----------------------")
        search_query = input("Enter search query: ").strip() or "books"
        
        # Make catalog ID optional
        catalog_id_input = input("Enter catalog ID (optional, press Enter to skip): ").strip()
        catalog_id = catalog_id_input if catalog_id_input else None
        
        check_interval = int(input("Check interval in seconds (default 60): ") or "60")
        max_results = int(input("Max items per check (default 5): ") or "5")
        
        # Ask if the user wants to run in monitor mode or just do a single check
        monitor_mode = input("Run in continuous monitoring mode? (y/n, default: y): ").strip().lower() != 'n'
        
        logger.info(f"\n{'='*40}")
        logger.info(f"Configuration:")
        logger.info(f"Query: '{search_query}'")
        if catalog_id:
            logger.info(f"Catalog ID: {catalog_id}")
        else:
            logger.info(f"Catalog ID: Not specified (searching all categories)")
        logger.info(f"Check interval: {check_interval} seconds")
        logger.info(f"Max items per check: {max_results}")
        logger.info(f"Monitor mode: {'Enabled' if monitor_mode else 'Disabled'}")
        logger.info(f"{'='*40}\n")
        
        if monitor_mode:
            # Run monitoring function
            monitor_for_new_items(
                driver=driver,
                query=search_query,
                catalog_id=catalog_id,
                interval=check_interval,
                max_items=max_results
            )
        else:
            # Just do a single check
            logger.info(f"Performing single check for: '{search_query}'")
            results = scrape_vinted_search(driver, search_query, max_results, catalog_id)
            
            if results:
                logger.info(f"\n{'='*40}")
                logger.info(f"Scraping Results ({len(results)} items):")
                logger.info(f"{'='*40}")
                for idx, item in enumerate(results, 1):
                    logger.info(f"\nItem {idx}:")
                    logger.info(f"Title: {item['title']}")
                    logger.info(f"Price: {item['price']}")
                    logger.info(f"URL: {item['url']}")
                    logger.info(f"Image: {item['image_url']}")
                
                with open('vinted_results.json', 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                logger.info("\nResults saved to vinted_results.json")
            else:
                logger.error("\nNo results found")
            
    except Exception as e:
        logger.error(f"\nFatal error in main execution: {e}", exc_info=True)
    finally:
        logger.info("\nClosing browser...")
        driver.quit()

if __name__ == "__main__":
    # Always use multi-instance mode with this script
    multi_instance_main()