"""
=============================================================================
ownAgent - Web 服务器模块
=============================================================================

本文件是 ownAgent 项目的 Web 服务入口，提供：
1. RESTful API 接口
2. SSE 流式响应
3. 用户认证
4. 会话管理
5. 静态文件服务

技术栈：
- FastAPI: 现代、高性能的 Web 框架
- Uvicorn: ASGI 服务器
- SSE (Server-Sent Events): 实现流式响应

启动方式：
    python server.py
    
访问地址：
    http://localhost:8000

API 端点：
    GET  /              - 主页
    GET  /sessions      - 列出会话
    POST /sessions/new  - 创建新会话
    POST /sessions/{id}/load - 加载会话
    POST /chat          - 发送消息（SSE 流式）
    POST /auth/register - 用户注册
    POST /auth/token    - 获取令牌

作者: ownAgent Team
版本: 1.0.0
=============================================================================
"""

# =============================================================================
# 标准库导入
# =============================================================================

import os           # 操作系统接口，用于环境变量
import json         # JSON 数据处理，用于 SSE 事件数据
import asyncio      # 异步 I/O，用于异步生成器
from pathlib import Path  # 面向对象的文件路径处理
from datetime import datetime  # 日期时间处理，用于生成会话 ID

# =============================================================================
# 第三方库导入
# =============================================================================

from dotenv import load_dotenv  # 从 .env 文件加载环境变量
from typing import AsyncGenerator, Dict, Any, Optional  # 类型提示

# FastAPI 相关导入
from fastapi import FastAPI, Request, Depends  # Web 框架核心
from fastapi.responses import StreamingResponse, FileResponse  # 响应类型
from fastapi.staticfiles import StaticFiles  # 静态文件服务
from fastapi.middleware.cors import CORSMiddleware  # CORS 中间件
from pydantic import BaseModel  # 数据验证

# =============================================================================
# 项目内部模块导入
# =============================================================================

# 从 ag.py 导入 Agent 核心组件
from ag import (
    LLMTransport,      # LLM 传输层
    ToolExecutor,      # 工具执行器
    AgentRuntime,      # Agent 运行时
)

from log.logger import ConversationLogger
from agent_tools.skills_loader import SkillsLoader
from agent_tools.skills_manager import SkillsManager


# 导入所有工具函数和参数模型
# 这些工具会在启动时注册到 ToolExecutor
from ag import (
    # 文件操作工具
    list_files, ListFilesArgs,
    read_file, ReadFileArgs,
    write_to_file, WriteToFileArgs,
    delete_file, DeleteFileArgs,
    search_files, SearchFilesArgs,
    edit_file, EditFileArgs,
    # 系统工具
    execute_command, ExecuteCommandArgs,
    # 浏览器工具
    browser_action, BrowserActionArgs,
    # 差异工具
    apply_diff, ApplyDiffArgs,
    # 交互工具
    ask_followup_question, AskFollowupQuestionArgs,
    attempt_completion, AttemptCompletionArgs,
    new_task, NewTaskArgs,
    switch_mode, SwitchModeArgs,
    fetch_instructions, FetchInstructionsArgs,
    # 技能工具
    list_skills, ListSkillsArgs,
    search_skills, SearchSkillsArgs,
    list_skills, ListSkillsArgs,
    search_skills, SearchSkillsArgs,
    get_skill, GetSkillArgs
)

from agent_tools.todo import (
    read_todo, ReadTodoArgs,
    write_todo, WriteTodoArgs,
    update_todo, UpdateTodoArgs
)

# 导入认证模块
# 导入认证模块
from auth import router as auth_router, dependencies as auth_deps, models as auth_models

# 导入 MCP 模块
from agent_tools.mcp.client import McpClient
from agent_tools.mcp.transport import StdioTransport, SseTransport


# =============================================================================
# FastAPI 应用初始化
# =============================================================================

