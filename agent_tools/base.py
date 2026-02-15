"""
=============================================================================
ownAgent - 工具基础模块
=============================================================================

本文件定义了工具系统的核心基础类和函数：

1. ToolResult - 工具执行结果的标准返回格式
2. ToolContext - 工具执行上下文，保存会话状态
3. validate_path - 路径验证函数，防止路径遍历攻击

这些是所有工具的基础构建块。

作者: ownAgent Team
版本: 1.0.0
=============================================================================
"""

# =============================================================================
# 标准库导入
# =============================================================================

import os               # 操作系统接口，用于路径展开
from pathlib import Path  # 面向对象的��件路径处理
from typing import Optional, List, Any  # 类型提示

# =============================================================================
# 第三方库导入
# =============================================================================

from pydantic import BaseModel, Field  # 数据验证和设置管理


# =============================================================================
# 核心类定义
# =============================================================================

class ToolResult(BaseModel):
    """
    工具执行结果的标准返回格式。
    
    所有工具函数都应该返回这个类的实例，或者返回字符串（会被自动包装）。
    使用标准格式可以让 Runtime 统一处理结果，并支持额外的元数据。
    
    属性:
        success (bool): 工具执行是否成功
            - True: 执行成功
            - False: 执行失败（如文件不存在、权限错误等）
        
        output (str): 工具执行的输出信息或错误信息
            - 成功时：通常是操作结果或获取的数据
            - 失败时：错误描述信息
        
        data (Optional[Any]): 可选的结构化数据
            - 用于传递复杂的数据结构
            - 例如：ask_followup_question 工具用它传递选项列表
    
    示例:
        >>> # 成功结果
        >>> result = ToolResult(
        ...     success=True,
        ...     output="文件已成功创建",
        ...     data={"path": "/path/to/file"}
        ... )
        
        >>> # 失败结果
        >>> result = ToolResult(
        ...     success=False,
        ...     output="错误：文件不存在"
        ... )
        
        >>> # 在工具函数中使用
        >>> def my_tool(ctx: ToolContext, args: MyArgs) -> ToolResult:
        ...     try:
        ...         # 执行操作
        ...         return ToolResult(success=True, output="操作成功")
        ...     except Exception as e:
        ...         return ToolResult(success=False, output=f"错误：{e}")
    """
    
    success: bool = Field(
        ...,  # ... 表示必填字段
        description="工具执行是否成功 / Whether the tool execution was successful"
    )
    
    output: str = Field(
        ...,
        description="工具执行的输出信息或错误信息 / Output message or error message"
    )
    
    data: Optional[Any] = Field(
        None,  # 默认值为 None
        description="可选的结构化数据 / Optional structured data"
    )


class ToolContext(BaseModel):
    """
    工具执行上下文 - 保存当前会话的状态。
    
    每个工具函数都会接收一个 ToolContext 实例作为第一个参数。
    上下文包含了工具执行所需的所有环境信息。
    
    属性:
        workspace_root (Path): 工作区根目录
            - 所有文件操作必须在此目录下进行
            - 用于安全验证，防止访问工作区外的文件
        
        todos (List[str]): 当前的待办事项列表
            - Markdown 格式的待办事项
            - 例如：["[x] 任务1", "[ ] 任务2", "[-] 任务3"]
        
        mode (str): 当前的模式
            - 可选值：code, architect, ask, debug, orchestrator
            - 某些工具可能根据模式有不同的行为
        
        browser_session (Optional[Any]): 活动的浏览器会话对象
            - Playwright 浏览器实例
            - 用于浏览器自动化工具
        
        skills_manager (Optional[Any]): 技能管理器实例
            - 用于技能相关工具
        
        env (str): 运行环境
            - "cli": 命令行环境
            - "web": Web 环境
    
    示例:
        >>> # 在工具函数中访问上下文
        >>> def my_tool(ctx: ToolContext, args: MyArgs) -> ToolResult:
        ...     # 获取工作区路径
        ...     workspace = ctx.workspace_root
        ...     
        ...     # 检查运行环境
        ...     if ctx.env == "web":
        ...         # Web 环境的特殊处理
        ...         pass
        ...     
        ...     # 使用技能管理器
        ...     if ctx.skills_manager:
        ...         skills = ctx.skills_manager.list_skills()
    """
    
    workspace_root: Path = Field(
        ...,
        description="工作区根目录，所有文件操作必须在此目录下进行 / Workspace root directory"
    )
    
    todo_state: List[Any] = Field(
        default_factory=list,
        description="结构化的待办事项状态 (JSON) / Structured Todo state (JSON)"
    )
    
    mode: str = Field(
        default="code",
        description="当前的模式 (例如: code, architect) / Current mode"
    )
    
    browser_session: Optional[Any] = Field(
        None,
        description="活动的浏览器会话对象 (Playwright) / Active browser session object"
    )
    
    skills_manager: Optional[Any] = Field(
        None,
        description="技能管理器实例 / Skills manager instance"
    )
    
    env: str = Field(
        default="cli",
        description="运行环境 (cli / web)"
    )

    class Config:
        """
        Pydantic 模型配置。
        
        arbitrary_types_allowed = True 允许使用任意类型，
        这对于 browser_session 等非 Pydantic 类型的字段是必需的。
        """
        arbitrary_types_allowed = True


