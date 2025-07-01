from server.database import Post
from datetime import datetime

# This is the handler that will be called by the BlueSky API
def handler(cursor: str, limit: int) -> dict:
    """
    The main handler for your feed algorithm.

    This implementation returns a reverse-chronological feed of all posts
    stored in the database.

    Args:
        cursor: The cursor for pagination. It's a timestamp from the last post of the previous page.
        limit: The number of items to return, with a default of 20.

    Returns:
        A dictionary containing the feed posts and an optional cursor for the next page.
    """
    
    # Start building the database query using Peewee
    # We select the post's URI and when it was indexed
    query = (
        Post.select(Post.uri, Post.indexed_at)
        .order_by(Post.indexed_at.desc()) # Order by newest first
        .limit(limit)
    )

    # If a cursor is provided, we use it to get the next page of results.
    # The cursor is the 'indexed_at' timestamp of the last post from the previous page.
    if cursor:
        # The 'try-except' block handles cases where the cursor might be malformed.
        try:
            # Parse the cursor string back into a datetime object
            cursor_datetime = datetime.fromisoformat(cursor.replace('Z', '+00:00'))
            # Add a 'where' clause to fetch posts older than the cursor
            query = query.where(Post.indexed_at < cursor_datetime)
        except ValueError:
            # If the cursor is invalid, we can just return an empty feed
            # or handle the error as we see fit.
            return {'feed': []}

    # Execute the query and fetch the posts
    posts = list(query)

    # Prepare the list of post URIs to return
    feed = [{'post': post.uri} for post in posts]

    # Determine the cursor for the next page
    next_cursor = None
    if posts:
        # The next cursor is the timestamp of the last post in the current list
        # We format it as an ISO 8601 string, which is a common standard.
        next_cursor = posts[-1].indexed_at.isoformat().replace('+00:00', 'Z')

    return {
        'feed': feed,
        'cursor': next_cursor  # This will be None if there are no more posts
    }