# 创建 FastAPI 应用实例
# FastAPI 是一个现代、高性能的 Python Web 框架
app = FastAPI(
    title="ownAgent API",
    description="AI 编程助手 API",
    version="1.0.0"
)


# =============================================================================
# 启动事件处理
# =============================================================================

@app.on_event("startup")
def on_startup():
    """
    应用启动时执行的初始化函数。
    
    这里初始化认证数据库，确保用户表存在。
    """
    auth_router.init_db()


# =============================================================================
# CORS 中间件配置
# =============================================================================

# 添加 CORS (跨域资源共享) 中间件
# 允许前端从不同的域名访问 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # 允许所有来源（开发环境）
    allow_credentials=True,     # 允许携带凭证（Cookie）
    allow_methods=["*"],        # 允许所有 HTTP 方法
    allow_headers=["*"],        # 允许所有请求头
)
# 注意：生产环境应该限制 allow_origins 为具体的前端域名


# =============================================================================
# 路由注册
# =============================================================================

# 包含认证路由
# 所有 /auth/* 的请求会被路由到认证模块
app.include_router(auth_router.router)


# =============================================================================
# 静态文件服务
# =============================================================================

# 设置静态文件目录
static_dir = Path("static")
# 确保目录存在
static_dir.mkdir(exist_ok=True)
# 挂载静态文件目录到 /static 路径
# 这样 /static/app.js 会映射到 static/app.js 文件
app.mount("/static", StaticFiles(directory="static"), name="static")


# =============================================================================
# 会话存储配置
# =============================================================================

# 会话文件存储目录
SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)  # 确保目录存在


# =============================================================================
# 全局状态存储
# =============================================================================

# 注意：以下使用内存存储，重启后会丢失
# 生产环境应该使用 Redis 或数据库

# 会话列表（暂未使用）
sessions = []

# 运行时存储：映射 "用户ID:会话ID" -> AgentRuntime
# 每个用户的每个会话都有独立的运行时实例
session_runtimes: Dict[str, Any] = {}

# 活跃会话：映射 用户ID -> 当前活跃的会话ID
# 用于跟踪用户当前正在使用的会话
active_sessions: Dict[int, str] = {}


# =============================================================================
# 环境变量加载
# =============================================================================

# 从 .env 文件加载环境变量
load_dotenv()

# API 配置
# 这些配置用于初始化 LLM 传输层
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")      # API 密钥
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")    # API 基础 URL
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "glm4.7")  # 模型名称，默认 glm4.7


# =============================================================================
# 辅助函数
# =============================================================================

def get_session_path(user_id: int, session_id: str) -> Path:
    """
    获取会话文件的路径。
    
    参数:
        user_id (int): 用户 ID
        session_id (str): 会话 ID
    
    返回:
        Path: 会话文件路径，格式为 sessions/{user_id}_session_{session_id}.json
    
    示例:
        >>> path = get_session_path(1, "20240101_120000")
        >>> print(path)
        sessions/1_session_20240101_120000.json
    """
    return SESSIONS_DIR / f"{user_id}_session_{session_id}.json"


async def init_mcp_servers(runtime: AgentRuntime):
    """
    初始化 MCP 服务器并注册工具。
    """
    config_path = Path("mcp_config.json")
    if not config_path.exists():
        return

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            
        servers = config.get("mcpServers", {})
        for name, server_config in servers.items():
            try:
                print(f"[Info] Initializing MCP server: {name}")
                transport = None
                
                # Command-based (Stdio)
                if "command" in server_config:
                    cmd = server_config["command"]
                    args = server_config.get("args", [])
                    env = server_config.get("env")
                    transport = StdioTransport(cmd, args, env)
                
                # URL-based (SSE)
                elif "url" in server_config:
                    url = server_config["url"]
                    transport = SseTransport(url)
                
                if transport:
                    client = McpClient(transport)
                    await client.connect()
                    
                    # Store client in runtime to keep it alive
                    if not hasattr(runtime, "mcp_clients"):
                        runtime.mcp_clients = []
                    runtime.mcp_clients.append(client)
                    
                    tools = await client.list_tools()
                    for tool in tools:
                        runtime.executor.register_mcp_tool(tool, client)
                        
            except Exception as e:
                print(f"[Error] Failed to initialize MCP server {name}: {e}")
                
    except Exception as e:
        print(f"[Error] Failed to load MCP config: {e}")