# =============================================================================
# 安全验证函数
# =============================================================================

def validate_path(path: str | Path, workspace_root: Path) -> Path:
    """
    验证路径是否在工作区根目录下，防止路径遍历攻击。
    
    这是一个重要的安全函数。所有涉及文件操作的工具都应该
    使用这个函数验证用户提供的路径。
    
    路径遍历攻击示例：
        - "../../../etc/passwd" 试图访问系统敏感文件
        - "~/.ssh/id_rsa" 试图访问用户私钥
    
    参数:
        path (str | Path): 需要验证的路径
            - 可以是相对路径或绝对路径
            - 可以包含 ~（用户目录）
        
        workspace_root (Path): 工作区根目录
            - 所有有效路径必须在此目录下
    
    返回:
        Path: 解析后的绝对路径
    
    异常:
        ValueError: 如果路径在工作区之外
    
    示例:
        >>> workspace = Path("/home/user/project")
        
        >>> # 有效路径
        >>> validate_path("src/main.py", workspace)
        Path("/home/user/project/src/main.py")
        
        >>> validate_path("./config.json", workspace)
        Path("/home/user/project/config.json")
        
        >>> # 无效路径 - 抛出 ValueError
        >>> validate_path("../../../etc/passwd", workspace)
        ValueError: 安全错误：路径位于工作区之外
    
    实现细节:
        1. 将字符串转换为 Path 对象
        2. 展开用户目录 (~)
        3. 如果是相对路径，相对于工作区解析
        4. 解析为绝对路径（处理 . 和 ..）
        5. 检查是否在工作区内
    """
    # 步骤 1: 将输入转换为 Path 对象
    if isinstance(path, str):
        # 展开用户目录 (~)
        # 例如：~/Documents -> /home/user/Documents
        path = os.path.expanduser(path)
        path_obj = Path(path)
    else:
        path_obj = path

    # 步骤 2: 获取工作区的绝对路径
    # resolve() 会解析所有符号链接和相对路径组件
    root_path = workspace_root.resolve()

    # 步骤 3: 处理输入路径
    if path_obj.is_absolute():
        # 如果是绝对路径，直接解析
        target_path = path_obj.resolve()
    else:
        # 如果是相对路径，相对于工作区根目录解析
        target_path = (root_path / path_obj).resolve()

    # 步骤 4: 检查目标路径是否在工作区根目录内
    # is_relative_to() 是 Python 3.9+ 的方法
    # 它检查 target_path 是否是 root_path 的子路径
    if not target_path.is_relative_to(root_path):
        raise ValueError(
            f"安全错误：路径 '{target_path}' 位于工作区 '{root_path}' 之外。"
            f" / Security Error: Path is outside workspace."
        )

    return target_path
