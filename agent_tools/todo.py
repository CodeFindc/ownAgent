"""
=============================================================================
ownAgent - Todo 工具模块
=============================================================================

本文件实现了结构化 Todo 列表的管理工具：

1. read_todo - 读取当前 Todo 状态
2. write_todo - 更新 Todo 状态并触发展示

作者: ownAgent Team
版本: 1.0.0
=============================================================================
"""

import json
from typing import List, Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field

from agent_tools.base import ToolContext, ToolResult

# =============================================================================
# 数据模型定义
# =============================================================================

class TodoStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class TodoItem(BaseModel):
    """
    单个 Todo 任务项模型。
    """
    id: str = Field(..., description="任务唯一标识符")
    title: str = Field(..., description="任务标题")
    status: TodoStatus = Field(default=TodoStatus.PENDING, description="任务状态")
    subtasks: List['TodoItem'] = Field(default_factory=list, description="子任务列表")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="额外的元数据")

    class Config:
        use_enum_values = True

# 解决前向引用
TodoItem.update_forward_refs()

class ReadTodoArgs(BaseModel):
    """
    read_todo 工具的参数模型。
    无需参数。
    """
    pass

class WriteTodoArgs(BaseModel):
    """
    write_todo 工具的参数模型。
    """
    todos: List[Dict[str, Any]] = Field(
        ..., 
        description="完整的结构化 Todo 列表 (JSON 格式)。每个项应包含 id, title, status, subtasks 等字段。"
    )

class UpdateTodoArgs(BaseModel):
    """
    update_todo 工具的参数模型。
    """
    id: str = Field(..., description="要更新的任务 ID")
    status: TodoStatus = Field(..., description="新的任务状态")


# =============================================================================
# 工具实现
# =============================================================================

def read_todo(ctx: ToolContext, args: ReadTodoArgs) -> ToolResult:
    """
    读取当前的结构化 Todo 状态。
    
    返回:
        ToolResult: 包含当前 Todo 列表的 JSON 数据
    """
    # 确保 ctx.todo_state 已初始化
    if not hasattr(ctx, "todo_state") or ctx.todo_state is None:
        ctx.todo_state = []
        
    return ToolResult(
        success=True,
        output=json.dumps(ctx.todo_state, ensure_ascii=False, indent=2),
        data={"todos": ctx.todo_state}
    )

def write_todo(ctx: ToolContext, args: WriteTodoArgs) -> ToolResult:
    """
    更新结构化 Todo 状态并触发展示。
    
    此工具会完全替换当前的 Todo 列表，并返回更新后的状态。
    前端或 CLI 接收到此工具的输出后，应重新渲染任务列表。
    
    参数:
        ctx (ToolContext): 工具执行上下文
        args (WriteTodoArgs): 包含新 Todo 列表的参数
    """
    # 更新上下文中的状态
    ctx.todo_state = args.todos
    
    # 构造展示用的输出
    # 这里我们生成一个简化的文本表示，但 data 字段包含完整的结构化数据
    output_lines = ["Current Plan Status:"]
    
    def _format_item(item, indent=0):
        status_markers = {
            "pending": "[ ]",
            "in_progress": "[-]",
            "completed": "[x]",
            "failed": "[!]",
            "skipped": "[?]"
        }
        marker = status_markers.get(item.get("status"), "[ ]")
        prefix = "  " * indent
        return f"{prefix}{marker} {item.get('title')} (ID: {item.get('id')})"

    for item in args.todos:
        output_lines.append(_format_item(item))
        for sub in item.get("subtasks", []):
            output_lines.append(_format_item(sub, indent=1))


    return ToolResult(
        success=True,
        output="\n".join(output_lines),
        data={
            "action": "display_todo",  # 标记：请求前端展示
            "todos": ctx.todo_state
        }
    )


def update_todo(ctx: ToolContext, args: UpdateTodoArgs) -> ToolResult:
    """
    更新单个 Todo 任务的状态。
    
    参数:
        ctx (ToolContext): 工具执行上下文
        args (UpdateTodoArgs): 包含任务 ID 和新状态的参数
    """
    # 递归查找并更新任务
    updated = False
    
    def _update_recursive(items: List[Dict[str, Any]]):
        nonlocal updated
        for item in items:
            if str(item.get("id")) == str(args.id):
                item["status"] = args.status
                updated = True
                return
            if item.get("subtasks"):
                _update_recursive(item["subtasks"])
                if updated: return

    if not ctx.todo_state:
        return ToolResult(success=False, output="Error: No todo list found.")

    _update_recursive(ctx.todo_state)
    
    if not updated:
        return ToolResult(success=False, output=f"Error: Todo item with ID '{args.id}' not found.")

    # 构造展示用的输出 (复用 update_todo_list 的逻辑)
    output_lines = ["Updated Plan Status:"]
    
    def _format_item(item, indent=0):
        status_markers = {
            "pending": "[ ]",
            "in_progress": "[-]",
            "completed": "[x]",
            "failed": "[!]",
            "skipped": "[?]"
        }
        marker = status_markers.get(item.get("status"), "[ ]")
        prefix = "  " * indent
        return f"{prefix}{marker} {item.get('title')} (ID: {item.get('id')})"

    for item in ctx.todo_state:
        output_lines.append(_format_item(item))
        for sub in item.get("subtasks", []):
            output_lines.append(_format_item(sub, indent=1))

    return ToolResult(
        success=True,
        output="\n".join(output_lines),
        data={
            "action": "display_todo",
            "todos": ctx.todo_state
        }
    )
