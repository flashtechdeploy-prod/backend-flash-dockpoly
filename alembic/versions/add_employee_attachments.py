"""Add missing attachment columns to employees2 table

Revision ID: add_employee_attachments
Revises: 
Create Date: 2024-01-01 14:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_employee_attachments'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add missing attachment columns to employees2 table."""
    # Add personal signature attachment column
    op.add_column('employees2', sa.Column('personal_signature_attachment', sa.Text(), nullable=True))
    
    # Add fingerprint attachment columns
    op.add_column('employees2', sa.Column('fingerprint_thumb_attachment', sa.Text(), nullable=True))
    op.add_column('employees2', sa.Column('fingerprint_index_attachment', sa.Text(), nullable=True))
    op.add_column('employees2', sa.Column('fingerprint_middle_attachment', sa.Text(), nullable=True))
    op.add_column('employees2', sa.Column('fingerprint_ring_attachment', sa.Text(), nullable=True))
    op.add_column('employees2', sa.Column('fingerprint_pinky_attachment', sa.Text(), nullable=True))
    
    # Add employment agreement attachment column
    op.add_column('employees2', sa.Column('employment_agreement_attachment', sa.Text(), nullable=True))


def downgrade():
    """Remove the added attachment columns."""
    # Remove personal signature attachment column
    op.drop_column('employees2', 'personal_signature_attachment')
    
    # Remove fingerprint attachment columns
    op.drop_column('employees2', 'fingerprint_thumb_attachment')
    op.drop_column('employees2', 'fingerprint_index_attachment')
    op.drop_column('employees2', 'fingerprint_middle_attachment')
    op.drop_column('employees2', 'fingerprint_ring_attachment')
    op.drop_column('employees2', 'fingerprint_pinky_attachment')
    
    # Remove employment agreement attachment column
    op.drop_column('employees2', 'employment_agreement_attachment')
