from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from agent_tools.base import ToolContext, ToolResult

# --- Argument Models ---

class FollowUpOption(BaseModel):
    text: str = Field(..., description="Suggested answer the user can pick")
    mode: Optional[str] = Field(None, description="Optional mode slug to switch to if this suggestion is chosen (e.g., code, architect)")

class AskFollowupQuestionArgs(BaseModel):
    question: str = Field(..., description="Clear, specific question that captures the missing information you need")
    follow_up: List[FollowUpOption] = Field(..., min_items=2, max_items=4, description="Required list of 2-4 suggested responses; each suggestion must be a complete, actionable answer and may include a mode switch")

class AttemptCompletionArgs(BaseModel):
    result: str = Field(..., description="Final result message to deliver to the user once the task is complete")

class NewTaskArgs(BaseModel):
    mode: str = Field(..., description="Slug of the mode to begin the new task in (e.g., code, debug, architect)")
    message: str = Field(..., description="Initial user instructions or context for the new task")
    todos: Optional[str] = Field(None, description="Optional initial todo list written as a markdown checklist; required when the workspace mandates todos")

class SwitchModeArgs(BaseModel):
    mode_slug: str = Field(..., description="Slug of the mode to switch to (e.g., code, ask, architect)")
    reason: str = Field(..., description="Explanation for why the mode switch is needed")

class UpdateTodoListArgs(BaseModel):
    todos: str = Field(..., description="Full markdown checklist in execution order, using [ ] for pending, [x] for completed, and [-] for in progress")

class FetchInstructionsArgs(BaseModel):
    task: Literal["create_mcp_server", "create_mode"] = Field(..., description="Task identifier to fetch instructions for")

# --- Tool Implementations ---

def ask_followup_question(ctx: ToolContext, args: AskFollowupQuestionArgs) -> ToolResult:
    """
    Ask the user a question to gather additional information needed to complete the task. Use when you need clarification or more details to proceed effectively.

    Parameters:
    - question: (required) A clear, specific question addressing the information needed
    - follow_up: (required) A list of 2-4 suggested answers. Suggestions must be complete, actionable answers without placeholders. Optionally include mode to switch modes (code/architect/etc.)
    """
    
    print(f"\n\033[93mQUESTION: {args.question}\033[0m")
    options = args.follow_up
    
    # === Web Environment Support ===
    if getattr(ctx, 'env', 'cli') == 'web':
        # 在 Web 环境下，不进行 input() 阻塞，而是返回特定的数据结构
        # Runtime 收到这个 Result 后，应该将 tool call 标记为完成 (或者 pending?) 
        # 本质上，我们希望前端展示选项。
        # 这里返回 success=True，但在 data 中带上 'action': 'ask_user'
        # 这样 Runtime 检测到 output 中包含特定标记或者 data 结构时，可以 yield 给前端
        
        return ToolResult(
            success=True, 
            output="[WAITING FOR USER INPUT]", # 占位符，实际回答由前端再次发送
            data={
                "action": "ask_user",
                "question": args.question,
                "options": [opt.dict() for opt in options]
            }
        )

    # === CLI Environment (Interactive Block) ===
    # 打印选项
    for i, opt in enumerate(options):
        mode_info = f" (Switch to Mode: {opt.mode})" if opt.mode else ""
        print(f"{i + 1}. {opt.text}{mode_info}")
    
    # 添加自定义选项
    print("0. Custom Input (Enter your own answer)")
    
    selected_text = ""
    
    while True:
        try:
            choice_str = input("\n请选择一项 (Enter number): ").strip()
            if not choice_str:
                continue
                
            choice = int(choice_str)
            
            if choice == 0:
                # Custom input
                custom_ans = input("请输入您的回答: ").strip()
                if custom_ans:
                    selected_text = custom_ans
                    break
                else:
                    print("回答不能为空，请重新输入。")
            elif 1 <= choice <= len(options):
                # Pre-defined option
                selected_opt = options[choice - 1]
                selected_text = selected_opt.text
                
                # Check for mode switch
                if selected_opt.mode:
                     if hasattr(ctx, 'mode'):
                        ctx.mode = selected_opt.mode
                        print(f"[System] Switching mode to: {selected_opt.mode}")
                break
            else:
                print(f"无效选项，请输入 0 到 {len(options)}")
        except ValueError:
            print("输入无效，请输入数字。")
            
    return ToolResult(success=True, output=f"USER ANSWER: {selected_text}", data=args.dict())

