import api
import time

# poll every 60 seconds
REQUEST_INTERVAL_SEC: int = 60

if __name__ == "__main__":
    while True:
        # do stuff and then sleep for REQUEST_INTERVAL_SEC
        time.sleep(REQUEST_INTERVAL_SEC)