async def get_or_create_runtime(user_id: int, session_id: str) -> AgentRuntime:
    """
    获取或创建用户的会话运行时。
    
    这个函数实现了运行时的懒加载和缓存：
    - 如果运行时已存在，直接返回
    - 如果不存在，创建新的运行时并缓存
    
    参数:
        user_id (int): 用户 ID
        session_id (str): 会话 ID
    
    返回:
        AgentRuntime: Agent 运行时实例
    
    创建流程：
        1. 创建 LLM 传输层
        2. 初始化技能系统
        3. 创建工具执行器并注册所有工具
        4. 创建 Agent 运行时
        5. 如果存在历史记录，加载历史
        6. 初始化 MCP 服务器
    """
    # 构建运行时的唯一标识
    runtime_key = f"{user_id}:{session_id}"
    
    # 检查是否已有缓存的运行时
    if runtime_key in session_runtimes:
        return session_runtimes[runtime_key]
    
    # --- 创建新的运行时 ---
    
    # 步骤 1: 创建 LLM 传输层
    transport = LLMTransport(
        api_key=OPENAI_API_KEY, 
        base_url=OPENAI_BASE_URL, 
        model=OPENAI_MODEL
    )
    
    # 步骤 2: 初始化技能系统
    skills_root = Path(".skills")
    # skills_loader = SkillsLoader(skills_root)
    skills_manager = SkillsManager(skills_root)
    skills_manager.load_skills()  # 加载所有技能

    # 步骤 3: 创建工具执行器
    executor = ToolExecutor()
    
    # 注册所有工具
    # --- 文件操作工具 ---
    executor.register(list_files, ListFilesArgs)
    executor.register(read_file, ReadFileArgs)
    executor.register(write_to_file, WriteToFileArgs)
    executor.register(delete_file, DeleteFileArgs)
    executor.register(search_files, SearchFilesArgs)
    executor.register(edit_file, EditFileArgs)
    
    # --- 系统工具 ---
    executor.register(execute_command, ExecuteCommandArgs)
    
    # --- 浏览器工具 ---
    executor.register(browser_action, BrowserActionArgs)
    
    # --- 差异工具 ---
    executor.register(apply_diff, ApplyDiffArgs)
    
    # --- 交互工具 ---
    executor.register(ask_followup_question, AskFollowupQuestionArgs)
    executor.register(attempt_completion, AttemptCompletionArgs)
    executor.register(new_task, NewTaskArgs)
    executor.register(switch_mode, SwitchModeArgs)
    executor.register(fetch_instructions, FetchInstructionsArgs)
    
    
    # --- 技能工具 ---
    executor.register(list_skills, ListSkillsArgs)
    executor.register(search_skills, SearchSkillsArgs)
    executor.register(get_skill, GetSkillArgs)

    # --- Todo 工具 ---
    executor.register(read_todo, ReadTodoArgs)
    executor.register(write_todo, WriteTodoArgs)
    executor.register(update_todo, UpdateTodoArgs)

    # 步骤 4: 创建日志记录器
    logger = ConversationLogger()
    
    # 确定自动保存路径
    session_path = get_session_path(user_id, session_id)
    
    # 步骤 5: 创建 Agent 运行时
    runtime = AgentRuntime(
        transport, 
        executor, 
        skills_manager=skills_manager, 
        logger=logger, 
        env="web",  # 标记为 Web 环境
        autosave_file=str(session_path)  # 启用自动保存
    )
    
    # 步骤 6: 如果存在历史文件，加载历史
    if session_path.exists():
        try:
            runtime.context.load_history(str(session_path))
        except Exception:
            pass  # 忽略加载错误

    # 步骤 7: 初始化 MCP 服务器
    await init_mcp_servers(runtime)

    # 缓存运行时
    session_runtimes[runtime_key] = runtime
    return runtime


