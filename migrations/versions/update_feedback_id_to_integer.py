"""Update feedback table id to Integer with autoincrement

Revision ID: update_feedback_id_to_integer
Revises: initial_schema
Create Date: 2025-06-07 19:08:00
"""

from alembic import op
import sqlalchemy as sa

revision = 'update_feedback_id_to_integer'
down_revision = 'initial_schema'
branch_labels = None
depends_on = None

def upgrade():
    # Create a new temporary table with the updated schema
    op.create_table(
        'feedback_new',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('tool_name', sa.String(length=50), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_feedback_session_id', 'feedback_new', ['session_id'], unique=False)
    op.create_index('ix_feedback_user_id', 'feedback_new', ['user_id'], unique=False)

    # Copy data from old feedback table to new one (if any)
    op.execute("""
        INSERT INTO feedback_new (user_id, session_id, created_at, tool_name, rating, comment)
        SELECT user_id, session_id, created_at, tool_name, rating, comment
        FROM feedback
    """)

    # Drop the old feedback table
    op.drop_table('feedback')

    # Rename the new table to feedback
    op.rename_table('feedback_new', 'feedback')

def downgrade():
    # Create a new temporary table with the original schema
    op.create_table(
        'feedback_old',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('tool_name', sa.String(length=50), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_feedback_session_id', 'feedback_old', ['session_id'], unique=False)
    op.create_index('ix_feedback_user_id', 'feedback_old', ['user_id'], unique=False)

    # Copy data from current feedback table to old schema
    op.execute("""
        INSERT INTO feedback_old (id, user_id, session_id, created_at, tool_name, rating, comment)
        SELECT CAST(id AS VARCHAR(36)), user_id, session_id, created_at, tool_name, rating, comment
        FROM feedback
    """)

    # Drop the current feedback table
    op.drop_table('feedback')

    # Rename the old table to feedback
    op.rename_table('feedback_old', 'feedback')
