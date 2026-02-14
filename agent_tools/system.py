"""
=============================================================================
ownAgent - 系统命令工具模块
=============================================================================

本文件实现了系统命令执行工具：

1. execute_command - 执行系统命令

这个工具让 AI 能够：
- 运行构建命令（如 npm run build）
- 执行测试（如 pytest）
- 安装依赖（如 pip install）
- 运行脚本
- 执行 Git 操作

安全考虑：
- 命令在工作区内执行
- 有超时限制防止挂起
- 捕获并返回所有输出

作者: ownAgent Team
版本: 1.0.0
=============================================================================
"""

# =============================================================================
# 标准库导入
# =============================================================================

import subprocess  # 子进程管理，用于执行系统命令
import os          # 操作系统接口
from typing import Optional  # 类型提示

# =============================================================================
# 第三方库导入
# =============================================================================

from pydantic import BaseModel, Field  # 数据验证和设置管理

# =============================================================================
# 项目内部模块导入
# =============================================================================

from agent_tools.base import ToolContext, ToolResult, validate_path


# =============================================================================
# 参数模型定义 (Argument Models)
# =============================================================================

class ExecuteCommandArgs(BaseModel):
    """
    execute_command 工具的参数模型。
    
    属性:
        command (str): 要执行的 Shell 命令
            - 必须是当前操作系统支持的有效命令
            - 确保命令格式正确
            - 不应包含有害指令
        
        cwd (Optional[str]): 工作目录
            - 可选，相对或绝对路径
            - 不指定则使用工作区根目录
    
    示例:
        >>> # 在项目目录运行测试
        >>> args = ExecuteCommandArgs(
        ...     command="pytest tests/",
        ...     cwd="myproject"
        ... )
        
        >>> # 安装 Python 依赖
        >>> args = ExecuteCommandArgs(
        ...     command="pip install -r requirements.txt"
        ... )
        
        >>> # 运行 Node.js 构建
        >>> args = ExecuteCommandArgs(
        ...     command="npm run build"
        ... )
    """
    command: str = Field(
        ...,
        description="Shell command to execute. This should be valid for the current operating system. Ensure the command is properly formatted and does not contain any harmful instructions."
    )
    cwd: Optional[str] = Field(
        None,
        description="Optional working directory for the command, relative or absolute"
    )


# =============================================================================
# 工具实现 (Tool Implementations)
# =============================================================================

def execute_command(ctx: ToolContext, args: ExecuteCommandArgs) -> ToolResult:
    """
    执行系统命令。
    
    这个工具允许 AI 在用户系统上执行命令，是自动化任务的关键能力。
    
    参数:
        ctx (ToolContext): 工具执行上下文
        args (ExecuteCommandArgs): 工具参数
    
    返回:
        ToolResult: 包含命令执行结果
            - 成功时：包含标准输出
            - 失败时：包含错误信息和退出码
    
    功能说明:
        - 捕获标准输出和标准错误
        - 支持指定工作目录
        - 有超时限制（120秒）
        - 返回完整的执行结果
    
    安全措施:
        - 工作目录限制在工作区内
        - 超时防止命令挂起
        - 不直接执行用户输入的命令（由 AI 生成）
    
    使用场景:
        1. 构建项目：npm run build, pip install
        2. 运行测试：pytest, npm test
        3. Git 操作：git status, git commit
        4. 文件操作：mkdir, cp, mv（推荐使用文件工具）
        5. 启动服务：python server.py, npm start
    
    示例输出:
        成功：
        ToolResult(
            success=True,
            output="Successfully built project.\\nOutput: dist/bundle.js"
        )
        
        失败：
        ToolResult(
            success=False,
            output="命令执行失败 (代码 1) / Command failed (code 1):\\nError: ..."
        )
    """
    try:
        # 步骤 1: 确定工作目录
        if args.cwd:
            # 如果指定了工作目录，验证并使用它
            cwd_path = validate_path(args.cwd, ctx.workspace_root)
        else:
            # 否则使用工作区根目录
            cwd_path = ctx.workspace_root

        # 步骤 2: 执行命令
        # subprocess.run 是同步执行命令的主要方法
        result = subprocess.run(
            args.command,           # 要执行的命令
            cwd=cwd_path,           # 工作目录
            capture_output=True,    # 捕获 stdout 和 stderr
            text=True,              # 返回字符串而非字节
            encoding='utf-8',       # 使用 UTF-8 编码
            shell=True,             # 通过 shell 执行（支持管道等特性）
            timeout=120             # 超时时间：120秒
        )
        
        # 步骤 3: 处理输出
        # 合并标准输出和标准错误
        output = result.stdout
        if result.stderr:
            output += "\nSTDERR:\n" + result.stderr
            
        # 步骤 4: 检查退出码
        if result.returncode != 0:
            # 非零退出码表示命令失败
            return ToolResult(
                success=False, 
                output=f"命令执行失败 (代码 {result.returncode}) / Command failed (code {result.returncode}):\n{output}"
            )
            
        # 成功执行
        return ToolResult(success=True, output=output)

    except subprocess.TimeoutExpired:
        # 命令执行超时
        return ToolResult(
            success=False, 
            output="错误：命令执行超时 / Error: Command execution timed out"
        )
    except Exception as e:
        # 其他异常
        return ToolResult(
            success=False, 
            output=f"执行命令失败 / Failed to execute command: {str(e)}"
        )
