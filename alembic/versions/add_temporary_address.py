"""Add temporary address fields to employees2 table

Revision ID: add_temporary_address
Revises: add_medical_details
Create Date: 2024-01-01 15:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_temporary_address'
down_revision = 'add_medical_details'
branch_labels = None
depends_on = None


def upgrade():
    """Add temporary address fields to employees2 table."""
    op.add_column('employees2', sa.Column('temp_village', sa.Text(), nullable=True))
    op.add_column('employees2', sa.Column('temp_post_office', sa.Text(), nullable=True))
    op.add_column('employees2', sa.Column('temp_thana', sa.Text(), nullable=True))
    op.add_column('employees2', sa.Column('temp_tehsil', sa.Text(), nullable=True))
    op.add_column('employees2', sa.Column('temp_district', sa.Text(), nullable=True))
    op.add_column('employees2', sa.Column('temp_city', sa.Text(), nullable=True))
    op.add_column('employees2', sa.Column('temp_phone', sa.Text(), nullable=True))
    op.add_column('employees2', sa.Column('temp_address_details', sa.Text(), nullable=True))
    op.add_column('employees2', sa.Column('address_details', sa.Text(), nullable=True))


def downgrade():
    """Remove temporary address fields from employees2 table."""
    op.drop_column('employees2', 'temp_village')
    op.drop_column('employees2', 'temp_post_office')
    op.drop_column('employees2', 'temp_thana')
    op.drop_column('employees2', 'temp_tehsil')
    op.drop_column('employees2', 'temp_district')
    op.drop_column('employees2', 'temp_city')
    op.drop_column('employees2', 'temp_phone')
    op.drop_column('employees2', 'temp_address_details')
    op.drop_column('employees2', 'address_details')
