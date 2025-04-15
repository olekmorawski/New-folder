import time
import random
import logging

# Set up logging
def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    return logger

# Create logger instance
logger = setup_logging()

def random_delay(min_seconds=1, max_seconds=3):
    """Add a random delay to simulate human behavior"""
    delay = random.uniform(min_seconds, max_seconds)
    logger.info(f"Waiting for {delay:.2f} seconds")
    time.sleep(delay)