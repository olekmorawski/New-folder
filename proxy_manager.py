import random
import requests
import json
import os
import time
from typing import List, Dict, Optional, Union

class ProxyManager:
    """
    Manages a pool of proxies and provides rotation functionality.
    Supports multiple proxy sources and formats.
    """
    
    def __init__(self):
        self.proxies = []
        self.working_proxies = []
        self.failed_proxies = []
        self.current_proxy = None
        self.max_failures = 3
        self.failure_counts = {}
        self.last_rotation_time = 0
        self.rotation_interval = 300  # 5 minutes by default
        
    def load_from_file(self, filepath: str) -> None:
        """Load proxies from a text file (one proxy per line)"""
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    proxy = line.strip()
                    if proxy and not proxy.startswith('#'):
                        self.proxies.append(proxy)
            print(f"Loaded {len(self.proxies)} proxies from {filepath}")
        except Exception as e:
            print(f"Error loading proxies from file: {e}")
    
    def load_from_json(self, filepath: str, key: str = 'proxies') -> None:
        """Load proxies from a JSON file with a specified key"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                proxy_list = data.get(key, [])
                for proxy in proxy_list:
                    if isinstance(proxy, str):
                        self.proxies.append(proxy)
                    elif isinstance(proxy, dict):
                        # Handle different formats like {'ip': '1.2.3.4', 'port': '8080'}
                        ip = proxy.get('ip') or proxy.get('host') or proxy.get('address')
                        port = proxy.get('port')
                        if ip and port:
                            self.proxies.append(f"{ip}:{port}")
            print(f"Loaded {len(self.proxies)} proxies from {filepath}")
        except Exception as e:
            print(f"Error loading proxies from JSON: {e}")
    
    def load_from_api(self, api_url: str, headers: Optional[Dict] = None, 
                      api_key: Optional[str] = None, response_format: str = 'json', 
                      proxy_path: str = 'data') -> None:
        """
        Load proxies from an API endpoint
        
        Args:
            api_url: The API URL to fetch proxies from
            headers: Optional headers for the API request
            api_key: Optional API key (will be added to headers)
            response_format: 'json' or 'text' based on API response
            proxy_path: JSON path to proxies (e.g., 'data.proxies')
        """
        try:
            if headers is None:
                headers = {}
            
            if api_key:
                headers['Authorization'] = f"Bearer {api_key}"
                
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()
            
            if response_format == 'json':
                data = response.json()
                
                # Navigate through nested JSON if needed
                if '.' in proxy_path:
                    parts = proxy_path.split('.')
                    for part in parts:
                        data = data.get(part, {})
                else:
                    data = data.get(proxy_path, [])
                
                # Extract proxies from the data
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, str):
                            self.proxies.append(item)
                        elif isinstance(item, dict):
                            ip = item.get('ip') or item.get('host') or item.get('address')
                            port = item.get('port')
                            if ip and port:
                                self.proxies.append(f"{ip}:{port}")
            else:
                # Assume text format with one proxy per line
                proxy_list = response.text.strip().split('\n')
                for proxy in proxy_list:
                    proxy = proxy.strip()
                    if proxy:
                        self.proxies.append(proxy)
                        
            print(f"Loaded {len(self.proxies)} proxies from API")
        except Exception as e:
            print(f"Error loading proxies from API: {e}")
    
    def add_proxy(self, proxy: str) -> None:
        """Add a single proxy to the pool"""
        if proxy not in self.proxies:
            self.proxies.append(proxy)
    
    def verify_proxies(self, test_url: str = 'https://httpbin.org/ip', 
                       timeout: int = 10, max_proxies: Optional[int] = None) -> None:
        """
        Test each proxy to verify it's working
        
        Args:
            test_url: URL to test the proxy against
            timeout: Request timeout in seconds
            max_proxies: Maximum number of proxies to verify (None for all)
        """
        self.working_proxies = []
        proxies_to_check = self.proxies[:max_proxies] if max_proxies else self.proxies
        
        print(f"Verifying {len(proxies_to_check)} proxies...")
        for proxy in proxies_to_check:
            try:
                # Format proxy for requests
                proxy_dict = {
                    'http': f'http://{proxy}',
                    'https': f'http://{proxy}'
                }
                
                # Test the proxy
                response = requests.get(test_url, proxies=proxy_dict, timeout=timeout)
                
                if response.status_code == 200:
                    self.working_proxies.append(proxy)
                    print(f"Proxy {proxy} is working")
                else:
                    print(f"Proxy {proxy} returned status code {response.status_code}")
                    
            except Exception as e:
                print(f"Proxy {proxy} failed: {e}")
        
        print(f"Verification complete. {len(self.working_proxies)} working proxies found.")
    
    def get_random_proxy(self) -> Optional[str]:
        """Get a random proxy from the pool of working proxies"""
        if self.working_proxies:
            return random.choice(self.working_proxies)
        elif self.proxies:
            return random.choice(self.proxies)
        return None
    
    def get_next_proxy(self) -> Optional[str]:
        """Get the next proxy in the rotation"""
        proxy_list = self.working_proxies if self.working_proxies else self.proxies
        
        if not proxy_list:
            return None
            
        if self.current_proxy in proxy_list:
            current_index = proxy_list.index(self.current_proxy)
            next_index = (current_index + 1) % len(proxy_list)
        else:
            next_index = 0
            
        self.current_proxy = proxy_list[next_index]
        return self.current_proxy
    
    def mark_proxy_failed(self, proxy: str) -> None:
        """
        Mark a proxy as failed. If it fails too many times, 
        move it to the failed list.
        """
        if proxy not in self.failure_counts:
            self.failure_counts[proxy] = 0
            
        self.failure_counts[proxy] += 1
        
        if self.failure_counts[proxy] >= self.max_failures:
            if proxy in self.working_proxies:
                self.working_proxies.remove(proxy)
            if proxy in self.proxies:
                self.proxies.remove(proxy)
            self.failed_proxies.append(proxy)
            print(f"Proxy {proxy} has been marked as failed and removed from rotation")
    
    def should_rotate(self) -> bool:
        """Check if we should rotate to a new proxy based on time interval"""
        current_time = time.time()
        if (current_time - self.last_rotation_time) > self.rotation_interval:
            self.last_rotation_time = current_time
            return True
        return False
    
    def get_as_selenium_proxy(self, proxy: Optional[str] = None) -> Dict[str, str]:
        """
        Format a proxy for use with Selenium/undetected-chromedriver
        If no proxy is provided, get the next proxy in rotation
        
        Returns:
            Dictionary with keys for Chrome's --proxy-server argument
        """
        if proxy is None:
            proxy = self.get_next_proxy()
            
        if not proxy:
            return {}
            
        # Update rotation timestamp
        self.last_rotation_time = time.time()
        self.current_proxy = proxy
        
        # For Selenium/Chrome, we need to return the formatted proxy string
        return proxy
    
    def get_proxy_server_arg(self, proxy_type: str = 'http') -> Optional[str]:
        """
        Get a proxy in the format needed for Chrome's --proxy-server argument
        
        Args:
            proxy_type: Type of proxy (http, https, socks4, socks5)
            
        Returns:
            Formatted proxy string or None if no proxies available
        """
        proxy = self.get_next_proxy()
        if not proxy:
            return None
            
        # Check if proxy already has a type specified
        if '://' in proxy:
            return proxy
            
        # Format the proxy for Chrome
        return f"{proxy_type}://{proxy}"
    
    def get_proxy_count(self) -> Dict[str, int]:
        """Get counts of proxies in each category"""
        return {
            'total': len(self.proxies),
            'working': len(self.working_proxies),
            'failed': len(self.failed_proxies)
        }
    
    def save_working_proxies(self, filepath: str) -> None:
        """Save the list of working proxies to a file"""
        try:
            with open(filepath, 'w') as f:
                for proxy in self.working_proxies:
                    f.write(f"{proxy}\n")
            print(f"Saved {len(self.working_proxies)} working proxies to {filepath}")
        except Exception as e:
            print(f"Error saving working proxies: {e}")

# Example usage            
if __name__ == "__main__":
    # Example of how to use the proxy manager
    proxy_manager = ProxyManager()
    
    # Load proxies from different sources (examples, uncomment as needed)
    # proxy_manager.load_from_file("proxies.txt")
    # proxy_manager.load_from_json("proxies.json", key="proxies")
    
    # Example with a few hardcoded proxies (replace with your actual proxies)
    proxy_manager.add_proxy("127.0.0.1:8080")  # Example only, replace with real proxies
    proxy_manager.add_proxy("127.0.0.1:8081")  # Example only, replace with real proxies
    
    # Verify which proxies are working
    proxy_manager.verify_proxies()
    
    # Get statistics
    print(proxy_manager.get_proxy_count())
    
    # Get a proxy for Selenium
    proxy = proxy_manager.get_proxy_server_arg("http")
    print(f"Using proxy: {proxy}")