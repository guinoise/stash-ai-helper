"""Images scene

Revision ID: b62fa3d9cda9
Revises: 64782571f628
Create Date: 2025-01-17 02:11:13.049284

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b62fa3d9cda9'
down_revision: Union[str, None] = '64782571f628'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('scenes_images',
    sa.Column('scene_id', sa.Integer(), nullable=False),
    sa.Column('image_phash', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['image_phash'], ['image.phash'], ),
    sa.ForeignKeyConstraint(['scene_id'], ['scene.id'], ),
    sa.PrimaryKeyConstraint('scene_id', 'image_phash')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('scenes_images')
    # ### end Alembic commands ###
