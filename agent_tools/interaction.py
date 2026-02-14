"""
=============================================================================
ownAgent - 用户交互工具模块
=============================================================================

本文件实现了所有与用户交互相关的工具：

1. ask_followup_question - 向用户提问获取更多信息
2. attempt_completion - 完成任务并返回结果
3. new_task - 创建新任务
4. switch_mode - 切换工作模式
5. update_todo_list - 更新待办事项列表
6. fetch_instructions - 获取预定义任务的指令

这些工具让 AI 能够：
- 在需要时向用户请求更多信息
- 报告任务完成
- 管理任务状态和工作模式

作者: ownAgent Team
版本: 1.0.0
=============================================================================
"""

# =============================================================================
# 标准库导入
# =============================================================================

from typing import List, Optional, Literal  # 类型提示
# Literal 用于限制参数为特定的字面值

# =============================================================================
# 第三方库导入
# =============================================================================

from pydantic import BaseModel, Field  # 数据验证和设置管理

# =============================================================================
# 项目内部模块导入
# =============================================================================

from agent_tools.base import ToolContext, ToolResult


# =============================================================================
# 参数模型定义 (Argument Models)
# =============================================================================

class FollowUpOption(BaseModel):
    """
    后续问题的选项模型。
    
    当 AI 向用户提问时，可以提供几个预设的选项供用户选择，
    这样用户不需要手动输入，提高交互效率。
    
    属性:
        text (str): 建议的回答文本
            - 必须是完整的、可执行的答案
            - 不能包含占位符
        
        mode (Optional[str]): 可选的模式切换
            - 如果用户选择此选项，可以自动切换到指定模式
            - 例如："code", "architect", "debug" 等
    
    示例:
        >>> option = FollowUpOption(
        ...     text="创建一个新的 Python 文件",
        ...     mode="code"
        ... )
    """
    text: str = Field(
        ...,
        description="Suggested answer the user can pick"
    )
    mode: Optional[str] = Field(
        None,
        description="Optional mode slug to switch to if this suggestion is chosen (e.g., code, architect)"
    )


class AskFollowupQuestionArgs(BaseModel):
    """
    ask_followup_question 工具的参数模型。
    
    属性:
        question (str): 清晰、具体的问题
            - 应该直接指出需要什么信息
            - 避免模糊或开放性的问题
        
        follow_up (List[FollowUpOption]): 建议的回答列表
            - 必须包含 2-4 个选项
            - 每个选项应该是完整的、可执行的答案
    
    示例:
        >>> args = AskFollowupQuestionArgs(
        ...     question="您希望使用哪种数据库？",
        ...     follow_up=[
        ...         FollowUpOption(text="SQLite（轻量级）"),
        ...         FollowUpOption(text="PostgreSQL（生产级）"),
        ...         FollowUpOption(text="MySQL（广泛使用）")
        ...     ]
        ... )
    """
    question: str = Field(
        ...,
        description="Clear, specific question that captures the missing information you need"
    )
    follow_up: List[FollowUpOption] = Field(
        ...,
        min_items=2,   # 最少 2 个选项
        max_items=4,   # 最多 4 个选项
        description="Required list of 2-4 suggested responses; each suggestion must be a complete, actionable answer and may include a mode switch"
    )


class AttemptCompletionArgs(BaseModel):
    """
    attempt_completion 工具的参数模型。
    
    这个工具用于标记任务完成并返回最终结果。
    
    属性:
        result (str): 任务的最终结果
            - 应该是完整的、不需要用户进一步输入的
            - 不要以问题或提供进一步帮助结尾
    
    注意:
        - 使用此工具前，必须确认之前的工具调用都成功了
        - 这是任务结束的标志，Runtime 会停止循环
    
    示例:
        >>> args = AttemptCompletionArgs(
        ...     result="我已成功创建了 Python HTTP 服务器脚本，监听端口 8000。"
        ... )
    """
    result: str = Field(
        ...,
        description="Final result message to deliver to the user once the task is complete"
    )


