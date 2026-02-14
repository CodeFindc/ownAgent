"""
=============================================================================
ownAgent - 数据库配置模块
=============================================================================

本文件实现了数据库的连接和会话管理：

1. 数据库引擎配置
2. 会话工厂配置
3. 数据库基类定义
4. 依赖注入函数

数据库设计说明：
- 使用 SQLite 作为数据库（轻量级，无需安装）
- 使用 SQLAlchemy ORM 框架
- 支持会话管理和依赖注入

SQLAlchemy 架构：
- Engine: 数据库连接引擎
- SessionLocal: 会话工厂类
- Base: 模型基类
- get_db: 依赖注入函���

作者: ownAgent Team
版本: 1.0.0
=============================================================================
"""

# =============================================================================
# 第三方库导入
# =============================================================================

from sqlalchemy import create_engine  # 创建数据库引擎
from sqlalchemy.orm import sessionmaker, declarative_base  # 会话管理和基类


# =============================================================================
# 数据库配置
# =============================================================================

# SQLite 数据库连接字符串
# 格式: sqlite:///./相对路径/数据库文件.db
# ./auth.db 表示在当前目录下创建 auth.db 文件
# SQLite 是文件数据库，无需启动数据库服务
SQLALCHEMY_DATABASE_URL = "sqlite:///./auth.db"

# 创建数据库引擎
# engine 是数据库连接的核心，负责：
# - 管理连接池
# - 执行 SQL 语句
# - 处理数据库通信
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    # SQLite 特殊配置
    # check_same_thread=False 允许在多线程环境中使用同一个连接
    # 默认情况下 SQLite 只允许创建它的线程使用连接
    # 设置为 False 可以在 FastAPI 的异步环境中正常工作
    connect_args={"check_same_thread": False}
)

# 创建会话工厂类
# SessionLocal 是一个工厂类，用于创建数据库会话实例
# 每个请求应该有自己独立的会话
SessionLocal = sessionmaker(
    autocommit=False,  # 不自动提交，需要手动 commit
    autoflush=False,   # 不自动刷新，需要手动 flush
    bind=engine        # 绑定到数据库引擎
)

# 创建声明式基类
# 所有数据库模型都继承自这个基类
# Base 包含了 ORM 映射的元数据
Base = declarative_base()


# =============================================================================
# 依赖注入函数
# =============================================================================

def get_db():
    """
    FastAPI 依赖项：获取数据库会话。
    
    这是一个生成器函数，用于 FastAPI 的依赖注入系统。
    在请求开始时创建会话，请求结束时自动关闭。
    
    工作流程:
        1. 请求进入 -> 创建数据库会话
        2. 处理请求 -> 使用会话操作数据库
        3. 请求结束 -> 关闭会话（无论成功或失败）
    
    使用示例:
        @router.get("/users")
        def get_users(db: Session = Depends(get_db)):
            # db 是自动注入的数据库会话
            users = db.query(User).all()
            return users
    
    异常处理:
        - try 块中的代码可能抛出异常
        - finally 确保会话总是被关闭
        - 异常会被 FastAPI 的异常处理器捕获
    
    为什么使用生成器:
        - yield 之前的代码在请求开始时执行
        - yield 返回的值被注入到路由函数
        - yield 之后的代码在请求结束时执行
        - 确保资源正确释放
    
    返回:
        Generator[Session, None, None]: 数据库会话生成器
    """
    # 创建新的数据库会话
    db = SessionLocal()
    try:
        # 使用 yield 返回会话
        # FastAPI 会在请求处理完成后继续执行 finally 块
        yield db
    finally:
        # 确保会话被关闭
        # 释放数据库连接回连接池
        db.close()


# =============================================================================
# 数据库初始化函数
# =============================================================================

def init_db():
    """
    初始化数据库表结构。
    
    创建所有定义的表。通常在应用启动时调用。
    
    使用示例:
        # 在 main.py 中
        from auth.database import init_db
        init_db()
    
    注意:
        - 只创建不存在的表
        - 不会修改已存在的表结构
        - 生产环境建议使用数据库迁移工具（如 Alembic）
    """
    # 创建所有表
    # Base.metadata 包含所有模型的元数据
    # create_all 会创建所有继承自 Base 的模型对应的表
    Base.metadata.create_all(bind=engine)


def get_engine():
    """
    获取数据库引擎实例。
    
    用于需要直接操作引擎的场景。
    
    返回:
        Engine: SQLAlchemy 数据库引擎
    """
    return engine


def get_base():
    """
    获取声明式基类。
    
    用于定义模型时导入。
    
    返回:
        DeclarativeMeta: 声明式基类
    """
    return Base
