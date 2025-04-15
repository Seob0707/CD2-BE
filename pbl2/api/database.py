import os
import ssl
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
from api.config import settings

load_dotenv()


DB_USER = os.getenv("DB_user")
DB_PASSWORD = os.getenv("DB_password")
DB_HOST = os.getenv("DB_host")
DB_PORT = os.getenv("DB_port", "3306")
DATABASE = "demo"  

ssl_context = None
if settings.environment == "production" and settings.db_ssl_ca:
    ssl_context = ssl.create_default_context(cafile=settings.db_ssl_ca)
   
    if settings.db_ssl_cert and settings.db_ssl_key:
        ssl_context.load_cert_chain(certfile=settings.db_ssl_cert, keyfile=settings.db_ssl_key)


ASYNC_DB_URL = f"mysql+aiomysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DATABASE}?charset=utf8"


connect_args = {}
if ssl_context:
    connect_args["ssl"] = ssl_context

async_engine = create_async_engine(
    ASYNC_DB_URL,
    echo=True,
    connect_args=connect_args
)

async_session = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with async_session() as session:
        yield session
