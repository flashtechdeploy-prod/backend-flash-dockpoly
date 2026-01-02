"""Merge heads: payroll OT bonus + employees2 address

Revision ID: merge_heads_payroll_ot_bonus_and_employees2
Revises: add_ot_bonus_amount_to_payroll_sheet_entries, add_temporary_address
Create Date: 2026-01-01 00:00:01.000000

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "merge_heads_payroll_ot_bonus_and_employees2"
down_revision = ("add_ot_bonus_amount_to_payroll_sheet_entries", "add_temporary_address")
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge revision; no schema changes.
    pass


def downgrade():
    # Downgrade is a no-op for merge revision.
    pass