class NewTaskArgs(BaseModel):
    """
    new_task 工具的参数模型。
    
    这个工具用于创建一个新的任务实例，可以在指定模式下开始。
    
    属性:
        mode (str): 新任务的模式
            - "code": 编写代码
            - "architect": 架构设计
            - "debug": 调试问题
            - "ask": 回答问题
        
        message (str): 新任务的初始指令或上下文
        
        todos (Optional[str]): 可选的初始待办事项列表
            - Markdown 格式的检查列表
            - 某些工作区可能要求必须有 TODO 列表
    
    示例:
        >>> args = NewTaskArgs(
        ...     mode="code",
        ...     message="创建一个 REST API 端点",
        ...     todos="[ ] 设计路由\\n[ ] 实现处理函数\\n[ ] 添加测试"
        ... )
    """
    mode: str = Field(
        ...,
        description="Slug of the mode to begin the new task in (e.g., code, debug, architect)"
    )
    message: str = Field(
        ...,
        description="Initial user instructions or context for the new task"
    )
    todos: Optional[str] = Field(
        None,
        description="Optional initial todo list written as a markdown checklist; required when the workspace mandates todos"
    )


class SwitchModeArgs(BaseModel):
    """
    switch_mode 工具的参数模型。
    
    这个工具用于切换 AI 的工作模式。
    
    属性:
        mode_slug (str): 目标模式的标识符
            - "code": 代码模式
            - "ask": 问答模式
            - "architect": 架构模式
            - "debug": 调试模式
            - "orchestrator": 编排模式
        
        reason (str): 切换模式的原因
            - 解释为什么需要切换
            - 帮助用户理解上下文
    
    示例:
        >>> args = SwitchModeArgs(
        ...     mode_slug="debug",
        ...     reason="需要排查代码中的错误"
        ... )
    """
    mode_slug: str = Field(
        ...,
        description="Slug of the mode to switch to (e.g., code, ask, architect)"
    )
    reason: str = Field(
        ...,
        description="Explanation for why the mode switch is needed"
    )


class UpdateTodoListArgs(BaseModel):
    """
    update_todo_list 工具的参数模型。
    
    这个工具用于更新待办事项列表，跟踪任务进度。
    
    属性:
        todos (str): 完整的 Markdown 检查列表
            - 使用 [ ] 表示待办
            - 使用 [x] 表示已完成
            - 使用 [-] 表示进行中（可选）
    
    格式说明:
        - 单层列表，不支持嵌套
        - 按执行顺序排列
        - 每次更新提供完整列表（会覆盖之前的）
    
    示例:
        >>> args = UpdateTodoListArgs(
        ...     todos="[x] 分析需求\\n[x] 设计架构\\n[-] 实现核心逻辑\\n[ ] 编写测试"
        ... )
    """
    todos: str = Field(
        ...,
        description="Full markdown checklist in execution order, using [ ] for pending, [x] for completed, and [-] for in progress"
    )


class FetchInstructionsArgs(BaseModel):
    """
    fetch_instructions 工具的参数模型。
    
    这个工具用于获取预定义任务的详细指令。
    
    属性:
        task (Literal[...]): 任务标识符
            - 只能是预定义的任务类型
            - 目前支持："create_mcp_server", "create_mode"
    
    示例:
        >>> args = FetchInstructionsArgs(task="create_mode")
    """
    task: Literal["create_mcp_server", "create_mode"] = Field(
        ...,
        description="Task identifier to fetch instructions for"
    )


# =============================================================================
# 工具实现 (Tool Implementations)
# =============================================================================

