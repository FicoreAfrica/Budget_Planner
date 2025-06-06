import os
import logging
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from models import db

# Set up logging
logger = logging.getLogger('alembic.env')
logger.setLevel(logging.INFO)

# Alembic Config object
config = context.config

# Ensure data directory exists
data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
try:
    os.makedirs(data_dir, exist_ok=True)
    logger.info(f"Ensured database directory exists at {data_dir}")
except OSError as e:
    logger.error(f"Failed to create database directory {data_dir}: {str(e)}")
    raise

# Set sqlalchemy.url from DATABASE_URL or default SQLite path
default_db_path = os.path.join(data_dir, 'ficore.db')
db_url = os.environ.get('DATABASE_URL', f'sqlite:///{default_db_path}')
config.set_main_option('sqlalchemy.url', db_url)
logger.info(f"Using database URL: {db_url}")

# Check if database file is writable
try:
    if db_url.startswith('sqlite:///'):
        db_path = db_url.replace('sqlite:///', '')
        with open(db_path, 'a'):
            pass
        logger.info(f"Database file {db_path} is writable")
except OSError as e:
    logger.error(f"Database file {db_path} is not writable: {str(e)}")
    raise

# Configure Python logging from alembic.ini
fileConfig(config.config_file_name)

# Set target metadata
target_metadata = db.metadata

# Create engine
connectable = engine_from_config(
    config.get_section(config.config_ini_section),
    prefix='sqlalchemy.',
    poolclass=pool.NullPool)

def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    logger.info("Running migrations in offline mode")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Run migrations in 'online' mode."""
    logger.info("Running migrations in online mode")
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
