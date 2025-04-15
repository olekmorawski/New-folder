import json
from utils import logger

def load_credentials(filename='vinted_credentials.json'):
    """Load Vinted login credentials from a JSON file"""
    try:
        with open(filename, 'r') as f:
            creds = json.load(f)
            return creds.get('email', ''), creds.get('password', '')
    except FileNotFoundError:
        logger.warning(f"Credentials file {filename} not found.")
        return '', ''
    except json.JSONDecodeError:
        logger.error(f"Error parsing credentials file {filename}.")
        return '', ''

def save_credentials(email, password, filename='vinted_credentials.json'):
    """Save Vinted login credentials to a JSON file"""
    with open(filename, 'w') as f:
        json.dump({'email': email, 'password': password}, f)
    logger.info(f"Credentials saved to {filename}")