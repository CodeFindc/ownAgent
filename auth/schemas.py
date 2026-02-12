from pydantic import BaseModel
from typing import Optional
from .models import UserRole

class Token(BaseModel):
    """返回给客户端的 Token 响应结构"""
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """JWT Token 解码后的数据结构"""
    username: Optional[str] = None

class UserBase(BaseModel):
    """用户基础属性"""
    username: str

class UserCreate(UserBase):
    """用户创建请求模型 (注册时使用)"""
    password: str
    role: UserRole = UserRole.USER

class User(UserBase):
    """用户响应模型 (返回给前端，不含密码)"""
    id: int
    is_active: bool
    role: UserRole

    class Config:
        from_attributes = True