async def save_user_session(user_id: int):
    """
    手动保存用户会话（已弃用）。
    
    由于启用了自动保存，此函数保留用于手动触发。
    
    参数:
        user_id (int): 用户 ID
    """
    if user_id not in active_sessions:
        return
    sid = active_sessions[user_id]
    path = get_session_path(user_id, sid)
    runtime = await get_or_create_runtime(user_id, sid)
    runtime.context.save_history(str(path))


# =============================================================================
# 请求模型定义
# =============================================================================

class ChatRequest(BaseModel):
    """
    聊天请求模型。
    
    属性:
        message (str): 用户消息内容
        session_id (Optional[str]): 可选的会话 ID，不提供则使用活跃会话
    """
    message: str
    session_id: Optional[str] = None


# =============================================================================
# API 路由定义
# =============================================================================

@app.get("/")
async def get_index():
    """
    主页路由 - 返回静态 HTML 文件。
    
    返回:
        FileResponse: static/index.html 文件
    """
    return FileResponse("static/index.html")


# -----------------------------------------------------------------------------
# 会话管理接口
# -----------------------------------------------------------------------------

@app.get("/sessions")
async def list_sessions(current_user: auth_models.User = Depends(auth_deps.get_current_active_user)):
    """
    列出当前用户的所有会话。
    
    需要认证：是
    
    参数:
        current_user: 当前登录用户（通过依赖注入获取）
    
    返回:
        dict: {
            "sessions": [
                {"id": "会话ID", "timestamp": 时间戳, "filename": "文件名"},
                ...
            ],
            "current_session_id": "当前活跃会话ID"
        }
    
    实现逻辑：
        1. 扫描 sessions 目录
        2. 过滤出当前用户的会话文件
        3. 按修改时间排序（最新的在前）
    """
    sessions = []
    if not SESSIONS_DIR.exists():
        return {"sessions": []}
    
    # 构建用户会话文件的前缀
    prefix = f"{current_user.id}_session_"
    
    # 遍历匹配的文件
    for f in SESSIONS_DIR.glob(f"{prefix}*.json"):
        # 从文件名提取会话 ID
        sid = f.stem.replace(prefix, "")
        stat = f.stat()
        sessions.append({
            "id": sid,
            "timestamp": stat.st_mtime,  # 修改时间戳
            "filename": f.name
        })
    
    # 按时间倒序排序
    sessions.sort(key=lambda x: x["timestamp"], reverse=True)
    
    # 获取当前活跃会话
    cur_sid = active_sessions.get(current_user.id, None)
    return {"sessions": sessions, "current_session_id": cur_sid}


@app.post("/sessions/new")
async def new_session(current_user: auth_models.User = Depends(auth_deps.get_current_active_user)):
    """
    创建新会话。
    
    需要认证：是
    
    参数:
        current_user: 当前登录用户
    
    返回:
        dict: {"id": "新会话ID", "message": "提示信息"}
    
    实现逻辑：
        1. 生成时间戳格式的会话 ID
        2. 初始化运行时
        3. 重置上下文
        4. 保存初始状态
        5. 设为活跃会话
    """
    # 生成会话 ID：格式为 YYYYMMDD_HHMMSS
    new_sid = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 初始化运行时
    runtime = await get_or_create_runtime(current_user.id, new_sid)
    runtime.context.reset()  # 重置为初始状态
    
    # 保存初始会话文件
    runtime.context.save_history(str(get_session_path(current_user.id, new_sid)))
    
    # 设为活跃会话
    active_sessions[current_user.id] = new_sid
    
    return {"id": new_sid, "message": "New session started"}


