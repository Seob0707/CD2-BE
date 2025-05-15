from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.database import Base
from datetime import datetime
from api.models.file_upload import File


class Language(Base):
    __tablename__ = 'language'

    lang_id = Column(Integer, primary_key=True, autoincrement=True)
    lang_code = Column(String(10), nullable=True)

    language_settings = relationship('LanguageSetting', back_populates='language')


class Setting(Base):
    __tablename__ = 'setting'

    setting_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    thema = Column(Boolean, nullable=False, default=True)
    memory = Column(Boolean, nullable=False, default=True)
    language = Column(Integer, nullable=False, default=1)

    language_settings = relationship('LanguageSetting', back_populates='setting')


class LanguageSetting(Base):
    __tablename__ = 'language_setting'

    id = Column(Integer, primary_key=True, autoincrement=True)
    lang_id = Column(Integer, ForeignKey('language.lang_id'), nullable=False)
    setting_id = Column(Integer, ForeignKey('setting.setting_id'), nullable=False)

    language = relationship('Language', back_populates='language_settings')
    setting = relationship('Setting', back_populates='language_settings')


class User(Base):
    __tablename__ = 'user'

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    login_info = Column(String(45), nullable=False)
    Oauth = Column(String(50), nullable=True)
    Oauth_id = Column(String(100), nullable=True)
    email = Column(String(320), nullable=False)
    nickname = Column(String(50), nullable=True)
    password = Column(String(320), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    modified_date = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    role = Column(String(20), nullable=False, server_default="user")
    refresh_token = Column(String(512), nullable=True)

    sessions = relationship('Session', back_populates='user')  
    agree = relationship('Agree', back_populates='user', uselist=False)  

class Session(Base):
    __tablename__ = 'session'
    session_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.user_id'), nullable=False)
    title = Column(String(320), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    modify_at = Column(DateTime(timezone=True), nullable=True, server_default=func.now(), onupdate=func.now())

    user = relationship('User', back_populates='sessions')
    topic_sessions = relationship('TopicSession', back_populates='session', cascade="all, delete-orphan")
    files = relationship("File", back_populates="session", cascade="all, delete-orphan")
    
    topics = relationship("Topic", secondary="topic_session", viewonly=True, lazy="selectin")


class Topic(Base):
    __tablename__ = 'topic'

    topic_id = Column(Integer, primary_key=True, autoincrement=True)
    topic_name = Column(String(20), nullable=False)

    topic_sessions = relationship('TopicSession', back_populates='topic')


class TopicSession(Base):
    __tablename__ = 'topic_session'

    topic_id = Column(Integer, ForeignKey('topic.topic_id'), primary_key=True)
    session_id = Column(Integer, ForeignKey('session.session_id'), primary_key=True)

    topic = relationship('Topic', back_populates='topic_sessions')
    session = relationship('Session', back_populates='topic_sessions')


class Agree(Base):
    __tablename__ = 'agree'

    agree_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.user_id'), nullable=False, unique=True)
    use_agree = Column(Boolean, nullable=False, default=True)
    personal_information_agree = Column(Boolean, nullable=False, default=True)
    date_agree = Column(Boolean, nullable=False, default=True)

    user = relationship('User', back_populates='agree')
