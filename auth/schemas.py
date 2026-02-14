"""
=============================================================================
ownAgent - 用户数据模式模块
=============================================================================

本文件定义了用户认证相关的 Pydantic 数据模式：

1. Token - JWT 令牌响应模式
2. TokenData - JWT 令牌数据模式
3. UserBase - 用户基础属性模式
4. UserCreate - 用户创建请求模式
5. User - 用户响应模式

Pydantic 模式说明：
- 用于请求验证和响应序列化
- 自动生成 OpenAPI 文档
- 提供数据类型验证

设计��则：
- 请求和响应使用不同的模式
- 敏感信息（密码）不会出现在响应中
- 继承复用公共属性

作者: ownAgent Team
版本: 1.0.0
=============================================================================
"""

# =============================================================================
# 标准库导入
# =============================================================================

from typing import Optional  # 可选类型提示

# =============================================================================
# 第三方库导入
# =============================================================================

from pydantic import BaseModel  # Pydantic 基类

# =============================================================================
# 项目内部模块导入
# =============================================================================

from .models import UserRole  # 用户角色枚举


# =============================================================================
# 令牌相关模式
# =============================================================================

class Token(BaseModel):
    """
    JWT 令牌响应模式。
    
    当用户登录成功后，返回此格式的响应。
    客户端需要保存 access_token，用于后续请求认证。
    
    属性:
        access_token (str): 访问令牌
            - JWT 格式的字符串
            - 包含用户信息和过期时间
            - 需要在请求头中携带
        
        token_type (str): 令牌类型
            - 固定为 "bearer"
            - 表示使用 Bearer Token 认证方式
    
    使用示例:
        # 登录成功后返回
        {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer"
        }
        
        # 客户端使用
        # Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
    """
    access_token: str   # 访问令牌
    token_type: str     # 令牌类型，通常为 "bearer"


class TokenData(BaseModel):
    """
    JWT 令牌解码后的数据模式。
    
    用于解析和验证 JWT 令牌中的数据。
    
    属性:
        username (Optional[str]): 用户名
            - 从 JWT 的 "sub" (subject) 字段提取
            - 可能为空（无效令牌）
    
    JWT Payload 结构:
        {
            "sub": "username",     # 主题（用户名）
            "role": "user",        # 角色
            "exp": 1234567890      # 过期时间戳
        }
    
    使用示例:
        >>> # 解析 JWT
        >>> payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        >>> username = payload.get("sub")
        >>> token_data = TokenData(username=username)
    """
    username: Optional[str] = None  # 用户名，可能为空


# =============================================================================
# 用户相关模式
# =============================================================================

class UserBase(BaseModel):
    """
    用户基础属性模式。
    
    定义用户共有的基础属性，供其他模式继承。
    
    属性:
        username (str): 用户名
            - 用于登录
            - 唯一标识
    
    设计说明:
        - 作为基类被 UserCreate 和 User 继承
        - 遵循 DRY 原则（Don't Repeat Yourself）
    """
    username: str  # 用户名


class UserCreate(UserBase):
    """
    用户创建请求模式。
    
    用于注册新用户时的请求数据验证。
    继承自 UserBase，添加密码和角色字段。
    
    属性:
        username (str): 用户名（继承自 UserBase）
        
        password (str): 密码
            - 明文密码（仅用于请求）
            - 会被哈希后存储
            - 不会在响应中返回
        
        role (UserRole): 用户角色
            - 默认为 UserRole.USER
            - 只有管理员可以指定其他角色
    
    请求示例:
        POST /auth/users
        {
            "username": "newuser",
            "password": "secure123",
            "role": "user"  # 可选，默认为 "user"
        }
    
    安全说明:
        - 密码通过 HTTPS 传输
        - 服务端收到后立即哈希
        - 明文密码不会被存储或记录
    """
    password: str                    # 明文密码（仅用于创建）
    role: UserRole = UserRole.USER   # 用户角色，默认为普通用户


class User(UserBase):
    """
    用户响应模式。
    
    用于返回用户信息给客户端。
    继承自 UserBase，添加 ID、状态和角色字段。
    
    重要：不包含密码字段，确保敏感信息不会泄露。
    
    属性:
        username (str): 用户名（继承自 UserBase）
        
        id (int): 用户 ID
            - 唯一标识
            - 由数据库自动生成
        
        is_active (bool): 是否激活
            - True: 用户正常
            - False: 用户已禁用
        
        role (UserRole): 用户角色
            - ADMIN 或 USER
    
    响应示例:
        GET /auth/users/me
        {
            "id": 1,
            "username": "admin",
            "is_active": true,
            "role": "admin"
        }
    
    配置说明:
        from_attributes = True
            - 允许从 SQLAlchemy 模型创建
            - 原名 orm_mode (Pydantic v1)
            - 可以直接传入数据库模型对象
    """
    id: int                # 用户 ID
    is_active: bool        # 是否激活
    role: UserRole         # 用户角色

    class Config:
        """Pydantic 配置类"""
        # 允许从 ORM 模型创建
        # 可以直接传入 User 数据库模型对象
        from_attributes = True