def ask_followup_question(ctx: ToolContext, args: AskFollowupQuestionArgs) -> ToolResult:
    """
    向用户提问以获取完成任务所需的额外信息。
    
    当 AI 需要更多信息才能继续时使用此工具。
    例如：用户说"创建一个服务器"，AI 需要询问使用什么技术栈。
    
    参数:
        ctx (ToolContext): 工具执行上下文
        args (AskFollowupQuestionArgs): 工具参数
    
    返回:
        ToolResult: 包含用户回答的结果
    
    行为说明:
        - CLI 环境：打印问题并等待用户输入
        - Web 环境：返回特殊数据结构，由前端展示选项
    
    Web 环境特殊处理:
        返回的 ToolResult.data 包含：
        - action: "ask_user" 标记
        - question: 问题文本
        - options: 选项列表
        
        Runtime 检测到这个结构后，会暂停执行循环，
        等待前端用户选择后继续。
    """
    # 打印问题（黄色高亮）
    # \033[93m 是 ANSI 黄色转义码
    print(f"\n\033[93mQUESTION: {args.question}\033[0m")
    options = args.follow_up
    
    # === Web 环境处理 ===
    # 检查运行环境
    if getattr(ctx, 'env', 'cli') == 'web':
        # 在 Web 环境下，不能使用 input() 阻塞
        # 返回特殊数据结构，让前端处理用户交互
        
        return ToolResult(
            success=True, 
            output="[WAITING FOR USER INPUT]",  # 占位符
            data={
                "action": "ask_user",           # 标记：需要用户输入
                "question": args.question,       # 问题文本
                "options": [opt.dict() for opt in options]  # 选项列表
            }
        )

    # === CLI 环境（交互式阻塞）===
    
    # 打印所有选项
    for i, opt in enumerate(options):
        # 如果选项有模式切换，显示提示
        mode_info = f" (Switch to Mode: {opt.mode})" if opt.mode else ""
        print(f"{i + 1}. {opt.text}{mode_info}")
    
    # 添加自定义输入选项
    print("0. Custom Input (Enter your own answer)")
    
    selected_text = ""  # 用户选择的文本
    
    # 等待用户输入循环
    while True:
        try:
            # 读取用户选择
            choice_str = input("\n请选择一项 (Enter number): ").strip()
            
            if not choice_str:
                continue  # 空输入，重新等待
                
            choice = int(choice_str)  # 转换为数字
            
            if choice == 0:
                # 用户选择自定义输入
                custom_ans = input("请输入您的回答: ").strip()
                if custom_ans:
                    selected_text = custom_ans
                    break
                else:
                    print("回答不能为空，请重新输入。")
                    
            elif 1 <= choice <= len(options):
                # 用户选择了预设选项
                selected_opt = options[choice - 1]
                selected_text = selected_opt.text
                
                # 检查是否需要切换模式
                if selected_opt.mode:
                    if hasattr(ctx, 'mode'):
                        ctx.mode = selected_opt.mode
                        print(f"[System] Switching mode to: {selected_opt.mode}")
                break
                
            else:
                print(f"无效选项，请输入 0 到 {len(options)}")
                
        except ValueError:
            print("输入无效，请输入数字。")
            
    # 返回用户的选择
    return ToolResult(
        success=True, 
        output=f"USER ANSWER: {selected_text}", 
        data=args.dict()  # 包含原始参数，便于调试
    )


def attempt_completion(ctx: ToolContext, args: AttemptCompletionArgs) -> ToolResult:
    """
    完成任务并返回最终结果。
    
    这是任务结束的标志。当 AI 认为任务已完成时，
    使用此工具向用户报告结果。
    
    参数:
        ctx (ToolContext): 工具执行上下文
        args (AttemptCompletionArgs): 工具参数
    
    返回:
        ToolResult: 包含完成消息的结果
    
    重要说明:
        - 使用前必须确认之前的工具调用都成功了
        - 结果应该是最终的，不需要用户进一步输入
        - 不要以问题或"还需要其他帮助吗"结尾
        - Runtime 检测到此工具调用后会停止循环
    
    示例:
        任务：创建一个 Python HTTP 服务器
        结果："我已创建了一个简单的 HTTP 服务器脚本 server.py，
              监听端口 8000。运行 python server.py 启动服务器。"
    """
    # 返回完成结果
    # Runtime 会检测这个工具调用并停止执行循环
    return ToolResult(
        success=True, 
        output=f"TASK COMPLETED: {args.result}"
    )


