"""
=============================================================================
ownAgent - 安全认证模块
=============================================================================

本文件实现了用户认证的核心安全功能：

1. 密码哈希和验证
2. JWT 令牌生成和解析

安全设计说明：
- 使用 bcrypt 算法哈希密码（行业标准）
- 使用 JWT (JSON Web Token) 进行身份认证
- 令牌有过期时间，防止长期有效

JWT 认证流程：
1. 用户登录 -> 验证用户名密码
2. 生成 JWT 令牌 -> 返回给客户端
3. 客户端存储令牌 -> 后续请求携带令牌
4. 服务端验证令牌 -> 解析用户身份

依赖库：
- python-jose[cryptography]: JWT 处理
- passlib[bcrypt]: 密码哈希

作者: ownAgent Team
版本: 1.0.0
=============================================================================
"""

# =============================================================================
# 标准库导入
# =============================================================================

from datetime import datetime, timedelta  # 日期时间处理
from typing import Optional  # 可选类型提示

# =============================================================================
# 第三方库导入
# =============================================================================

from jose import JWTError, jwt  # JWT 处理库
from passlib.context import CryptContext  # 密码哈希库


# =============================================================================
# 安全配置常量
# =============================================================================

# 密钥：用于签名和验证 JWT
# 【重要】生产环境必须从环境变量加载，不要硬编码！
# 硬编码的密钥会带来安全风险
SECRET_KEY = "CHANGE_THIS_IN_PRODUCTION_SECRET_KEY"

# 算法：JWT 签名算法
# HS256 是对称加密算法（HMAC SHA-256）
# 特点：同一密钥签名和验证，速度快
ALGORITHM = "HS256"

# 令牌过期时间（分钟）
# 4320 分钟 = 72 小时 = 3 天
# 根据安全需求调整，越短越安全
ACCESS_TOKEN_EXPIRE_MINUTES = 4320


# =============================================================================
# 密码哈希上下文
# =============================================================================

# 创建密码哈希上下文
# schemes=["bcrypt"]: 使用 bcrypt 算法
# deprecated="auto": 自动处理过时的哈希算法
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# =============================================================================
# 密码处理函数
# =============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码是否与哈希密码匹配。
    
    用于用户登录时验证密码。
    
    参数:
        plain_password (str): 用户输入的明文密码
        hashed_password (str): 数据库中存储的哈希密码
    
    返回:
        bool: 匹配返回 True，不匹配返回 False
    
    工作原理:
        1. bcrypt 算法从哈希值中提取盐值
        2. 使用相同盐值对明文密码进行哈希
        3. 比较两个哈希值是否相同
    
    示例:
        >>> hashed = get_password_hash("mypassword")
        >>> verify_password("mypassword", hashed)
        True
        >>> verify_password("wrongpassword", hashed)
        False
    
    安全说明:
        - bcrypt 是专门为密码存储设计的算法
        - 自动加盐，防止彩虹表攻击
        - 计算成本可调，抵抗暴力破解
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    生成密码的哈希值。
    
    用于创建用户或修改密码时，将明文密码转换为安全的哈希值。
    
    参数:
        password (str): 明文密码
    
    返回:
        str: 哈希后的密码字符串
    
    哈希值格式:
        $2b$12$... (bcrypt 格式)
        ├── $2b$: bcrypt 版本标识
        ├── $12$: 成本因子（迭代次数 2^12）
        └── 后续: 盐值和哈希值
    
    示例:
        >>> hash1 = get_password_hash("mypassword")
        >>> hash2 = get_password_hash("mypassword")
        >>> # 每次生成的哈希值不同（因为盐值不同）
        >>> hash1 != hash2
        True
        >>> # 但都可以验证成功
        >>> verify_password("mypassword", hash1)
        True
        >>> verify_password("mypassword", hash2)
        True
    
    安全说明:
        - 永远不要存储明文密码
        - 每次哈希都会生成新的盐值
        - 相同密码的哈希值每次都不同
    """
    return pwd_context.hash(password)


# =============================================================================
# JWT 令牌处理函数
# =============================================================================

def create_access_token(
    data: dict, 
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    创建 JWT 访问令牌。
    
    将用户信息编码为 JWT 令牌，用于后续请求认证。
    
    参数:
        data (dict): 要编码进令牌的数据
            - 通常包含 "sub" (subject, 用户名)
            - 可以包含 "role" 等自定义字段
            - 示例: {"sub": "admin", "role": "admin"}
        
        expires_delta (Optional[timedelta]): 过期时间间隔
            - 如果提供，使用指定的过期时间
            - 如果不提供，默认 15 分钟
    
    返回:
        str: JWT 令牌字符串
    
    JWT 结构:
        Header.Payload.Signature
        
        Header (Base64 编码):
        {
            "alg": "HS256",
            "typ": "JWT"
        }
        
        Payload (Base64 编码):
        {
            "sub": "username",    # 主题（用户名）
            "role": "user",       # 自定义字段
            "exp": 1234567890     # 过期时间戳
        }
        
        Signature:
        HMACSHA256(
            base64UrlEncode(header) + "." + base64UrlEncode(payload),
            secret
        )
    
    示例:
        >>> # 创建 3 天有效期的令牌
        >>> token = create_access_token(
        ...     data={"sub": "admin", "role": "admin"},
        ...     expires_delta=timedelta(days=3)
        ... )
        >>> # 返回类似: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    
    使用流程:
        1. 用户登录成功
        2. 调用此函数生成令牌
        3. 返回给客户端保存
        4. 客户端在请求头携带: Authorization: Bearer <token>
    
    安全说明:
        - JWT 可以被解码（不要放敏感信息）
        - 但无法被篡改（没有密钥无法签名）
        - 过期时间应该合理设置
    """
    # 复制数据，避免修改原始字典
    to_encode = data.copy()
    
    # 计算过期时间
    if expires_delta:
        # 使用指定的过期时间
        expire = datetime.utcnow() + expires_delta
    else:
        # 默认 15 分钟过期
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    # 添加过期时间到 payload
    # "exp" 是 JWT 标准字段，表示过期时间
    to_encode.update({"exp": expire})
    
    # 使用密钥和算法编码生成 JWT
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    解码 JWT 访问令牌。
    
    验证令牌签名并提取其中的数据。
    
    参数:
        token (str): JWT 令牌字符串
    
    返回:
        Optional[dict]: 解码后的数据，失败返回 None
    
    示例:
        >>> payload = decode_access_token(token)
        >>> if payload:
        ...     username = payload.get("sub")
        ...     role = payload.get("role")
    
    失败原因:
        - 令牌格式错误
        - 签名验证失败
        - 令牌已过期
        - 密钥不匹配
    """
    try:
        # 解码并验证令牌
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
