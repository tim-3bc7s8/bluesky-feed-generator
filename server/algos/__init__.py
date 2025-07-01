import os
from importlib import import_module
from server import config

# A dictionary to store our algorithm handlers
algos = {}

def get_algo_handler(record_name):
    """
    Dynamically imports and returns a handler function for a given algorithm.
    The module name is derived from the record_name by replacing dashes with underscores.
    
    For example, a record_name of 'personal-feed' will attempt to import the 'handler'
    function from the 'server.algos.personal_feed' module.
    """
    # Convert the record_name from the URI (e.g., 'personal-feed')
    # into a Python module name (e.g., 'personal_feed')
    module_name = record_name.replace('-', '_')
    module_path = f'server.algos.{module_name}'

    try:
        # Import the module
        module = import_module(module_path)
        # Return the 'handler' function from the module
        return module.handler
    except (ImportError, AttributeError) as e:
        # Handle cases where the module or the handler function doesn't exist
        print(f"Could not load algorithm handler for '{record_name}': {e}")
        return None

# --- Algorithm Discovery ---
# Scan the current directory for Python files (excluding this __init__.py file)
# to discover and register algorithm handlers.
current_dir = os.path.dirname(__file__)
for filename in os.listdir(current_dir):
    # Check for .py files, excluding __init__.py
    if filename.endswith('.py') and not filename.startswith('__'):
        # Derive the record_name from the filename
        # e.g., 'personal_feed.py' -> 'personal-feed'
        record_name = filename[:-3].replace('_', '-')
        
        # Construct the AT URI for the feed
        uri = f'at://{config.SERVICE_DID}/app.bsky.feed.generator/{record_name}'
        
        # Get the handler function for this algorithm
        handler_func = get_algo_handler(record_name)
        if handler_func:
            # Add the URI and handler to our algos dictionary
            algos[uri] = handler_func
            print(f"Successfully registered feed: {uri}")
