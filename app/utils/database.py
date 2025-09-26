from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.models import Base

# ✅ MySQL Database URL

DATABASE_URL = "mysql+pymysql://sameerbangkokumeed:Sameer1313umeed@localhost/umeed_web1"

# Example:
#DATABASE_URL = "mysql+pymysql://root:Love1718@localhost/umeed_web1"

# ✅ Create engine and session
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Checks connection before using it
    #pool_pre_ping=True,
    pool_size=0,  # No persistent connections
    max_overflow=-1,  # Unlimited overflow (temporary) connections
    echo=True #or SQL logs during dev
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ✅ Create DB Session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ✅ Create tables on DB Init
def init_db():
    Base.metadata.create_all(bind=engine)
