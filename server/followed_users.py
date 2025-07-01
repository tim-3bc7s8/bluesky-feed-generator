import threading
import time
from atproto import Client
from server import config
from server.logger import logger

# A set to store the DIDs of users we follow, for fast lookups.
# This will be populated and periodically updated by a background thread.
FOLLOWED_DIDS = set()

def _fetch_and_update_followed_users():
    """
    Logs in and fetches the full list of users followed by the account
    configured in the environment variables. Updates the global FOLLOWED_DIDS set.
    """
    global FOLLOWED_DIDS
    
    logger.info("Attempting to fetch list of followed users...")
    
    try:
        # We use the same credentials as the main app
        client = Client()
        client.login(config.HANDLE, config.PASSWORD)
        
        profile = client.app.bsky.actor.get_profile({'actor': config.HANDLE})
        
        # The 'follows_count' is on the profile view model
        follows_count = profile.follows_count
        logger.info(f"Found {follows_count} followed users for @{config.HANDLE}. Fetching pages...")
        
        all_follows = []
        cursor = None
        
        # The get_follows method paginates, so we loop until we have them all
        while True:
            response = client.app.bsky.graph.get_follows({
                'actor': config.HANDLE,
                'limit': 100,
                'cursor': cursor
            })
            all_follows.extend(response.follows)
            
            if not response.cursor:
                break
            cursor = response.cursor

        # Instead of re-assigning the global variable, we modify it in-place.
        # This ensures that other modules that have imported FOLLOWED_DIDS see the change.
        new_followed_dids = {follow.did for follow in all_follows}
        FOLLOWED_DIDS.clear()
        FOLLOWED_DIDS.update(new_followed_dids)
        
        # Atomically update the global set so our filter always has the latest list
        FOLLOWED_DIDS = new_followed_dids
        
        logger.info(f"Successfully updated followed users list. Total: {len(FOLLOWED_DIDS)}")

    except Exception as e:
        logger.error(f"Could not fetch followed users: {e}")


def _run_update_loop(stop_event: threading.Event, update_interval_seconds: int):
    """
    Continuously fetches the list of followed users at a set interval.
    
    Args:
        stop_event: A threading.Event to signal when to stop the loop.
        update_interval_seconds: The time to wait between updates.
    """
    while not stop_event.is_set():
        _fetch_and_update_followed_users()
        stop_event.wait(update_interval_seconds)


def start_follower_update_thread(update_interval_minutes: int = 15) -> threading.Thread:
    """
    Creates and starts a background thread to keep the list of followed users updated.
    
    Args:
        update_interval_minutes: The interval in minutes for how often to refresh the list.
        
    Returns:
        The threading.Event object used to stop the thread.
    """
    stop_event = threading.Event()
    update_interval_seconds = update_interval_minutes * 60
    
    thread = threading.Thread(
        target=_run_update_loop,
        args=(stop_event, update_interval_seconds)
    )
    thread.daemon = True # Allows the main app to exit even if this thread is running
    thread.start()
    
    logger.info(f"Started background thread to update followed users every {update_interval_minutes} minutes.")
    
    # We return the event so the main app can signal this thread to stop
    return stop_event
