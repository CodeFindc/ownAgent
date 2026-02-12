from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from . import database, schemas, models, security, dependencies

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

@router.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    """
    获取访问令牌 (Access Token)。
    客户端提交 username 和 password (form-data)，验证通过后返回 JWT。
    """
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 创建 Access Token
    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.username, "role": user.role}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/users/me", response_model=schemas.User)
async def read_users_me(current_user: models.User = Depends(dependencies.get_current_active_user)):
    """
    获取当前登录用户的信息。
    需要携带有效 JWT。
    """
    return current_user

@router.post("/users", response_model=schemas.User)
async def create_user(
    user: schemas.UserCreate, 
    db: Session = Depends(database.get_db), 
    current_user: models.User = Depends(dependencies.get_current_admin_user)
):
    """
    创建新用户 (仅管理员可用)。
    可以指定用户名、密码和角色。
    """
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = security.get_password_hash(user.password)
    db_user = models.User(
        username=user.username, 
        hashed_password=hashed_password,
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# Initialize default admin on startup if not exists
def init_db():
    """
    初始化数据库。
    创建表结构，并检查是否存在默认 admin 用户，如果不存在则自动创建。
    """
    db = database.SessionLocal()
    try:
        models.Base.metadata.create_all(bind=database.engine)
        
        # Check if admin exists
        admin = db.query(models.User).filter(models.User.username == "admin").first()
        if not admin:
            print("Creating default admin user: admin / admin123")
            hashed_pwd = security.get_password_hash("admin123")
            admin_user = models.User(
                username="admin",
                hashed_password=hashed_pwd,
                role=models.UserRole.ADMIN
            )
            db.add(admin_user)
            db.commit()
    finally:
        db.close()
