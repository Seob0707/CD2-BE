"""empty message

Revision ID: 77a0d61021d4
Revises: 52815e6a8735
Create Date: 2025-03-30 15:50:08.605580

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '77a0d61021d4'
down_revision: Union[str, None] = '52815e6a8735'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('language',
    sa.Column('lang_id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('lang_code', sa.String(length=10), nullable=True),
    sa.PrimaryKeyConstraint('lang_id')
    )
    op.create_table('setting',
    sa.Column('setting_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('thema', sa.Boolean(), nullable=False),
    sa.Column('memory', sa.Boolean(), nullable=False),
    sa.Column('language', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('setting_id')
    )
    op.create_table('topic',
    sa.Column('topic_id', sa.Integer(), nullable=False),
    sa.Column('topic_name', sa.String(length=20), nullable=False),
    sa.PrimaryKeyConstraint('topic_id')
    )
    op.create_table('user',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('login_info', sa.String(length=45), nullable=False),
    sa.Column('Oauth', sa.String(length=50), nullable=True),
    sa.Column('Oauth_id', sa.String(length=100), nullable=True),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('nickname', sa.String(length=50), nullable=True),
    sa.Column('password', sa.String(length=320), nullable=False),
    sa.Column('creat_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('modified_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('agree',
    sa.Column('agree_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('use_agree', sa.Boolean(), nullable=False),
    sa.Column('personal_information_agree', sa.Boolean(), nullable=False),
    sa.Column('date_agree', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.user_id'], ),
    sa.PrimaryKeyConstraint('agree_id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('language_setting',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('lang_id', sa.Integer(), nullable=False),
    sa.Column('setting_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['lang_id'], ['language.lang_id'], ),
    sa.ForeignKeyConstraint(['setting_id'], ['setting.setting_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('session',
    sa.Column('session_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=320), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.user_id'], ),
    sa.PrimaryKeyConstraint('session_id')
    )
    op.create_table('topic_session',
    sa.Column('topic_id', sa.Integer(), nullable=False),
    sa.Column('session_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['session.session_id'], ),
    sa.ForeignKeyConstraint(['topic_id'], ['topic.topic_id'], ),
    sa.PrimaryKeyConstraint('topic_id', 'session_id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('topic_session')
    op.drop_table('session')
    op.drop_table('language_setting')
    op.drop_table('agree')
    op.drop_table('user')
    op.drop_table('topic')
    op.drop_table('setting')
    op.drop_table('language')
    # ### end Alembic commands ###
