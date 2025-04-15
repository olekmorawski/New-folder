import getpass
import json

from utils import logger
from driver_setup import setup_driver
from vinted_login import login_to_vinted
from item_scraper import scrape_vinted_search
from monitor import monitor_for_new_items
from credentials import load_credentials, save_credentials

def main():
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
    main()