"""Group Identification

Revision ID: 1c44263565e2
Revises: ebf6535f2ca8
Create Date: 2025-01-23 20:04:08.208492

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c44263565e2'
down_revision: Union[str, None] = 'ebf6535f2ca8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('group_identification',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('group', sa.String(), nullable=False),
    sa.Column('_scene_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['_scene_id'], ['scene.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('group_identification_performer',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('_group_identification_id', sa.Integer(), nullable=False),
    sa.Column('_performer_id', sa.Integer(), nullable=False),
    sa.Column('score', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['_group_identification_id'], ['group_identification.id'], ),
    sa.ForeignKeyConstraint(['_performer_id'], ['performer.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('group_identification_performer')
    op.drop_table('group_identification')
    # ### end Alembic commands ###
