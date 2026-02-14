"""
=============================================================================
ownAgent - 认证路由模块
=============================================================================

本文件实现了用户认证相关的 API 路由：

1. POST /auth/token - 用户登录获取令牌
2. GET /auth/users/me - 获取当前用户信息
3. POST /auth/users - 创建新用户（管理员）
4. init_db() - 初始化数据库和默认管理员

API 设计说明：
- 使用 OAuth2 密码模式（Password Flow）
- 返回 JWT 令牌用于后续认证
- 支持角色权限控制

认证流程：
1. 客户端 POST /auth/token 获取令牌
2. 服务端验证用户名密码
3. 返回 JWT 令牌
4. 客户端在后续请求中携带令牌
5. 服务端验证令牌并识别用户

作者: ownAgent Team
版本: 1.0.0
=============================================================================
"""

# =============================================================================
# 标准库导入
# =============================================================================

from datetime import timedelta  # 时间间隔计算

# =============================================================================
# 第三方库导入
# =============================================================================

from fastapi import APIRouter, Depends, HTTPException, status  # FastAPI 核心组件
from fastapi.security import OAuth2PasswordRequestForm  # OAuth2 表单数据
from sqlalchemy.orm import Session  # SQLAlchemy 会话类型

# =============================================================================
# 项目内部模块导入
# =============================================================================

from . import database, schemas, models, security, dependencies


# =============================================================================
# 路由器配置
# =============================================================================

# 创建 API 路由器
# prefix: 路由前缀，所有路由都会加上 /auth
# tags: OpenAPI 文档中的标签，用于分组
router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)


# =============================================================================
# API 路由定义
# =============================================================================

@router.post("/token", response_model=schemas.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db)
):
    """
    用户登录获取访问令牌。
    
    这是 OAuth2 密码模式的令牌端点。
    客户端提交 username 和 password（表单数据），
    验证通过后返回 JWT 令牌。
    
    请求格式:
        POST /auth/token
        Content-Type: application/x-www-form-urlencoded
        
        username=admin&password=admin123
    
    参数:
        form_data (OAuth2PasswordRequestForm): 表单数据
            - username: 用户名
            - password: 密码
            - 由 FastAPI 自动从表单解析
        
        db (Session): 数据库会话
            - 由 get_db 依赖注入
    
    返回:
        schemas.Token: 令牌响应
            - access_token: JWT 令牌
            - token_type: "bearer"
    
    异常:
        HTTPException 401: 用户名或密码错误
    
    使用示例:
        # 使用 curl
        curl -X POST "http://localhost:8000/auth/token" \
             -H "Content-Type: application/x-www-form-urlencoded" \
             -d "username=admin&password=admin123"
        
        # 使用 requests
        import requests
        response = requests.post(
            "http://localhost:8000/auth/token",
            data={"username": "admin", "password": "admin123"}
        )
        token = response.json()["access_token"]
    
    错误响应:
        HTTP 401 Unauthorized
        {
            "detail": "Incorrect username or password"
        }
    """
    # 从数据库查询用户
    user = db.query(models.User).filter(
        models.User.username == form_data.username
    ).first()
    
    # 验证用户存在且密码正确
    if not user or not security.verify_password(
        form_data.password, 
        user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 计算令牌过期时间
    access_token_expires = timedelta(
        minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    
    # 创建访问令牌
    # sub (subject): 用户名，用于标识用户
    # role: 用户角色，用于权限控制
    access_token = security.create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=access_token_expires
    )
    
    # 返回令牌
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me", response_model=schemas.User)
async def read_users_me(
    current_user: models.User = Depends(dependencies.get_current_active_user)
):
    """
    获取当前登录用户的信息。
    
    需要在请求头中携带有效的 JWT 令牌。
    返回当前用户的详细信息（不包含密码）。
    
    请求格式:
        GET /auth/users/me
        Authorization: Bearer <token>
    
    参数:
        current_user (models.User): 当前用户
            - 由 get_current_active_user 依赖注入
            - 自动从令牌解析并验证
    
    返回:
        schemas.User: 用户信息
            - id: 用户 ID
            - username: 用户名
            - is_active: 是否激活
            - role: 用户角色
    
    使用示例:
        # 使用 curl
        curl -X GET "http://localhost:8000/auth/users/me" \
             -H "Authorization: Bearer <token>"
        
        # 使用 requests
        import requests
        response = requests.get(
            "http://localhost:8000/auth/users/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        user = response.json()
    
    响应示例:
        {
            "id": 1,
            "username": "admin",
            "is_active": true,
            "role": "admin"
        }
    """
    return current_user


@router.post("/users", response_model=schemas.User)
async def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_current_admin_user)
):
    """
    创建新用户（仅管理员可用）。
    
    管理员可以创建新用户并指定角色。
    用户名不能重复。
    
    请求格式:
        POST /auth/users
        Authorization: Bearer <admin_token>
        Content-Type: application/json
        
        {
            "username": "newuser",
            "password": "password123",
            "role": "user"
        }
    
    参数:
        user (schemas.UserCreate): 用户创建数据
            - username: 用户名（���一）
            - password: 密码
            - role: 角色（可选，默认 user）
        
        db (Session): 数据库会话
        
        current_user (models.User): 当前管理员用户
            - 由 get_current_admin_user 依赖注入
            - 确保只有管理员可以创建用户
    
    返回:
        schemas.User: 创建的用户信息
    
    异常:
        HTTPException 400: 用户名已存在
        HTTPException 403: 非管理员无权限
    
    使用示例:
        # 使用 curl（管理员）
        curl -X POST "http://localhost:8000/auth/users" \
             -H "Authorization: Bearer <admin_token>" \
             -H "Content-Type: application/json" \
             -d '{"username": "newuser", "password": "pass123", "role": "user"}'
    
    响应示例:
        {
            "id": 2,
            "username": "newuser",
            "is_active": true,
            "role": "user"
        }
    """
    # 检查用户名是否已存在
    db_user = db.query(models.User).filter(
        models.User.username == user.username
    ).first()
    
    if db_user:
        raise HTTPException(
            status_code=400, 
            detail="Username already registered"
        )
    
    # 哈希密码
    hashed_password = security.get_password_hash(user.password)
    
    # 创建用户对象
    db_user = models.User(
        username=user.username,
        hashed_password=hashed_password,
        role=user.role
    )
    
    # 保存到数据库
    db.add(db_user)      # 添加到会话
    db.commit()          # 提交事务
    db.refresh(db_user)  # 刷新以获取自动生成的字段（如 id）
    
    return db_user


