from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext

# SECRET_KEY 应该在生产环境中从环境变量加载，不要硬编码
SECRET_KEY = "CHANGE_THIS_IN_PRODUCTION_SECRET_KEY" 
ALGORITHM = "HS256"
# Token 过期时间设置 (例如 3 天)
ACCESS_TOKEN_EXPIRE_MINUTES = 4320 

# 密码哈希上下文，使用 bcrypt 算法
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    """验证明文密码是否与哈希密码匹配"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """生成密码哈希值"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    创建 JWT 访问令牌
    :param data: 要编码进 Payload 的数据 (如 sub, role)
    :param expires_delta: 过期时间差，如果不传则默认 15 分钟
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    # 添加过期时间 claim
    to_encode.update({"exp": expire})
    
    # 编码生成 JWT
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