def attempt_completion(ctx: ToolContext, args: AttemptCompletionArgs) -> ToolResult:
    """
    After each tool use, the user will respond with the result of that tool use, i.e. if it succeeded or failed, along with any reasons for failure. Once you've received the results of tool uses and can confirm that the task is complete, use this tool to present the result of your work to the user. The user may respond with feedback if they are not satisfied with the result, which you can use to make improvements and try again.

    IMPORTANT NOTE: This tool CANNOT be used until you've confirmed from the user that any previous tool uses were successful. Failure to do so will result in code corruption and system failure. Before using this tool, you must confirm that you've received successful results from the user for any previous tool uses. If not, then DO NOT use this tool.

    Parameters:
    - result: (required) The result of the task. Formulate this result in a way that is final and does not require further input from the user. Don't end your result with questions or offers for further assistance.

    Example: Completing after updating CSS
    { "result": "I've updated the CSS to use flexbox layout for better responsiveness" }
    """
    # print(f"\n\033[92mTASK COMPLETED: {args.result}\033[0m")
    return ToolResult(success=True, output=f"TASK COMPLETED: {args.result}")

def new_task(ctx: ToolContext, args: NewTaskArgs) -> ToolResult:
    """
    This will let you create a new task instance in the chosen mode using your provided message and initial todo list (if required).
    """
    ctx.mode = args.mode
    if args.todos:
        ctx.todos = [line.strip() for line in args.todos.splitlines() if line.strip()]
    else:
        ctx.todos = []
        
    return ToolResult(success=True, output=f"Started new task in mode '{args.mode}': {args.message}")

def switch_mode(ctx: ToolContext, args: SwitchModeArgs) -> ToolResult:
    """
    Request to switch to a different mode. This tool allows modes to request switching to another mode when needed, such as switching to Code mode to make code changes. The user must approve the mode switch.
    """
    old_mode = ctx.mode
    ctx.mode = args.mode_slug
    return ToolResult(success=True, output=f"Switched mode from '{old_mode}' to '{args.mode_slug}'. Reason: {args.reason}")

def update_todo_list(ctx: ToolContext, args: UpdateTodoListArgs) -> ToolResult:
    """
    Replace the entire TODO list with an updated checklist reflecting the current state. Always provide the full list; the system will overwrite the previous one. This tool is designed for step-by-step task tracking, allowing you to confirm completion of each step before updating, update multiple task statuses at once (e.g., mark one as completed and start the next), and dynamically add new todos discovered during long or complex tasks.

    Checklist Format:
    - Use a single-level markdown checklist (no nesting or subtasks)
    - List todos in the intended execution order
    - Status options: [ ] (pending), [x] (completed), [-] (in progress)

    Core Principles:
    - Before updating, always confirm which todos have been completed
    - You may update multiple statuses in a single update
    - Add new actionable items as they're discovered
    - Only mark a task as completed when fully accomplished
    - Keep all unfinished tasks unless explicitly instructed to remove

    Example: Initial task list
    { "todos": "[x] Analyze requirements\\n[x] Design architecture\\n[-] Implement core logic\\n[ ] Write tests\\n[ ] Update documentation" }

    Example: After completing implementation
    { "todos": "[x] Analyze requirements\\n[x] Design architecture\\n[x] Implement core logic\\n[-] Write tests\\n[ ] Update documentation\\n[ ] Add performance benchmarks" }

    When to Use:
    - Task involves multiple steps or requires ongoing tracking
    - Need to update status of several todos at once
    - New actionable items are discovered during execution
    - Task is complex and benefits from stepwise progress tracking

    When NOT to Use:
    - Only a single, trivial task
    - Task can be completed in one or two simple steps
    - Request is purely conversational or informational
    """
    ctx.todos = [line.strip() for line in args.todos.splitlines() if line.strip()]
    return ToolResult(success=True, output="TODO list updated.")

def fetch_instructions(ctx: ToolContext, args: FetchInstructionsArgs) -> ToolResult:
    """
    Retrieve detailed instructions for performing a predefined task, such as creating an MCP server or creating a mode.
    """
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
    
    content = instructions.get(args.task, "No instructions found.")
    return ToolResult(success=True, output=content)
