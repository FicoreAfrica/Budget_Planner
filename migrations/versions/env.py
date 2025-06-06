import os
import logging
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from models import db  # Import the db instance from models.py

# Set up logging
logger = logging.getLogger('alembic.env')

# This is the Alembic Config object, which provides access to the values within the .ini file in use.
config = context.config

# Ensure the data directory exists for the default SQLite path
data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
try:
    os.makedirs(data_dir, exist_ok=True)
    logger.info(f"Ensured database directory exists at {data_dir}")
except (PermissionError, OSError) as e:
    logger.error(f"Failed to create database directory {data_dir}: {str(e)}")
    raise

# Set the sqlalchemy.url from environment variable DATABASE_URL if available
# Fallback to a default SQLite path if not set
default_db_path = os.path.join(data_dir, 'ficore.db')
db_url = os.environ.get('DATABASE_URL', f'sqlite:///{default_db_path}')
config.set_main_option('sqlalchemy.url', db_url)
logger.info(f"Using database URL: {db_url}")

# Interpret the config file for Python logging.
fileConfig(config.config_file_name)

# Add your model's MetaData object here for 'autogenerate' support
target_metadata = db.metadata

# Get the database URL from the config (now set from environment or default)
connectable = engine_from_config(
    config.get_section(config.config_ini_section),
    prefix='sqlalchemy.',
    poolclass=pool.NullPool)

def run_migrations_offline():
    """Run migrations in 'offline' mode.
    
    This configures the context with just a URL and not an Engine, suitable for SQLite
    where transactions are not needed in the same way.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Run migrations in 'online' mode.
    
    In this scenario, we need to create an Engine and associate a connection with the context.
    """
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
