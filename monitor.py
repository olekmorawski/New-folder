import time
import json

from utils import logger
from item_scraper import scrape_vinted_search

def monitor_for_new_items(driver, query, catalog_id=None, interval=60, max_items=5, max_runs=None):
    """
    Continuously monitors for new items by checking Vinted at regular intervals
    
    Args:
        driver: Selenium WebDriver instance
        query: Search query string
        catalog_id: Vinted catalog ID (optional)
        interval: Seconds between checks (default: 60)
        max_items: Maximum items to return per check
        max_runs: Maximum number of monitoring cycles (None for infinite)
    
    Returns:
        None - this function runs until stopped
    """
    logger.info(f"Starting monitoring for new '{query}' items every {interval} seconds")
    
    # Keep track of already seen items to identify new ones
    seen_items = {}
    run_count = 0
    
    try:
        while True:
            run_count += 1
            logger.info(f"Run #{run_count}: Checking for new items")
            
            # Get current items
            results = scrape_vinted_search(driver, query, max_items, catalog_id)
            
            # Identify new items
            new_items = []
            for item in results:
                # Extract item ID from URL (with error handling)
                try:
                    item_id = item['url'].split('/')[-1].split('-')[0]
                except Exception as e:
                    logger.warning(f"Could not extract item ID from URL '{item['url']}': {e}")
                    continue
                
                if item_id not in seen_items:
                    logger.info(f"Found new item: {item['title']}")
                    new_items.append(item)
                    seen_items[item_id] = item
            
            # Report and save new items if found
            if new_items:
                logger.info(f"Found {len(new_items)} new items!")
                
                # Save results to both individual and cumulative files
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                
                # Save this batch
                with open(f'vinted_new_items_{timestamp}.json', 'w', encoding='utf-8') as f:
                    json.dump(new_items, f, indent=2, ensure_ascii=False)
                
                # Save all seen items
                with open('vinted_all_items.json', 'w', encoding='utf-8') as f:
                    json.dump(list(seen_items.values()), f, indent=2, ensure_ascii=False)
                
                logger.info(f"Saved new items to vinted_new_items_{timestamp}.json")
                logger.info(f"Total items tracked: {len(seen_items)}")
                
                # Add any additional notification logic here (e.g., email, Discord webhook, etc.)
                
            else:
                logger.info("No new items found in this check")
            
            # Check if we should stop
            if max_runs and run_count >= max_runs:
                logger.info(f"Reached maximum run count ({max_runs}). Stopping.")
                break
                
            # Wait for next check
            wait_time = interval
            logger.info(f"Waiting {wait_time} seconds until next check...")
            time.sleep(wait_time)
            
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    except Exception as e:
        logger.error(f"Error during monitoring: {e}", exc_info=True)
    finally:
        logger.info("Monitoring ended")