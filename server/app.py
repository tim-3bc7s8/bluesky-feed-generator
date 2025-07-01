import os
import sys
import time
import signal
import threading

from server import config
from server import data_stream

from flask import Flask, jsonify, request
from flask_cors import CORS
from atproto import Client as BskyClient

# from server.algos import algos
from server.data_filter import operations_callback
from server.database import init_db
from server import followed_users


# --- Pre-flight Checks ---

# 1. Define all required environment variables
required_env_vars = [
    'MYSQL_DATABASE', 'MYSQL_USER', 'MYSQL_PASSWORD', 'DB_HOST', 'DB_PORT',
    'HOSTNAME', 'HANDLE', 'PASSWORD', 'SERVICE_DID'
]

# 2. Check for any missing or empty variables
# This loop checks both for missing keys and empty strings.
missing_or_empty_vars = [
    var for var in required_env_vars if not os.environ.get(var)
]

if missing_or_empty_vars:
    print(f"FATAL: The following required environment variables are missing or empty: {', '.join(missing_or_empty_vars)}")
    sys.exit(1)

# 3. Now that we know DB_PORT exists and is not empty, validate its type.
db_port_str = os.environ.get('DB_PORT')
if not db_port_str.isdigit():
    print(f"FATAL: DB_PORT must be a number, but received: '{db_port_str}'")
    sys.exit(1)

# 4. If all checks pass, proceed with database connection.
# All variables are guaranteed to exist and be valid at this point.
db_name = os.environ.get('MYSQL_DATABASE')
db_user = os.environ.get('MYSQL_USER')
db_password = os.environ.get('MYSQL_PASSWORD')
db_host = os.environ.get('DB_HOST')

if not init_db(db_name, db_user, db_password, db_host, db_port_str):
    print("FATAL: Could not connect to the database after several attempts.")
    sys.exit(1)

print("Pre-flight checks passed. Starting application...")

# --- End of Pre-flight Checks ---


# Pre-populate the followed users list before starting threads
followed_users._fetch_and_update_followed_users()

app = Flask(__name__)
CORS(app) # Needed for local testing with browsers

stream_stop_event = threading.Event()
stream_thread = threading.Thread(
    target=data_stream.run, args=(config.SERVICE_DID, operations_callback, stream_stop_event,)
)
stream_thread.start()
# Start the thread to update the list of followed users
follower_update_stop_event = followed_users.start_follower_update_thread()

def sigint_handler(*_):
    print('Stopping data stream...')
    stream_stop_event.set()
    print('Stopping follower update thread...')
    follower_update_stop_event.set()
    sys.exit(0)


signal.signal(signal.SIGINT, sigint_handler)


@app.route('/')
def index():
    return 'ATProto Feed Generator powered by The AT Protocol SDK for Python (https://github.com/MarshalX/atproto).'


@app.route('/.well-known/did.json', methods=['GET'])
def did_json():
    if not config.SERVICE_DID.endswith(config.HOSTNAME):
        return '', 404

    return jsonify({
        '@context': ['https://www.w3.org/ns/did/v1'],
        'id': config.SERVICE_DID,
        'service': [
            {
                'id': '#bsky_fg',
                'type': 'BskyFeedGenerator',
                'serviceEndpoint': f'https://{config.HOSTNAME}'
            }
        ]
    })


@app.route('/xrpc/app.bsky.feed.describeFeedGenerator', methods=['GET'])
def describe_feed_generator():
    from server.algos import algos
    feeds = [{'uri': uri} for uri in algos.keys()]
    response = {
        'encoding': 'application/json',
        'body': {
            'did': config.SERVICE_DID,
            'feeds': feeds
        }
    }
    return jsonify(response)


@app.route('/xrpc/app.bsky.feed.getFeedSkeleton', methods=['GET'])
def get_feed_skeleton():
    from server.algos import algos
    feed = request.args.get('feed', default=None, type=str)
    algo = algos.get(feed)
    if not algo:
        return 'Unsupported algorithm', 400

    # Example of how to check auth if giving user-specific results:
    """
    from server.auth import AuthorizationError, validate_auth
    try:
        requester_did = validate_auth(request)
    except AuthorizationError:
        return 'Unauthorized', 401
    """

    try:
        cursor = request.args.get('cursor', default=None, type=str)
        limit = request.args.get('limit', default=20, type=int)
        body = algo(cursor, limit)
    except ValueError:
        return 'Malformed cursor', 400

    return jsonify(body)

# ENDPOINT FOR LOCAL VISUAL TESTING
@app.route('/get-feed-with-details', methods=['GET'])
def get_feed_with_details():
    HANDLE = os.environ.get('HANDLE')
    PASSWORD = os.environ.get('PASSWORD')
    from server.algos import algos
    feed_uri = request.args.get('feed', default=None, type=str)
    limit = request.args.get('limit', default=20, type=int)
    cursor = request.args.get('cursor', default=None, type=str)

    algo = algos.get(feed_uri)
    if not algo:
        return 'Unsupported algorithm', 400

    # 1. Get the skeleton from your algorithm
    skeleton = algo(cursor, limit)
    post_uris = [item['post'] for item in skeleton.get('feed', [])]

    if not post_uris:
        return jsonify({'posts': [], 'cursor': skeleton.get('cursor')})

    # 2. Fetch full post details from BlueSky's API
    try:
        # We create a new client and log in for each request.
        # This is simple and stateless.
        bsky_client = BskyClient()
        bsky_client.login(HANDLE, PASSWORD)
        
        response = bsky_client.app.bsky.feed.get_posts({'uris': post_uris})
        
        # Return the detailed posts and the cursor from your algorithm
        return jsonify({
            'posts': [post.dict() for post in response.posts],
            'cursor': skeleton.get('cursor')
        })

    except Exception as e:
        print(f"Error fetching post details from BlueSky: {e}")
        return f"Error fetching post details: {e}", 500