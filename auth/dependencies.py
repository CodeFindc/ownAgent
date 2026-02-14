"""
=============================================================================
ownAgent - 认证依赖模块
=============================================================================

本文件实现了 FastAPI 的认证依赖注入：

1. OAuth2 密码模式配置
2. get_current_user - 获取当前用户
3. get_current_active_user - 获取当前活跃用户
4. get_current_admin_user - 获取当前管理员用户

依赖注入说明：
- FastAPI 使用 Depends() 实现依赖注入
- 依赖可以链式调用（如 admin 依赖 active 依赖 current）
- 自动处理异常和错误响应

认证流程：
1. 客户端请求携带 Bearer Token
2. OAuth2PasswordBearer 提取 Token
3. 解码 JWT 获取用户名
4. 查询数据库获取用户
5. 验证用户状态和权限

作者: ownAgent Team
版本: 1.0.0
=============================================================================
"""

# =============================================================================
# 第三方库导入
# =============================================================================

from fastapi import Depends, HTTPException, status  # FastAPI 核心组件
from fastapi.security import OAuth2PasswordBearer  # OAuth2 认证方案
from jose import JWTError, jwt  # JWT 处理
from sqlalchemy.orm import Session  # SQLAlchemy 会话类型

# =============================================================================
# 项目内部模块导入
# =============================================================================

from . import schemas, security, models, database


# =============================================================================
# OAuth2 认证方案配置
# =============================================================================

# 创建 OAuth2 密码模式实例
# tokenUrl 指定获取令牌的端点
# 客户端需要先通过此端点获取令牌
# 完整 URL 为: http://host:port/auth/token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


# =============================================================================
# 依赖注入函数
# =============================================================================

def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: Session = Depends(database.get_db)
) -> models.User:
    """
    FastAPI 依赖项：从请求头解析 JWT 并获取当前用户。
    
    这是最基础的认证依赖，其他认证依赖都基于此。
    
    参数:
        token (str): OAuth2 自动从请求头提取的令牌
            - 请求头格式: Authorization: Bearer <token>
            - 由 OAuth2PasswordBearer 自动处理
        
        db (Session): 数据库会话
            - 由 get_db 依赖注入
            - 用于查询用户信息
    
    返回:
        models.User: 当前登录用户对象
    
    异常:
        HTTPException 401: 令牌无效或用户不存在
    
    工作流程:
        1. 从请求头提取 Bearer Token
        2. 解码 JWT 获取用户名
        3. 从数据库查询用户
        4. 返回用户对象
    
    使用示例:
        @router.get("/profile")
        def get_profile(user: User = Depends(get_current_user)):
            return {"username": user.username}
    
    错误响应:
        HTTP 401 Unauthorized
        {
            "detail": "Could not validate credentials"
        }
    """
    # 创建认证异常
    # 包含 WWW-Authenticate 头，告诉客户端需要 Bearer 认证
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 解码 JWT 令牌
        # 使用密钥和算法验证签名
        payload = jwt.decode(
            token, 
            security.SECRET_KEY, 
            algorithms=[security.ALGORITHM]
        )
        
        # 提取用户名（subject）
        username: str = payload.get("sub")
        
        # 检查用户名是否存在
        if username is None:
            raise credentials_exception
        
        # 创建令牌数据对象
        token_data = schemas.TokenData(username=username)
        
    except JWTError:
        # JWT 解码失败（格式错误、签名错误、过期等）
        raise credentials_exception
    
    # 从数据库查询用户
    user = db.query(models.User).filter(
        models.User.username == token_data.username
    ).first()
    
    # 检查用户是否存在
    if user is None:
        raise credentials_exception
    
    return user


def get_current_active_user(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """
    获取当前活跃用户。
    
    在 get_current_user 基础上增加活跃状态检查。
    已禁用的用户无法通过此检查。
    
    参数:
        current_user (models.User): 当前用户
            - 由 get_current_user 依赖注入
            - 已经通过 JWT 验证
    
    返回:
        models.User: 当前活跃用户对象
    
    异常:
        HTTPException 400: 用户已被禁用
    
    使用场景:
        - 需要用户登录的功能
        - 不需要管理员权限的功能
        - 大部分用户操作
    
    使用示例:
        @router.post("/chat")
        def chat(
            message: str,
            user: User = Depends(get_current_active_user)
        ):
            return {"response": "..."}
    
    错误响应:
        HTTP 400 Bad Request
        {
            "detail": "Inactive user"
        }
    """
    # 检查用户是否激活
    if not current_user.is_active:
        raise HTTPException(
            status_code=400, 
            detail="Inactive user"
        )
    
    return current_user


def get_current_admin_user(
    current_user: models.User = Depends(get_current_active_user)
) -> models.User:
    """
    获取当前管理员用户。
    
    在 get_current_active_user 基础上增加角色检查。
    只有管理员才能通过此检查。
    
    参数:
        current_user (models.User): 当前活跃用户
            - 由 get_current_active_user 依赖注入
            - 已经是活跃用户
    
    返回:
        models.User: 当前管理员用户对象
    
    异常:
        HTTPException 403: 权限不足
    
    使用场景:
        - 用户管理功能
        - 系统配置功能
        - 需要管理员权限的操作
    
    使用示例:
        @router.post("/users")
        def create_user(
            user_data: UserCreate,
            admin: User = Depends(get_current_admin_user)
        ):
            # 只有管理员可以创建用户
            ...
    
    错误响应:
        HTTP 403 Forbidden
        {
            "detail": "Not enough permissions"
        }
    
    依赖链:
        get_current_admin_user
        └── get_current_active_user
            └── get_current_user
                ├── oauth2_scheme (提取 token)
                └── get_db (数据库会话)
    """
    # 检查用户角色
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(
            status_code=403, 
            detail="Not enough permissions"
        )
    
    return current_user


# =============================================================================
# 可选认证依赖
# =============================================================================

def get_current_user_optional(
    token: str = Depends(OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)),
    db: Session = Depends(database.get_db)
) -> models.User | None:
    """
    可选的用户认证依赖。
    
    与 get_current_user 类似，但不强制要求认证。
    如果提供了有效令牌则返回用户，否则返回 None。
    
    参数:
        token (str | None): 令牌，可能为 None
            - auto_error=False 使令牌缺失时不报错
        db (Session): 数据库会话
    
    返回:
        models.User | None: 用户对象或 None
    
    使用场景:
        - 公开但可根据登录状态提供不同内容的接口
        - 可选的个性化功能
    
    使用示例:
        @router.get("/public")
        def public_content(user: User | None = Depends(get_current_user_optional)):
            if user:
                return {"message": f"Hello, {user.username}!"}
            return {"message": "Hello, guest!"}
    """
    if token is None:
        return None
    
    try:
        payload = jwt.decode(
            token, 
            security.SECRET_KEY, 
            algorithms=[security.ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            return None
        
        user = db.query(models.User).filter(
            models.User.username == username
        ).first()
        
        return user
    except JWTError:
        return None
