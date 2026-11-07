import time
from functools import wraps
from requests.exceptions import ReadTimeout, ConnectionError

def retry(retries=3, delay=10):
    """
    Decorator to retry API calls with a specified number of retries and delay between attempts.
    
    Args:
        retries (int): Number of retry attempts
        delay (int): Delay between retries in seconds
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < retries:
                try:
                    return func(*args, **kwargs)
                except (ReadTimeout, ConnectionError) as e:
                    print(f"Attempt {attempts + 1} failed: {str(e)}")
                    if attempts < retries - 1:
                        print(f"Waiting {delay} seconds before retrying...")
                        time.sleep(delay)
                    attempts += 1
            raise Exception(f"Failed after {retries} attempts")
        return wrapper
    return decorator