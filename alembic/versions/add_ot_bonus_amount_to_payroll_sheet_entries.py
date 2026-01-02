"""Add ot_bonus_amount to payroll_sheet_entries

Revision ID: add_ot_bonus_amount_to_payroll_sheet_entries
Revises: add_temporary_address
Create Date: 2026-01-01 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_ot_bonus_amount_to_payroll_sheet_entries"
down_revision = "1eaca84a43ef"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "payroll_sheet_entries",
        sa.Column("ot_bonus_amount", sa.Float(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_column("payroll_sheet_entries", "ot_bonus_amount")
