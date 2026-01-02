"""Add medical_details column to employees2 table

Revision ID: add_medical_details
Revises: add_employee_attachments
Create Date: 2024-01-01 15:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_medical_details'
down_revision = 'add_employee_attachments'
branch_labels = None
depends_on = None


def upgrade():
    """Add medical_details column to employees2 table."""
    op.add_column('employees2', sa.Column('medical_details', sa.Text(), nullable=True))


def downgrade():
    """Remove medical_details column from employees2 table."""
    op.drop_column('employees2', 'medical_details')
