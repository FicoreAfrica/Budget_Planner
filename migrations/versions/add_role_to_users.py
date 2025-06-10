"""Add role column to users table

Revision ID: add_role_to_users
Revises: initial_schema
Create Date: 2025-06-10 08:51:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = 'add_role_to_users'
down_revision = 'initial_schema'
branch_labels = None
depends_on = None

def upgrade():
    # Add role column to users table
    op.add_column(
        'users',
        sa.Column('role', sa.String(length=20), nullable=False, server_default='user')
    )
    
    # Update existing users to set role='admin' where is_admin=True
    op.execute("UPDATE users SET role = 'admin' WHERE is_admin = true")

def downgrade():
    # Drop role column from users table
    op.drop_column('users', 'role')