@app.post("/sessions/{session_id}/load")
async def load_session(session_id: str, current_user: auth_models.User = Depends(auth_deps.get_current_active_user)):
    """
    加载指定会话。
    
    需要认证：是
    
    参数:
        session_id (str): 要加载的会话 ID
        current_user: 当前登录用户
    
    返回:
        dict: {
            "id": "会话ID",
            "history": [对话历史消息列表]
        }
    
    安全检查：
        - 只能加载自己的会话（通过文件名前缀验证）
    """
    # 获取会话文件路径
    path = get_session_path(current_user.id, session_id)
    
    # 检查文件是否存在
    if not path.exists():
        return {"error": "Session not found or permission denied"}
    
    # 获取或创建运行时（会自动加载历史）
    runtime = await get_or_create_runtime(current_user.id, session_id)
    
    # 设为活跃会话
    active_sessions[current_user.id] = session_id
    
    # 返回历史消息（跳过系统提示词）
    msgs = runtime.context.history[1:] if len(runtime.context.history) > 0 else []
    return {"id": session_id, "history": msgs}


# -----------------------------------------------------------------------------
# 聊天接口
# -----------------------------------------------------------------------------

@app.post("/chat")
async def chat_endpoint(request: ChatRequest, current_user: auth_models.User = Depends(auth_deps.get_current_active_user)):
    """
    聊天接口 - 使用 SSE 流式响应。
    
    需要认证：是
    
    参数:
        request (ChatRequest): 聊天请求，包含消息和可选的会话 ID
        current_user: 当前登录用户
    
    返回:
        StreamingResponse: SSE 流式响应
    
    SSE 事件格式：
        data: {"type": "thinking_delta", "content": "思考内容"}
        data: {"type": "content_delta", "content": "文本内容"}
        data: {"type": "tool_call", "content": {...}}
        data: {"type": "tool_output", "content": {...}}
        data: {"type": "finished", "content": "完成"}
        data: {"type": "error", "content": "错误信息"}
    
    实现流程：
        1. 确定会话 ID
        2. 获取或创建运行时
        3. 创建异步生成器
        4. 返回 SSE 响应
    """
    # 确定会话 ID
    session_id = request.session_id
    
    if not session_id:
        # 如果没有指定会话 ID，使用活跃会话
        session_id = active_sessions.get(current_user.id)
    
    if not session_id:
        # 如果没有活跃会话，自动创建
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        active_sessions[current_user.id] = session_id
    
    # 获取运行时
    runtime = await get_or_create_runtime(current_user.id, session_id)

    # 定义 SSE 事件生成器
    async def event_generator():
        """
        SSE 事件生成器。
        
        将 Runtime 的事件转换为 SSE 格式。
        """
        try:
            # 遍历 Runtime 产生的事件
            async for event in runtime.step(request.message):
                # 将事件序列化为 JSON
                data = json.dumps(event, ensure_ascii=False)
                # SSE 格式：data: {json}\n\n
                yield f"data: {data}\n\n"
                # 短暂休眠，让出控制权
                await asyncio.sleep(0.01)
            
            # 对话完成后自动保存
            await save_user_session(current_user.id)
            
        except Exception as e:
            # 发生错误时返回错误事件
            error_event = {"type": "error", "content": str(e)}
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

    # 返回 SSE 流式响应
    # media_type="text/event-stream" 是 SSE 的标准 MIME 类型
    return StreamingResponse(event_generator(), media_type="text/event-stream")


# =============================================================================
# 主程序入口
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    # 打印启动信息
    print("Starting Web Server on http://localhost:8000")
    
    # 启动 Uvicorn ASGI 服务器
    # host="127.0.0.1" 只监听本地连接
    # port=8000 监听 8000 端口
    uvicorn.run(app, host="127.0.0.1", port=8000)