# =============================================================================
# 数据库初始化函数
# =============================================================================

def init_db():
    """
    初始化数据库。
    
    创建表结构，并检查是否存在默认 admin 用户。
    如果不存在则自动创建。
    
    默认管理员账户:
        - 用户名: admin
        - 密码: admin123
        - 角色: ADMIN
    
    使用场景:
        - 应用启动时调用
        - 首次部署时初始化数据库
    
    使用示例:
        # 在 main.py 中
        from auth.router import init_db
        
        @app.on_event("startup")
        def startup_event():
            init_db()
    
    安全建议:
        - 生产环境应修改默认密码
        - 或删除默认管理员，手动创建
    """
    # 创建数据库会话
    db = database.SessionLocal()
    
    try:
        # 创建所有表
        # 如果表已存在则不会重复创建
        models.Base.metadata.create_all(bind=database.engine)
        
        # 检查是否存在 admin 用户
        admin = db.query(models.User).filter(
            models.User.username == "admin"
        ).first()
        
        if not admin:
            # 不存在则创建默认管理员
            print("Creating default admin user: admin / admin123")
            
            # 哈希默认密码
            hashed_pwd = security.get_password_hash("admin123")
            
            # 创建管理员用户
            admin_user = models.User(
                username="admin",
                hashed_password=hashed_pwd,
                role=models.UserRole.ADMIN
            )
            
            # 保存到数据库
            db.add(admin_user)
            db.commit()
            
    finally:
        # 确保会话被关闭
        db.close()


# =============================================================================
# 其他用户管理路由（可选扩展）
# =============================================================================

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_current_admin_user)
):
    """
    删除用户（仅管理员可用）。
    
    参数:
        user_id (int): 要删除的用户 ID
    
    异常:
        HTTPException 404: 用户不存在
        HTTPException 400: 不能删除自己
    """
    # 查询用户
    user = db.query(models.User).filter(models.User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 不能删除自己
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    # 删除用户
    db.delete(user)
    db.commit()
    
    return {"message": "User deleted successfully"}


@router.put("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_current_admin_user)
):
    """
    禁用用户（仅管理员可用）。
    
    将用户设为非活跃状态，但不删除。
    
    参数:
        user_id (int): 要禁用的用户 ID
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = False
    db.commit()
    
    return {"message": "User deactivated successfully"}
