import os
import sys
import time
from dotenv import load_dotenv
from alembic.config import Config
from alembic import command
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
import asyncio
import traceback
import subprocess

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def wait_for_db(max_retries=5, retry_interval=5):
    """Wait for the database to be ready."""
    db_url = f"postgresql+asyncpg://{os.getenv('POSTGRES_USER', 'postgres')}:{os.getenv('POSTGRES_PASSWORD', 'postgres')}@{os.getenv('POSTGRES_HOST', 'db')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'doorbell')}"
    
    logger.info(f"Attempting to connect to database at {os.getenv('POSTGRES_HOST', 'db')}:{os.getenv('POSTGRES_PORT', '5432')}")
    
    for attempt in range(max_retries):
        try:
            engine = create_async_engine(db_url)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                logger.info("Database is ready!")
                return True
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Database not ready, retrying in {retry_interval} seconds... (Attempt {attempt + 1}/{max_retries})")
                logger.warning(f"Error: {str(e)}")
                await asyncio.sleep(retry_interval)
            else:
                logger.error(f"Could not connect to database after {max_retries} attempts: {e}")
                return False

def run_migrations():
    try:
        logger.info("Starting migration process...")
        
        # Wait for database to be ready
        if not asyncio.run(wait_for_db()):
            logger.error("Failed to connect to database. Exiting...")
            sys.exit(1)

        # Get the directory containing this script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        logger.info(f"Current directory: {current_dir}")
        
        # Create Alembic configuration
        alembic_ini_path = os.path.join(current_dir, "alembic.ini")
        logger.info(f"Loading Alembic config from: {alembic_ini_path}")
        alembic_cfg = Config(alembic_ini_path)
        
        # Run the migration using subprocess to capture output
        logger.info("Starting database migrations...")
        try:
            # First, try to run alembic directly to see if it works
            result = subprocess.run(
                ["alembic", "upgrade", "head"],
                cwd=current_dir,
                capture_output=True,
                text=True,
                check=True
            )
            logger.info("Alembic output:")
            logger.info(result.stdout)
            if result.stderr:
                logger.warning("Alembic stderr:")
                logger.warning(result.stderr)
            logger.info("Database migrations completed successfully!")
        except subprocess.CalledProcessError as e:
            logger.error(f"Alembic command failed with exit code {e.returncode}")
            logger.error("Alembic stdout:")
            logger.error(e.stdout)
            logger.error("Alembic stderr:")
            logger.error(e.stderr)
            raise
        
    except Exception as e:
        logger.error(f"Error running migrations: {str(e)}")
        logger.error("Traceback:")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    run_migrations() 