from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLite 数据库地址
SQLALCHEMY_DATABASE_URL = "sqlite:///./auth.db"

# 创建数据库引擎
# check_same_thread=False 是 SQLite 在多线程环境下的特殊配置
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# 创建 SessionLocal 类，用于后续实例化数据库会话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建 Base 类，供模型继承
Base = declarative_base()

def get_db():
    """
    FastAPI 依赖项：获取数据库会话。
    在请求开始时创建会话，请求结束时自动关闭。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
