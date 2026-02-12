import subprocess
import os
from typing import Optional
from pydantic import BaseModel, Field
from agent_tools.base import ToolContext, ToolResult, validate_path

class ExecuteCommandArgs(BaseModel):
    command: str = Field(..., description="Shell command to execute. This should be valid for the current operating system. Ensure the command is properly formatted and does not contain any harmful instructions.")
    cwd: Optional[str] = Field(None, description="Optional working directory for the command, relative or absolute")

def execute_command(ctx: ToolContext, args: ExecuteCommandArgs) -> ToolResult:
    """
    Request to execute a CLI command on the system. Use this when you need to perform system operations or run specific commands to accomplish any step in the user's task. You must tailor your command to the user's system and provide a clear explanation of what the command does. For command chaining, use the appropriate chaining syntax for the user's shell. Prefer to execute complex CLI commands over creating executable scripts, as they are more flexible and easier to run. Prefer relative commands and paths that avoid location sensitivity for terminal consistency.
    """
    try:
        # Determine working directory
        if args.cwd:
            cwd_path = validate_path(args.cwd, ctx.workspace_root)
        else:
            cwd_path = ctx.workspace_root

        # Execute command
        # capture_output=True captures stdout and stderr
        # text=True returns string instead of bytes
        # shell=True allows shell features (like pipes), but be careful with security
        
        result = subprocess.run(
            args.command,
            cwd=cwd_path,
            capture_output=True,
            text=True,
            encoding='utf-8',
            shell=True,
            timeout=120 # Set timeout to prevent hanging
        )
        
        output = result.stdout
        if result.stderr:
            output += "\nSTDERR:\n" + result.stderr
            
        if result.returncode != 0:
            return ToolResult(success=False, output=f"命令执行失败 (代码 {result.returncode}) / Command failed (code {result.returncode}):\n{output}")
            
        return ToolResult(success=True, output=output)

    except subprocess.TimeoutExpired:
        return ToolResult(success=False, output="错误：命令执行超时 / Error: Command execution timed out")
    except Exception as e:
        return ToolResult(success=False, output=f"执行命令失败 / Failed to execute command: {str(e)}")
