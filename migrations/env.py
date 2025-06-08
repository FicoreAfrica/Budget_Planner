from logging.config import fileConfig
import os
from sqlalchemy import engine_from_config, pool
from alembic import context
from app import db
from models import User, Course, FinancialHealth, Budget, Bill, NetWorth, EmergencyFund, LearningProgress, QuizResult, Feedback

# Alembic Config object
config = context.config

# Set up logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set SQLAlchemy URL from environment variable or default to SQLite
database_url = os.getenv('DATABASE_URL', 'sqlite:///ficore.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
config.set_main_option('sqlalchemy.url', database_url)

# Create engine
try:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=db.metadata
        )

        with context.begin_transaction():
            context.run_migrations()
except Exception as e:
    print(f"Error connecting to database: {str(e)}")
    raise
