import os
from pathlib import Path
from typing import Optional, List, Any
from pydantic import BaseModel, Field

class ToolResult(BaseModel):
    """
    工具执行结果的标准返回格式。
    Standard return format for tool execution results.
    """
    success: bool = Field(..., description="工具执行是否成功 / Whether the tool execution was successful")
    output: str = Field(..., description="工具执行的输出信息或错误信息 / Output message or error message")
    data: Optional[Any] = Field(None, description="可选的结构化数据 / Optional structured data")

class ToolContext(BaseModel):
    """
    工具执行上下文，保存当前会话的状态。
    Tool execution context, holding the state of the current session.
    """
    workspace_root: Path = Field(..., description="工作区根目录，所有文件操作必须在此目录下进行 / Workspace root directory")
    todos: List[str] = Field(default_factory=list, description="当前的待办事项列表 / Current list of TODOs")
    mode: str = Field(default="code", description="当前的模式 (例如: code, architect) / Current mode")
    browser_session: Optional[Any] = Field(None, description="活动的浏览器会话对象 (Playwright) / Active browser session object")
    skills_manager: Optional[Any] = Field(None, description="技能管理器实例 / Skills manager instance")
    env: str = Field(default="cli", description="运行环境 (cli / web)")

    class Config:
        arbitrary_types_allowed = True

def validate_path(path: str | Path, workspace_root: Path) -> Path:
    """
    验证路径是否在工作区根目录下，防止路径遍历攻击。
    Validate that the path is within the workspace root to prevent path traversal attacks.

    Args:
        path: 需要验证的路径 (相对或绝对) / The path to validate (relative or absolute)
        workspace_root: 工作区根目录 / The workspace root directory

    Returns:
        Path: 解析后的绝对路径 / The resolved absolute path

    Raises:
        ValueError: 如果路径在工作区之外 / If the path is outside the workspace
    """
    # 将输入转换为 Path 对象
    # Convert input to Path object
    if isinstance(path, str):
        # 展开用户目录 (~)
        # Expand user directory (~)
        path = os.path.expanduser(path)
        path_obj = Path(path)
    else:
        path_obj = path

    # 获取工作区的绝对路径
    # Get absolute path of workspace root
    root_path = workspace_root.resolve()

    # 处理输入路径
    # Handle input path
    if path_obj.is_absolute():
        # 如果是绝对路径，直接解析
        # If absolute, resolve directly
        target_path = path_obj.resolve()
    else:
        # 如果是相对路径，相对于工作区根目录解析
        # If relative, resolve relative to workspace root
        target_path = (root_path / path_obj).resolve()

    # 检查目标路径是否在工作区根目录内
    # Check if target path is within workspace root
    # 使用 is_relative_to (Python 3.9+)
    if not target_path.is_relative_to(root_path):
        raise ValueError(f"安全错误：路径 '{target_path}' 位于工作区 '{root_path}' 之外。 / Security Error: Path is outside workspace.")

    return target_path
