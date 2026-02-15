from app.database import engine
from app.models import metadata
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    logger.info("Creating tables in local database...")
    metadata.create_all(bind=engine)
    logger.info("Tables created successfully!")

if __name__ == "__main__":
    init_db()