def new_task(ctx: ToolContext, args: NewTaskArgs) -> ToolResult:
    """
    创建一个新的任务实例。
    
    这个工具允许 AI 在指定模式下开始一个新任务，
    并设置初始的待办事项列表。
    
    参数:
        ctx (ToolContext): 工具执行上下文
        args (NewTaskArgs): 工具参数
    
    返回:
        ToolResult: 包含新任务信息的结果
    
    功能:
        1. 切换到指定模式
        2. 设置初始待办事项列表
        3. 清除之前的上下文（由 Runtime 处理）
    """
    # 切换模式
    ctx.mode = args.mode
    
    # 设置待办事项列表
    if args.todos:
        # 将 Markdown 格式的 TODO 转换为列表
        ctx.todos = [line.strip() for line in args.todos.splitlines() if line.strip()]
    else:
        ctx.todos = []
        
    return ToolResult(
        success=True, 
        output=f"Started new task in mode '{args.mode}': {args.message}"
    )


def switch_mode(ctx: ToolContext, args: SwitchModeArgs) -> ToolResult:
    """
    切换到不同的工作模式。
    
    不同模式有不同的能力和限制：
    - Code 模式：可以编辑代码文件
    - Architect 模式：只能编辑 Markdown 文件
    - Ask 模式：只读，不能修改文件
    - Debug 模式：专注于调试
    
    参数:
        ctx (ToolContext): 工具执行上下文
        args (SwitchModeArgs): 工具参数
    
    返回:
        ToolResult: 包含切换信息的结果
    
    注意:
        模式切换需要用户批准。
    """
    # 记录旧模式
    old_mode = ctx.mode
    
    # 切换到新模式
    ctx.mode = args.mode_slug
    
    return ToolResult(
        success=True, 
        output=f"Switched mode from '{old_mode}' to '{args.mode_slug}'. Reason: {args.reason}"
    )


def update_todo_list(ctx: ToolContext, args: UpdateTodoListArgs) -> ToolResult:
    """
    更新待办事项列表。
    
    这个工具用于跟踪多步骤任务的进度。
    每次更新都会完全替换之前的列表。
    
    参数:
        ctx (ToolContext): 工具执行上下文
        args (UpdateTodoListArgs): 工具参数
    
    返回:
        ToolResult: 确认更新的结果
    
    使用原则:
        1. 更新前确认哪些任务已完成
        2. 可以一次更新多个状态
        3. 发现新任务时动态添加
        4. 只有完全完成时才标记 [x]
        5. 保留未完成的任务
    
    TODO 格式:
        [ ] 待办任务
        [x] 已完成任务
        [-] 进行中任务（可选）
    
    示例:
        初始状态：
        [x] 分析需求
        [x] 设计架构
        [-] 实现核心逻辑
        [ ] 编写测试
        [ ] 更新文档
        
        完成实现后：
        [x] 分析需求
        [x] 设计架构
        [x] 实现核心逻辑
        [-] 编写测试
        [ ] 更新文档
        [ ] 添加性能测试
    """
    # 将 Markdown 格式转换为列表存储
    # 过滤掉空行
    ctx.todos = [line.strip() for line in args.todos.splitlines() if line.strip()]
    
    return ToolResult(success=True, output="TODO list updated.")


def fetch_instructions(ctx: ToolContext, args: FetchInstructionsArgs) -> ToolResult:
    """
    获取预定义任务的详细指令。
    
    这个工具提供一些常见任务的步骤指南。
    
    参数:
        ctx (ToolContext): 工具执行上下文
        args (FetchInstructionsArgs): 工具参数
    
    返回:
        ToolResult: 包含任务指令的结果
    
    支持的任务:
        - create_mcp_server: 创建 MCP 服务器
        - create_mode: 创建新模式
    """
    # 预定义的指令库
    instructions = {
        "create_mcp_server": """
# Creating an MCP Server
1. Define the server capabilities.
2. Implement the protocol handlers.
3. Register tools and resources.
4. Test with an MCP client.
""",
        "create_mode": """
# Creating a Mode
1. Define the mode configuration.
2. Specify available tools.
3. Set up the prompt template.
4. Register the mode in the system.
"""
    }
    
    # 获取对应任务的指令
    content = instructions.get(args.task, "No instructions found.")
    
    return ToolResult(success=True, output=content)
