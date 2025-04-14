import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from models import Base, Profile, Location

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/daterDB"

def log_table_schema(engine, table_name: str) -> None:
    """Log detailed schema information for a table"""
    inspector = inspect(engine)
    columns = inspector.get_columns(table_name)
    
    logger.info(f"\n📊 Schema for table '{table_name}':")
    logger.info("-" * 50)
    for column in columns:
        nullable = "NULL" if column['nullable'] else "NOT NULL"
        logger.info(f"  • {column['name']}: {column['type']} {nullable}")
    logger.info("-" * 50)

def init_db():
    """Initialize the database and create tables"""
    try:
        # Create engine
        engine = create_engine(DATABASE_URL)
        
        # Drop existing tables safely
        with engine.connect() as conn:
            logger.info("🗑️ Dropping existing tables...")
            conn.execute(text("DROP TABLE IF EXISTS profiles CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS locations CASCADE"))
            conn.commit()
            logger.info("✅ Tables dropped successfully")
        
        # Create all tables
        logger.info("\n🏗️ Creating new tables...")
        Base.metadata.create_all(engine)
        logger.info("✅ Tables created successfully")
        
        # Log schema for each table
        log_table_schema(engine, "profiles")
        log_table_schema(engine, "locations")
        
    except Exception as e:
        logger.error(f"❌ Error initializing database: {str(e)}")
        raise

if __name__ == "__main__":
    init_db() 