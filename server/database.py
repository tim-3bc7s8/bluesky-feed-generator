from datetime import datetime
import time
import peewee

# Create a temporary database proxy
# This allows us to define models without immediately connecting to a database.
db = peewee.Proxy()


class BaseModel(peewee.Model):
    class Meta:
        database = db


class Post(BaseModel):
    uri = peewee.CharField(index=True)
    cid = peewee.CharField()
    reply_parent = peewee.CharField(null=True, default=None)
    reply_root = peewee.CharField(null=True, default=None)
    indexed_at = peewee.DateTimeField(default=datetime.utcnow)


class SubscriptionState(BaseModel):
    service = peewee.CharField(unique=True)
    cursor = peewee.BigIntegerField()


def init_db(db_name, db_user, db_password, db_host, db_port, retries=5, delay=3):
    """
    Initialize the database.
    """
    for i in range(retries):
        try:
            print(f"Attempting to connect to the database (attempt {i + 1}/{retries})...")

            database_connection = peewee.MySQLDatabase(
                db_name,
                user=db_user,
                password=db_password,
                host=db_host,
                port=int(db_port)
            )

            db.initialize(database_connection)
            db.connect()
            db.create_tables([Post, SubscriptionState], safe=True)
            print("Database connection successful.")
            return True

        except peewee.OperationalError as e:
            print(f"Database connection failed: {e}")
            if i < retries - 1:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print("Max retries reached. Could not connect to the database.")
                return False

