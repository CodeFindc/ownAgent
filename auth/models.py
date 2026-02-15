"""
=============================================================================
ownAgent - 用户数据模型模块
=============================================================================

本文件定义了用户认证相关的数据库模型：

1. UserRole - 用户角色枚举
2. User - 用户数据库模型

数据库设计说明：
- 使用 SQLAlchemy ORM 框架
- 支持角色权限控制
- 密码以哈希形式存储，不存储明文

角色权限：
- ADMIN: 管理员，拥有所有权限，可以创建/删除用户
- USER: 普通用户，只能访问自己的数据

作者: ownAgent Team
版本: 1.0.0
=============================================================================
"""

# =============================================================================
# 标准库导入
# =============================================================================

import enum  # 枚举类型支持

# =============================================================================
# 第三方库导入
# =============================================================================

from sqlalchemy import Boolean, Column, Integer, String, Enum  # SQLAlchemy 数据类型

# =============================================================================
# 项目内部模块导入
# =============================================================================

from .database import Base  # 数据库基类


# =============================================================================
# 枚举定义
# =============================================================================

class UserRole(str, enum.Enum):
    """
    用户角色枚举类。
    
    定义系统中用户的角色类型，用于权限控制。
    继承 str 使其可以像字符串一样使用。
    
    属性:
        ADMIN (str): 管理员角色
            - 拥有所有权限
            - 可以创建/删除用户
            - 可以访问所有数据
        
        USER (str): 普通用户角色
            - 只能访问自己的数据
            - 不能管理其他用户
    
    使用示例:
        >>> role = UserRole.ADMIN
        >>> print(role.value)  # "admin"
        >>> if user.role == UserRole.ADMIN:
        ...     print("管理员")
    """
    ADMIN = "admin"  # 管理员，拥有所有权限
    USER = "user"    # 普通用户，仅访问自有数据


# =============================================================================
# 数据库模型定义
# =============================================================================

class User(Base):
    """
    用户数据库模型。
    
    对应数据库中的 users 表，存储用户的基本信息和认证数据。
    继承自 Base，由 SQLAlchemy 管理。
    
    表结构:
        users
        ├── id (Integer)        - 主键，自增
        ├── username (String)   - 用户名，唯一
        ├── hashed_password (String) - 密码哈希值
        ├── is_active (Boolean) - 是否激活
        └── role (String)       - 用户角色
    
    属性:
        __tablename__ (str): 数据库表名
        
        id (int): 用户唯一标识
            - 主键
            - 自动递增
            - 用于关联其他表
        
        username (str): 用户名
            - 唯一约束
            - 用于登录
            - 建立索引加速查询
        
        hashed_password (str): 密码哈希值
            - 存储的是密码的哈希值，不是明文
            - 使用 bcrypt 算法加密
            - 不可逆，只能验证
        
        is_active (bool): 是否激活
            - 默认为 True
            - 设为 False 可禁用用户
            - 禁用后无法登录
        
        role (str): 用户角色
            - 默认为 UserRole.USER
            - 值为 "admin" 或 "user"
            - 用于权限控制
    
    使用示例:
        >>> # 创建用户
        >>> new_user = User(
        ...     username="test",
        ...     hashed_password="hashed...",
        ...     role=UserRole.USER
        ... )
        >>> db.add(new_user)
        >>> db.commit()
    """
    # 数据库表名
    __tablename__ = "users"

    # 用户 ID - 主键，自增，建立索引
    id = Column(Integer, primary_key=True, index=True)
    
    # 用户名 - 唯一约束，建立索引加速查询
    username = Column(String, unique=True, index=True)
    # 新增邮箱字段
    email = Column(String, unique=True, index=True, nullable=True)
    # 头像 URL
    avatar_url = Column(String, nullable=True)
    
    # 密码哈希值 - 存储哈希后的密码，而非明文
    # 安全原则：永远不要存储明文密码
    hashed_password = Column(String)

    # 是否激活 - 默认为 True，可用于禁用用户
    is_active = Column(Boolean, default=True)
    
    # 用户角色 - 默认为普通用户
    role = Column(Enum(UserRole), default=UserRole.USER)


class SystemSetting(Base):
    """
    系统设置模型
    
    存储全系统的键值对配置，如:
    - site_logo: 网站 Logo URL
    - site_name: 网站名称
    """
    __tablename__ = "system_settings"

    key = Column(String, primary_key=True, index=True)
    value = Column(String)
