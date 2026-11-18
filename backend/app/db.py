from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .settings import settings

database_url = make_url(settings.database_url)
if database_url.drivername == "mysql":
    database_url = database_url.set(drivername="mysql+pymysql")
engine = create_engine(database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase): pass

def get_db():
    db=SessionLocal()
    try: yield db
    finally: db.close()
