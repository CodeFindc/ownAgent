from sqlalchemy import Boolean, Column, Integer, String, Enum
from .database import Base
import enum

class UserRole(str, enum.Enum):
    """用户角色枚举"""
    ADMIN = "admin"  # 管理员，拥有所有权限
    USER = "user"    # 普通用户，仅访问自有数据

class User(Base):
    """
    用户数据库模型
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)  # 存储哈希后的密码，而非明文
    is_active = Column(Boolean, default=True)
    role = Column(String, default=UserRole.USER)
