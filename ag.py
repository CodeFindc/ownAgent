"""
=============================================================================
ownAgent - AI 编程助手核心模块
=============================================================================

本文件是 ownAgent 项目的核心引擎，包含以下主要组件：

1. LLMTransport (第4层) - 负责与大语言模型 API 通信
2. ContextManager (第3层) - 管理对话历史和系统提示词
3. ToolExecutor (第3层) - 注册和执行工具
4. StreamInterpreter (第3层) - 解析流式响应
5. AgentRuntime (第3层) - 核心循环，协调各组件
6. CLI (第1层) - 命令行界面

架构说明：
┌─────────────────────────────────────────────────────────────┐
│                    用户界面层 (Layer 1)                      │
│                      CLI / Web 界面                          │
├─────────────────────────────────────────────────────────────┤
│                    核心运行时层 (Layer 3)                     │
│    AgentRuntime → ContextManager + ToolExecutor             │
├──────────────────────────────────────────────────────��──────┤
│                    传输层 (Layer 4)                          │
│                     LLMTransport                             │
└─────────────────────────────────────────────────────────────┘

作者: ownAgent Team
版本: 1.0.0
=============================================================================
"""

# =============================================================================
# 标准库导入
# =============================================================================

import os          # 操作系统接口，用于文件路径操作、环境变量等
import json        # JSON 数据处理，用于解析 LLM 返回的参数
import time        # 时间相关功能，用于计时和延迟
import inspect     # 检查对象，用于判断函数是否为异步函数
import asyncio     # 异步 I/O，用于运行异步主循环

# =============================================================================
# 第三方库导入
# =============================================================================

from pathlib import Path  # 面向对象的文件路径处理，比 os.path 更现代
from dotenv import load_dotenv  # 从 .env 文件加载环境变量
from pydantic import BaseModel, Field  # 数据验证和设置管理
# typing 模块提供类型提示支持，让代码更清晰、IDE 支持更好
from typing import Dict, Any, Callable, Type, List, Generator, Union
# OpenAI 官方 SDK，用于调用 LLM API
from openai import AsyncOpenAI, DefaultHttpxClient
import httpx  # 现代化的 HTTP 客户端库

# =============================================================================
# 项目内部模块导入 - 工具系统
# =============================================================================

# 基础类型定义
from agent_tools.base import ToolContext, ToolResult

# 文件操作工具 (IO Tools)
# 这些工具用于文件系统的读写操作
from agent_tools.io import (
    list_files, ListFilesArgs,        # 列出目录内容
    read_file, ReadFileArgs,          # 读取文件
    write_to_file, WriteToFileArgs,   # 写入文件
    delete_file, DeleteFileArgs,      # 删除文件/目录
    search_files, SearchFilesArgs,    # 正则搜索文件内容
    edit_file, EditFileArgs           # 编辑文件（搜索替换）
)

# 系统命令工具
from agent_tools.system import execute_command, ExecuteCommandArgs

# 浏览器自动化工具
from agent_tools.browser import browser_action, BrowserActionArgs

# 差异应用工具（精确编辑文件）
from agent_tools.diff import apply_diff, ApplyDiffArgs

# 用户交互工具
from agent_tools.interaction import (
    ask_followup_question, AskFollowupQuestionArgs,  # 向用户提问
    attempt_completion, AttemptCompletionArgs,        # 完成任务
    new_task, NewTaskArgs,                            # 创建新任务
    switch_mode, SwitchModeArgs,                      # 切换模式
    fetch_instructions, FetchInstructionsArgs         # 获取指令
)

# 技能系统工具
from agent_tools.skills import (
    list_skills, ListSkillsArgs,      # 列出所有技能
    search_skills, SearchSkillsArgs,  # 搜索技能
    get_skill, GetSkillArgs           # 获取技能详情
)

# 技能加载器和管理器
from agent_tools.skills_loader import SkillsLoader
from agent_tools.skills_manager import SkillsManager

# 导入 MCP 模块
from agent_tools.mcp.client import McpClient
from agent_tools.mcp.transport import StdioTransport, SseTransport



# =============================================================================
# Layer 4: LLM Transport (负责与模型通讯)
# =============================================================================
# 这一层负责与大语言模型 API 进行通信，处理请求发送和响应接收
# =============================================================================

def generate_openai_schema(func: Callable, args_model: Type[BaseModel]) -> dict:
    """
    自动将函数和 Pydantic 参数模型转换为 OpenAI Function Calling 要求的 Schema 格式。
    
    这是实现工具自动注册的关键函数。通过 Pydantic 模型定义参数，
    可以自动生成符合 OpenAI API 要求的 JSON Schema。
    
    参数:
        func (Callable): 要注册的工具函数，函数名和 docstring 会被自动提取
        args_model (Type[BaseModel]): Pydantic 模型类，定义工具的参数结构
    
    返回:
        dict: 符合 OpenAI Function Calling 格式的 Schema 字典
    
    示例:
        >>> def read_file(ctx, args):
        ...     '''读取文件内容'''
        ...     pass
        >>> class ReadFileArgs(BaseModel):
        ...     path: str = Field(..., description="文件路径")
        >>> schema = generate_openai_schema(read_file, ReadFileArgs)
        >>> print(schema)
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "读取文件内容",
                "parameters": {"type": "object", "properties": {...}}
            }
        }
    """
    # 步骤 1: 使用 Pydantic 的 model_json_schema() 方法生成原生 JSON Schema
    # 这会自动包含所有字段的类型、描述、必填项等信息
    raw_schema = args_model.model_json_schema()
    
    # 步骤 2: 清理 Pydantic 特有的字段
    # OpenAI API 不需要 'title' 字段，移除它可以减少 token 消耗
    if "title" in raw_schema:
        del raw_schema["title"]
    
    # 步骤 3: 组装成 OpenAI Function Calling 格式
    # 这个格式是 OpenAI API 要求的标准结构
    return {
        "type": "function",  # 固定值，表示这是一个函数调用
        "function": {
            "name": func.__name__,           # 自动提取函数名作为工具名
            "description": func.__doc__ or "", # 自动提取函数的 docstring 作为描述
            "parameters": raw_schema         # 参数定义，直接使用 Pydantic 生成的 Schema
        }
    }


class LLMTransport:
    """
    LLM 传输层 - 负责与大语言模型 API 进行通信。
    
    这个类封装了与 LLM API 的所有交互逻辑，包括：
    - 初始化 API 客户端
    - 发送流式请求
    - 处理错误和超时
    
    属性:
        client (AsyncOpenAI): OpenAI 异步客户端实例
        model (str): 使用的模型名称
    
    示例:
        >>> transport = LLMTransport(
        ...     api_key="sk-xxx",
        ...     base_url="https://api.openai.com/v1",
        ...     model="gpt-4"
        ... )
        >>> stream = await transport.send_stream_request(messages, tools)
    """
    
    def __init__(self, api_key: str, base_url: str, model: str = "Qwen/Qwen3-235B-A22B-Thinking-2507"):
        """
        初始化 LLM 传输层。
        
        参数:
            api_key (str): API 密钥，从环境变量或配置文件获取
            base_url (str): API 基础 URL，支持任何兼容 OpenAI API 的服务
            model (str): 模型名称，默认使用 Qwen 思考模型
                          可以是 "gpt-4", "deepseek-chat" 等
        
        注意:
            - verify=False 禁用 SSL 验证，仅用于开发环境
            - 生产环境应该使用有效的 SSL 证书
        """
        # 创建自定义 HTTP 客户端
        # verify=False 禁用 SSL 证书验证（某些自签名证书环境需要）
        http_client = httpx.AsyncClient(verify=False)
        
        # 初始化 OpenAI 异步客户端
        # 使用异步客户端可以支持流式响应，提升用户体验
        self.client = AsyncOpenAI(
            api_key=api_key,        # API 密钥
            base_url=base_url,      # API 基础 URL
            http_client=http_client # 自定义 HTTP 客户端
        )
        
        # 保存模型名称，后续请求时使用
        self.model = model
    
    async def send_stream_request(self, messages: List[Dict], tools: List[Dict] = None):
        """
        发送流式请求到 LLM API。
        
        这个方法返回一个异步生成器，可以逐步产出响应内容（Chunk）。
        流式响应的好处是用户可以实时看到 AI 的输出，而不需要等待完整响应。
        
        参数:
            messages (List[Dict]): 对话消息列表，格式为:
                [
                    {"role": "system", "content": "系统提示词"},
                    {"role": "user", "content": "用户消息"},
                    {"role": "assistant", "content": "AI 回复"},
                    {"role": "tool", "tool_call_id": "xxx", "content": "工具返回"}
                ]
            tools (List[Dict], optional): 工具定义列表，用于 Function Calling
        
        返回:
            AsyncStream: 异步流对象，可以异步迭代获取响应块
        
        示例:
            >>> stream = await transport.send_stream_request(messages, tools)
            >>> async for chunk in stream:
            ...     if chunk.choices[0].delta.content:
            ...         print(chunk.choices[0].delta.content, end="")
        """
        # 注意：以下注释掉的代码用于过滤 reasoning_content 字段
        # 某些 API 不支持这个字段，会导致报错
        # 但目前我们保留这个字段，因为它包含模型的思考过程
        
        try:
            # 调用 OpenAI API 创建聊天完成请求
            stream = await self.client.chat.completions.create(
                model=self.model,           # 使用的模型
                messages=messages,          # 对话历史
                tools=tools,                # 可用的工具列表
                tool_choice="auto" if tools else None,  # 工具选择策略：有工具时自动选择
                temperature=0,              # 温度设为 0，使输出更确定、一致
                stream=True                 # 关键：开启流式响应
            )
            return stream
            
        except Exception as e:
            # ��获并打印错误，返回 None 让调用者处理
            print(f"[Transport Error]: {e}")
            return None


# =============================================================================
# Layer 3: Agent Runtime Core (核心大脑: 上下文+规划+工具)
# =============================================================================
# 这一层是 Agent 的核心，负责：
# - 管理对话上下文
# - 执行工具调用
# - 协调各组件工作
# =============================================================================

class ContextManager:
    """
    上下文管理器 - 管理对话历史和系统提示词。
    
    这个类负责：
    - 维护完整的对话历史（包括系统提示词、用户消息、AI 回复、工具调用）
    - 自动保存和加载会话
    - 构建系统提示词（包含技能信息）
    
    对话历史格式遵循 OpenAI Chat API 标准：
    - system: 系统提示词，定义 AI 的行为
    - user: 用户消息
    - assistant: AI 回复
    - tool: 工具返回结果
    
    属性:
        skills_manager: 技能管理器实例
        logger: 日志记录器
        autosave_file: 自动保存的文件路径
        history: 对话历史列表
    """
    
    def __init__(self, skills_manager=None, logger=None, autosave_file: str = None):
        """
        初始化上下文管理器。
        
        参数:
            skills_manager: 技能管理器，用于获取可用技能信息
            logger: 日志记录器，用于记录对话
            autosave_file (str, optional): 自动保存的文件路径，每次对话后自动保存
        """
        # 获取当前工作目录，用于构建系统提示词
        workspace = os.getcwd()
        
        # 保存技能管理器和日志记录器的引用
        self.skills_manager = skills_manager
        self.logger = logger
        self.autosave_file = autosave_file
        
        # 构建系统提示词
        # 系统提示词定义了 AI 的行为方式和可用能力
        system_prompt = self._build_system_prompt(workspace)
        
        # 初始化对话历史，第一条消息永远是系统提示词
        self.history: List[Dict] = [
            {"role": "system", "content": system_prompt}
        ]

    def add_user_msg(self, content: str):
        """
        添加用户消息到对话历史。
        
        参数:
            content (str): 用户输入的消息内容
        
        这会：
        1. 创建标准格式的用户消息
        2. 记录到日志（如果有日志器）
        3. 添加到历史记录
        4. 自动保存（如果配置了自动保存）
        """
        # 创建用户消息字典
        user_msg = {"role": "user", "content": content}
        
        # 记录到日志
        if self.logger:
            self.logger.log_user(user_msg)
        
        # 添加到历史记录
        self.history.append(user_msg)
        
        # 自动保存到文件
        if self.autosave_file:
            self.save_history(self.autosave_file)

    def add_assistant_msg(self, message: Any):
        """
        添加 AI 助手消息到对话历史。
        
        参数:
            message (Any): AI 的回复消息，可以是字符串或字典
                          字典格式包含 content, tool_calls, reasoning_content 等字段
        
        注意:
            助手消息可能包含：
            - content: 文本内容
            - tool_calls: 工具调用请求
            - reasoning_content: 思考过程（某些模型支持）
        """
        # 记录到日志
        if self.logger:
            self.logger.log_assistant(str(message))
        
        # 添加到历史记录
        self.history.append(message)
        
        # 自动保存
        if self.autosave_file:
            self.save_history(self.autosave_file)

    def add_tool_output(self, tool_call_id: str, content: str):
        """
        添加工具执行结果到对话历史。
        
        参数:
            tool_call_id (str): 工具调用的唯一标识符，用于关联请求和响应
            content (str): 工具执行的返回结果
        
        工具消息格式：
            {
                "role": "tool",
                "tool_call_id": "call_xxx",  # 与 assistant 消息中的 tool_calls 关联
                "content": "执行结果..."
            }
        """
        # 创建工具返回消息
        tool_output = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content
        }
        
        # 记录到日志
        if self.logger:
            self.logger.log_tool(tool_call_id, tool_output)
        
        # 添加到历史记录
        self.history.append(tool_output)
        
        # 自动保存
        if self.autosave_file:
            self.save_history(self.autosave_file)

    def save_history(self, filepath: str):
        """
        将当前对话历史保存到 JSON 文件。
        
        参数:
            filepath (str): 保存的文件路径
        
        用途:
        - 会话持久化，下次可以继续对话
        - 调试和分析对话流程
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            # ensure_ascii=False 支持中文等非 ASCII 字符
            # indent=2 使 JSON 文件可读性更好
            json.dump(self.history, f, ensure_ascii=False, indent=2)

    def load_history(self, filepath: str):
        """
        从 JSON 文件加载对话历史。
        
        参数:
            filepath (str): 要加载的文件路径
        
        注意:
            - 会保留当前的系统提示词（第一条消息）
            - 只加载用户、助手、工具消息
            - 这样可以更新系统提示词而不影响历史对话
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            loaded_history = json.load(f)
        
        # 如果加载的历史为空，直接返回
        if not loaded_history:
            return

        # 保留当前的系统提示词（self.history[0]）
        # 用加载的历史替换其余部分
        current_system = self.history[0]
        
        # 检查加载的历史是否有系统提示词（跳过它）
        start_idx = 0
        if loaded_history[0].get("role") == "system":
            start_idx = 1
            
        # 组合：当前系统提示词 + 加载的历史（跳过其系统提示词）
        self.history = [current_system] + loaded_history[start_idx:]

    def reset(self):
        """
        重置对话历史，只保留系统提示词。
        
        用途:
        - 开始新的对话会话
        - 清除上下文，避免历史信息干扰
        """
        workspace = os.getcwd()  # 重新获取工作目录
        
        if self.history:
            # 保留系统提示词（第一条消息）
            self.history = [self.history[0]]
        else:
            # 如果历史为空（不应该发生），重新创建系统提示词
            system_prompt = self._build_system_prompt(workspace)
            self.history = [{"role": "system", "content": system_prompt}]

    def _build_system_prompt(self, workspace: str) -> str:
        """
        构建系统提示词。
        
        参数:
            workspace (str): 当前工作目录路径
        
        返回:
            str: 完整的系统提示词
        
        系统提示词包含：
        1. AI 的身份和能力描述
        2. 工具使用规则
        3. 工作目录和系统信息
        4. 可用技能列表（如果有）
        
        这个提示词决定了 AI 的行为方式，是整个系统的核心配置。
        """
        # 基础提示词：定义 AI 的身份、能力和规则
        # 这是一个很长的提示词，包含所有必要的行为指导
        base_prompt = f"""You are  Code, a highly skilled software engineer with extensive knowledge in many programming languages, frameworks, design patterns, and best practices.

====

MARKDOWN RULES

ALL responses MUST show ANY `language construct` OR filename reference as clickable, exactly as [`filename OR language.declaration()`](relative/file/path.ext:line); line is required for `syntax` and optional for filename links. This applies to ALL markdown responses and ALSO those in attempt_completion

====

TOOL USE

You have access to a set of tools that are executed upon the user's approval. Use the provider-native tool-calling mechanism. Do not include XML markup or examples. **CRITICAL RULES:**
1. **You must use at least one tool call per assistant response.** You may attempt multiple calls if they are safe to execute in sequence.
2. **Do NOT call zero tools.** If you think the task is done, you MUST use the `attempt_completion` tool.
3. **Do NOT return a final answer as plain text.** You must encapsulate your final response in the `attempt_completion` tool arguments.
4. **Do NOT output conversational text without a tool call.**

# Tool Use Guidelines

1. Assess what information you already have and what information you need to proceed with the task.
2. Choose the most appropriate tool based on the task and tool descriptions provided. Assess if you need additional information to proceed, and which of the available tools would be most effective for gathering this information. For example using the list_files tool is more effective than running a command like `ls` in the terminal. It's critical that you think about each available tool and use the one that best fits the current step in the task.
3. If multiple actions are needed, use one tool at a time per message to accomplish the task iteratively, with each tool use being informed by the result of the previous tool use. Do not assume the outcome of any tool use. Each step must be informed by the previous step's result.
4. After each tool use, the user will respond with the result of that tool use. This result will provide you with the necessary information to continue your task or make further decisions. This response may include:
	 - Information about whether the tool succeeded or failed, along with any reasons for failure.
	 - Linter errors that may have arisen from the changes you made, which you'll need to address.
	 - New terminal output in reaction to the changes, which you may need to consider or act upon.
	 - Any other relevant feedback or information related to the tool use.

By carefully considering the user's response after tool executions, you can react accordingly and make informed decisions about how to proceed with the task. This iterative process helps ensure the overall success and accuracy of your work.



====

CAPABILITIES

- You have access to tools that let you execute CLI commands on the user's computer, list files, view source code definitions, regex search, read and write files, and ask follow-up questions. These tools help you effectively accomplish a wide range of tasks, such as writing code, making edits or improvements to existing files, understanding the current state of a project, performing system operations, and much more.
- When the user initially gives you a task, a recursive list of all filepaths in the current workspace directory ({workspace}) will be included in environment_details. This provides an overview of the project's file structure, offering key insights into the project from directory/file names (how developers conceptualize and organize their code) and file extensions (the language used). This can also guide decision-making on which files to explore further. If you need to further explore directories such as outside the current workspace directory, you can use the list_files tool. If you pass 'true' for the recursive parameter, it will list files recursively. Otherwise, it will list files at the top level, which is better suited for generic directories where you don't necessarily need the nested structure, like the Desktop.
- You can use the execute_command tool to run commands on the user's computer whenever you feel it can help accomplish the user's task. When you need to execute a CLI command, you must provide a clear explanation of what the command does. Prefer to execute complex CLI commands over creating executable scripts, since they are more flexible and easier to run. Interactive and long-running commands are allowed, since the commands are run in the user's VSCode terminal. The user may keep commands running in the background and you will be kept updated on their status along the way. Each command you execute is run in a new terminal instance.

====

MODES

- These are the currently available modes:
  * "Architect" mode (architect) - Use this mode when you need to plan, design, or strategize before implementation. Perfect for breaking down complex problems, creating technical specifications, designing system architecture, or brainstorming solutions before coding.
  * "Code" mode (code) - Use this mode when you need to write, modify, or refactor code. Ideal for implementing features, fixing bugs, creating new files, or making code improvements across any programming language or framework.
  * "Ask" mode (ask) - Use this mode when you need explanations, documentation, or answers to technical questions. Best for understanding concepts, analyzing existing code, getting recommendations, or learning about technologies without making changes.
  * "Debug" mode (debug) - Use this mode when you're troubleshooting issues, investigating errors, or diagnosing problems. Specialized in systematic debugging, adding logging, analyzing stack traces, and identifying root causes before applying fixes.
  * "Orchestrator" mode (orchestrator) - Use this mode for complex, multi-step projects that require coordination across different specialties. Ideal when you need to break down large tasks into subtasks, manage workflows, or coordinate work that spans multiple domains or expertise areas.
If the user asks you to create or edit a new mode for this project, you should read the instructions by using the fetch_instructions tool, like this:
<fetch_instructions>
<task>create_mode</task>
</fetch_instructions>


====

RULES

- The project base directory is: {workspace}
- All file paths must be relative to this directory. However, commands may change directories in terminals, so respect working directory specified by the response to execute_command.
- You cannot `cd` into a different directory to complete a task. You are stuck operating from '{workspace}', so be sure to pass in the correct 'path' parameter when using tools that require a path.
- Do not use the ~ character or $HOME to refer to the home directory.
- Before using the execute_command tool, you must first think about the SYSTEM INFORMATION context provided to understand the user's environment and tailor your commands to ensure they are compatible with their system. You must also consider if the command you need to run should be executed in a specific directory outside of the current working directory '{workspace}', and if so prepend with `cd`'ing into that directory && then executing the command (as one command since you are stuck operating from '{workspace}'). For example, if you needed to run `npm install` in a project outside of '{workspace}', you would need to prepend with a `cd` i.e. pseudocode for this would be `cd (path to project) && (command, in this case npm install)`.

- Some modes have restrictions on which files they can edit. If you attempt to edit a restricted file, the operation will be rejected with a FileRestrictionError that will specify which file patterns are allowed for the current mode.
- Be sure to consider the type of project (e.g., Python, JavaScript, web application) when determining the appropriate structure and files to include. Also consider what files may be most relevant to accomplishing the task, for example looking at a project's manifest file would help you understand the project's dependencies, which you could incorporate into any code you write.
  * For example, in architect mode trying to edit app.js would be rejected because architect mode can only edit files matching "\\.md$"
- When making changes to code, always consider the context in which the code is being used. Ensure that your changes are compatible with the existing codebase and that they follow the project's coding standards and best practices.
- Do not ask for more information than necessary. Use the tools provided to accomplish your user's request efficiently and effectively. When you've completed your user's task, you must use the attempt_completion tool to present the result of the task to the user. The user may provide feedback, which you can use to make improvements and try again.
- You are only allowed to ask the user questions using the ask_followup_question tool. Use this tool only when you need additional details to complete a task, and be sure to provide a clear and concise question that will help you move forward with the task. When you ask a question, provide the user with 2-4 suggested answers based on your question so they don't need to do so much typing. The suggestions should be specific, actionable, and directly related to the completed task. They should be ordered by priority or logical sequence. However if you can use the available tools to avoid having to ask the user questions, you should do so. For example, if the user mentions a file that may be in an outside directory like the Desktop, you should use the list_files tool to list the files in the Desktop and check if the file they are talking about is there, rather than asking the user to provide the file path themselves.
- When executing commands, if you don't see the expected output, assume the terminal executed the command successfully and proceed with the task. The user's terminal may be unable to stream the output back properly. If you absolutely need to see the actual terminal output, use the ask_followup_question tool to request the user to copy and paste it back to you.
- The user may provide a file's contents directly in their message, in which case you shouldn't use the read_file tool to get the file contents again since you already have it.
- Your goal is to try to accomplish the user's task, NOT engage in a back and forth conversation.
- NEVER end attempt_completion result with a question or request to engage in further conversation! Formulate the end of your result in a way that is final and does not require further input from the user.
- You are STRICTLY FORBIDDEN from starting your messages with "Great", "Certainly", "Okay", "Sure". You should NOT be conversational in your responses, but rather direct and to the point. For example you should NOT say "Great, I've updated the CSS" but instead something like "I've updated the CSS". It is important you be clear and technical in your messages.
- When presented with images, utilize your vision capabilities to thoroughly examine them and extract meaningful information. Incorporate these insights into your thought process as you accomplish the user's task.
- At the end of each user message, you will automatically receive environment_details. This information is not written by the user themselves, but is auto-generated to provide potentially relevant context about the project structure and environment. While this information can be valuable for understanding the project context, do not treat it as an explicit part of the user's request or response. Use it to inform your actions and decisions, but don't assume the user is explicitly asking about or referring to this information unless they clearly do so in their message. When using environment_details, explain your actions clearly to ensure the user understands, as they may not be aware of these details.
- Before executing commands, check the "Actively Running Terminals" section in environment_details. If present, consider how these active processes might impact your task. For example, if a local development server is already running, you wouldn't need to start it again. If no active terminals are listed, proceed with command execution as normal.
- MCP operations should be used one at a time, similar to other tool usage. Wait for confirmation of success before proceeding with additional operations.
- It is critical you wait for the user's response after each tool use, in order to confirm the success of the tool use. For example, if asked to make a todo app, you would create a file, wait for the user's response it was created successfully, then create another file if needed, wait for the user's response it was created successfully, etc.

====

SYSTEM INFORMATION

Operating System: Windows Server 2016
Default Shell: C:\\Windows\\system32\\cmd.exe
Home Directory: C:/Users/xsc
Current Workspace Directory: {workspace}

The Current Workspace Directory is the active VS Code project directory, and is therefore the default directory for all tool operations. New terminals will be created in the current workspace directory, however if you change directories in a terminal it will then have a different working directory; changing directories in a terminal does not modify the workspace directory, because you do not have access to change the workspace directory. When the user initially gives you a task, a recursive list of all filepaths in the current workspace directory ('/test/path') will be included in environment_details. This provides an overview of the project's file structure, offering key insights into the project from directory/file names (how developers conceptualize and organize their code) and file extensions (the language used). This can also guide decision-making on which files to explore further. If you need to further explore directories such as outside the current workspace directory, you can use the list_files tool. If you pass 'true' for the recursive parameter, it will list files recursively. Otherwise, it will list files at the top level, which is better suited for generic directories where you don't necessarily need the nested structure, like the Desktop.

====

OBJECTIVE

You accomplish a given task iteratively, breaking it down into clear steps and working through them methodically.

1. Analyze the user's task and set clear, achievable goals to accomplish it. Prioritize these goals in a logical order.
2. Work through these goals sequentially, utilizing available tools one at a time as necessary. Each goal should correspond to a distinct step in your problem-solving process. You will be informed on the work completed and what's remaining as you go.
3. Remember, you have extensive capabilities with access to a wide range of tools that can be used in powerful and clever ways as necessary to accomplish each goal. Before calling a tool, do some analysis. First, analyze the file structure provided in environment_details to gain context and insights for proceeding effectively. Next, think about which of the available tools is the most relevant tool to accomplish the user's task. Go through each of the required parameters of the relevant tool and determine if the user has directly provided or given enough information to infer a value. When deciding if the parameter can be inferred, carefully consider all the context to see if it supports a specific value. If all of the required parameters are present or can be reasonably inferred, proceed with the tool use. BUT, if one of the values for a required parameter is missing, DO NOT invoke the tool (not even with fillers for the missing params) and instead, ask the user to provide the missing parameters using the ask_followup_question tool. DO NOT ask for more information on optional parameters if it is not provided.
4. Once you've completed your user's task, you must use the attempt_completion tool to present the result of the task to the user.
5. The user may provide feedback, which you can use to make improvements and try again. But DO NOT continue in pointless back and forth conversations, i.e. don't end your results with questions or offers for further assistance.


====

USER'S CUSTOM INSTRUCTIONS

The following additional instructions are provided by the user, and should be followed to the best of your ability.

Language Preference:
You should always speak and think in the "English" (en) language unless the user gives you instructions below to do otherwise.

Rules:

# Agent Rules Standard (AGENTS.md):
# AGENTS.md

"""
        
        # 如果有技能管理器，添加可用技能的摘要信息
        # 这让 AI 知道有哪些技能可以使用
        if self.skills_manager:
            skills_summary = self.skills_manager.get_metadata_summary()
            base_prompt += f"""

## Available Skills

The following skills are available to assist with specific tasks:

{skills_summary}

When a task matches a skill's description, you can use the `get_skill` tool to retrieve the full skill content and follow its instructions.
"""
        
        return base_prompt


class ToolExecutor:
    """
    工具执行器 - 管理和执行所有注册的工具。
    
    这个类实现了工具的注册、Schema 生成和执行功能。
    采用"注册-执行"模式，让工具管理变得简单。
    
    属性:
        _execution_map (Dict): 存储工具执行逻辑的字典
            格式: {"工具名": (函数, 参数模型类)}
        _schemas (List[dict]): 存储工具 Schema 定义的列表
            用于传递给 LLM API
    
    使用流程:
        1. 创建 ToolExecutor 实例
        2. 调用 register() 注册工具
        3. 调用 get_definitions() 获取 Schema 传给 LLM
        4. 调用 execute() 执行工具
    """
    
    def __init__(self):
        """初始化工具执行器，创建空的存储结构。"""
        # 存储执行逻辑: { "工具名": (函数, 参数模型类) }
        self._execution_map: Dict[str, tuple] = {}
        
        # 存储对外定义: [ schema1, schema2, ... ]
        # 这些 Schema 会传给 LLM，让它知道有哪些工具可用
        self._schemas: List[dict] = []

    def register(self, func: Callable, args_model: Type[BaseModel]):
        """
        注册一个工具。
        
        一次注册，自动完成两件事：
        1. 存储执行逻辑（函数 + 参数模型）
        2. 生成并存入 Schema 定义
        
        参数:
            func (Callable): 工具函数，接受 (ctx, args) 两个参数
            args_model (Type[BaseModel]): Pydantic 参数模型类
        
        示例:
            >>> executor = ToolExecutor()
            >>> executor.register(read_file, ReadFileArgs)
            [INFO] 工具 [read_file] 已注册 (Schema 已自动生成)
        """
        # 获取函数名作为工具名
        name = func.__name__
        
        # 1. 存入执行表
        # 保存函数和参数模型的对应关系，执行时需要用到
        self._execution_map[name] = (func, args_model)
        
        # 2. 自动生成并存入 Schema 列表
        # 使用 generate_openai_schema 自动生成符合 OpenAI 格式的 Schema
        schema = generate_openai_schema(func, args_model)
        self._schemas.append(schema)
        
        # 打印注册成功信息
        print(f"[INFO] 工具 [{name}] 已注册 (Schema 已自动生成)")

    def register_mcp_tool(self, tool: Any, client: Any):
        """
        注册 MCP 工具。
        
        参数:
            tool: MCP Tool 对象 (from agent_tools.mcp.models)
            client: MCP Client 对象 (from agent_tools.mcp.client)
        """
        # 1. 构造 OpenAI Function Schema
        # MCP 的 inputSchema 就是 JSON Schema，可以直接使用
        schema = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema
            }
        }
        self._schemas.append(schema)
        
        # 2. 构造执行函数
        async def execute_mcp_tool(ctx, args: dict):
            """MCP 工具的包装执行函数"""
            # 调用 MCP 客户端
            result = await client.call_tool(tool.name, args)
            
            # 处理结果
            if result.isError:
                 return f"MCP Error: {result.content}"
            
            # 拼接所有文本内容
            text_content = []
            for item in result.content:
                if item.get("type") == "text":
                    text_content.append(item.get("text", ""))
                elif item.get("type") == "image":
                    text_content.append("[Image Content]")
                elif item.get("type") == "resource":
                    text_content.append(f"[Resource: {item.get('resource', {}).get('uri')}]")
            
            return "\n".join(text_content)

        # 3. 注册到执行表
        # 注意：这里我们存的是 (func, None)，因为没有 Pydantic 模型
        # execute 方法需要适配这种情况
        self._execution_map[tool.name] = (execute_mcp_tool, None)
        print(f"[INFO] MCP 工具 [{tool.name}] 已注册")

    def get_definitions(self) -> List[dict]:
        """
        获取所有工具的 Schema 定义。
        
        返回:
            List[dict]: 工具 Schema 列表，直接传给 OpenAI API 的 tools 参数
        
        示例:
            >>> tools = executor.get_definitions()
            >>> stream = await client.chat.completions.create(
            ...     model="gpt-4",
            ...     messages=messages,
            ...     tools=tools  # 传入工具定义
            ... )
        """
        return self._schemas

    async def execute(self, name: str, raw_args: dict, ctx: ToolContext) -> Any:
        """
        执行指定的工具。
        
        参数:
            name (str): 工具名称
            raw_args (dict): 原始参数字典，从 LLM 的 tool_call 中获取
            ctx (ToolContext): 工具执行上下文，包含工作目录、技能管理器等
        
        返回:
            Any: 工具执行结果，通常是 ToolResult 对象或字符串
        
        执行流程:
            1. 查找工具
            2. 使用 Pydantic 模型验证参数
            3. 判断函数是否异步
            4. 执行函数并返回结果
        """
        # 检查工具是否存在
        if name not in self._execution_map:
            return f"Error: Tool {name} not found"
            
        # 获取工具函数和参数模型
        func, args_model = self._execution_map[name]
        
        try:
            # 准备参数
            if args_model:
                # 使用 Pydantic 模型验证和转换参数
                args_instance = args_model(**raw_args)
            else:
                # 如果没有模型（如 MCP 工具），直接使用字典
                args_instance = raw_args
            
            # 判断函数是同步还是异步
            if inspect.iscoroutinefunction(func):
                # 异步函数：使用 await 调用
                result = await func(ctx, args_instance)
            else:
                # 同步函数：直接调用
                result = func(ctx, args_instance)
            
            return result
            
        except Exception as e:
            # 捕获并返回错误信息
            return f"Error executing {name}: {str(e)}"


class StreamInterpreter:
    """
    流式响应解析器。
    
    这个类负责解析 LLM 返回的流式响应，将其转换为统一的事件格式。
    
    主要功能：
    1. 实时 yield 事件给 Runtime (UI/Web)
    2. 拼接工具调用的参数（工具调用是分块传输的）
    3. 流结束后，返回完整的 Message 对象供 Runtime 存储
    
    事件类型：
    - thinking_delta: 思考过程增量（DeepSeek/Qwen 等模型支持）
    - content_delta: 文本内容增量
    - full_message: 完整消息（流结束时）
    
    示例:
        >>> interpreter = StreamInterpreter()
        >>> async for event in interpreter.parse_stream(stream):
        ...     if event["type"] == "content_delta":
        ...         print(event["content"], end="")
    """
    
    async def parse_stream(self, stream_generator):
        """
        解析流式响应。
        
        参数:
            stream_generator: OpenAI API 返回的异步流对象
        
        Yields:
            dict: 事件字典，格式为 {"type": "事件类型", "content": "内容"}
        
        处理流程：
        1. 遍历流中的每个 chunk
        2. 处理思考内容（reasoning_content）
        3. 处理文本内容（content）
        4. 拼接工具调用参数（tool_calls）
        5. 流结束时组装完整消息
        """
        # 累加器状态：用于拼接分块传输的内容
        final_content = ""       # 最终文本内容
        reasoning_content = ""   # 思考过程内容
        tool_calls_buffer = {}   # 工具调用缓冲区：index -> {id, name, args_str}

        # 检查流是否有效
        if not stream_generator:
            yield {"type": "error", "content": "Error: No stream"}
            return

        # 遍历流中的每个 chunk
        async for chunk in stream_generator:
            # 跳过没有 choices 的 chunk
            if not chunk.choices:
                continue
                
            # 获取 delta（增量内容）
            delta = chunk.choices[0].delta
            
            # === Case A: 处理思考过程 ===
            # DeepSeek、Qwen 等模型支持 reasoning_content 字段
            # 这是模型的"内心独白"，展示思考过程
            if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                reasoning_content += delta.reasoning_content
                # 实时 yield 给前端显示
                yield {"type": "thinking_delta", "content": delta.reasoning_content}

            # === Case B: 处理文本内容 ===
            # 这是 AI 的正式回复内容
            if delta.content:
                final_content += delta.content
                # 实时 yield 给前端显示
                yield {"type": "content_delta", "content": delta.content}

            # === Case C: 处理工具调用 ===
            # 工具调用是分块传输的，需要拼接
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    # index 是工具调用的序号（一个响应可能有多个工具调用）
                    idx = tc.index
                    
                    # 初始化该序号的缓冲槽位
                    if idx not in tool_calls_buffer:
                        tool_calls_buffer[idx] = {"id": "", "name": "", "args": ""}
                    
                    # 拼接 ID（可能分多次传输）
                    if tc.id:
                        tool_calls_buffer[idx]["id"] += tc.id
                    
                    # 拼接函数名
                    if tc.function.name:
                        tool_calls_buffer[idx]["name"] += tc.function.name
                        
                    # 拼接参数（JSON 字符串，可能分多次传输）
                    if tc.function.arguments:
                        tool_calls_buffer[idx]["args"] += tc.function.arguments

        # === 流结束：组装完整的 Message 对象 ===
        # 将缓冲区中的工具调用转换为标准格式
        assembled_tool_calls = []
        if tool_calls_buffer:
            # 按 index 排序，确保顺序正确
            for idx in sorted(tool_calls_buffer.keys()):
                data = tool_calls_buffer[idx]
                assembled_tool_calls.append({
                    "id": data["id"],
                    "type": "function",
                    "function": {
                        "name": data["name"],
                        "arguments": data["args"] 
                    }
                })
        
        # 构建完整消息
        full_message = {
            "role": "assistant",
            "reasoning_content": reasoning_content if reasoning_content else None,
            "content": final_content if final_content else None,
            "tool_calls": assembled_tool_calls if assembled_tool_calls else None
        }
        
        # yield 完整消息，带上特殊标记
        yield {"type": "full_message", "content": full_message}


class AgentRuntime:
    """
    Agent 运行时 - 核心循环（Planner / Loop）。
    
    这是整个 Agent 系统的核心，负责协调所有组件工作。
    
    主要职责：
    1. 管理对话上下文
    2. 发送请求到 LLM
    3. 解析响应并执行工具
    4. 处理工具返回结果
    5. 循环执行直到任务完成
    
    属性:
        transport (LLMTransport): LLM 传输层
        executor (ToolExecutor): 工具执行器
        context (ContextManager): 上下文管理器
        logger: 日志记录器
        max_steps (int): 最大循环次数，防止死循环
        tool_context (ToolContext): 工具执行上下文
    
    工作流程：
        用户输入 → 添加到上下文 → 发送到 LLM → 解析响应
        → 如果有工具调用 → 执行工具 → 添加结果到上下文 → 重复
        → 如果没有工具调用 → 任务完成
    """
    
    def __init__(self, transport: LLMTransport, executor: ToolExecutor, 
                 skills_manager=None, logger=None, env: str = "cli", autosave_file: str = None):
        """
        初始化 Agent 运行时。
        
        参数:
            transport (LLMTransport): LLM 传输层实例
            executor (ToolExecutor): 工具执行器实例
            skills_manager: 技能管理器实例
            logger: 日志记录器实例
            env (str): 运行环境，"cli" 或 "web"
            autosave_file (str): 自动保存的文件路径
        """
        # 保存传���层和执行器的引用
        self.transport = transport
        self.executor = executor
        
        # 初始化上下文管理器
        self.context = ContextManager(
            skills_manager=skills_manager, 
            logger=logger, 
            autosave_file=autosave_file
        )
        
        self.logger = logger
        self.max_steps = 100  # 最大循环次数，防止死循环
        
        # 初始化工具上下文
        # 工具上下文包含执行工具所需的所有信息
        self.tool_context = ToolContext(
            workspace_root=Path(os.getcwd()),  # 当前工作目录
            skills_manager=skills_manager,      # 技能管理器
            env=env                             # 运行环境
        )

    def _robust_json_parse(self, args_str: str) -> dict:
        """
        鲁棒的 JSON 解析方法。
        
        尝试解析 JSON 参数，即使格式错误或被截断也能尝试修复。
        这是因为 LLM 有时会生成不完整的 JSON。
        
        参数:
            args_str (str): JSON 字符串
        
        返回:
            dict: 解析后的字典
        
        处理策略：
        1. 清理 Markdown 代码块标记
        2. 尝试直接解析
        3. 尝试补全缺失的引号和括号
        4. 全部失败则抛出异常
        """
        # 步骤 1: 清理可能存在的 Markdown 代码块标记
        # LLM 有时会返回 ```json ... ``` 格式
        clean_str = args_str.strip()
        
        if not clean_str:
            return {}
            
        if clean_str.startswith("```"):
            lines = clean_str.splitlines()
            # 移除开头的 ```json 或 ```
            if lines[0].startswith("```"):
                lines = lines[1:]
            # 移除结尾的 ```
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean_str = "\n".join(lines).strip()
            
        # 步骤 2: 尝试直接解析
        try:
            return json.loads(clean_str)
        except json.JSONDecodeError:
            pass  # 继续尝试修复
            
        # 步骤 3: 尝试简单的截断修复
        # 补充缺失的引号或括号
        attempts = [
            clean_str + '"',    # 补全末尾引号
            clean_str + '"}',   # 补全末尾引号和花括号
            clean_str + '}',    # 补全末尾花括号
            clean_str + '"]',   # 补全列表末尾
            clean_str + ']'     # 补全列表括号
        ]
        
        for attempt in attempts:
            try:
                return json.loads(attempt)
            except json.JSONDecodeError:
                continue
                
        # 步骤 4: 全部失败，重新抛出原始错误
        # 让外层捕获并处理
        return json.loads(clean_str)

    async def step(self, user_input: str):
        """
        执行一步对话循环。
        
        这是一个异步生成器函数，yield 各种事件供 CLI 或 Web 使用。
        
        参数:
            user_input (str): 用户输入的消息
        
        Yields:
            dict: 事件字典，类型包括：
                - thinking_delta: 思考过程增量
                - content_delta: 文本内容增量
                - tool_call: 工具调用开始
                - tool_output: 工具执行结果
                - interrupt: 需要用户输入
                - finished: 任务完成
                - error: 发生错误
        
        工作流程：
        1. 添加用户消息到上下文
        2. 发送请求到 LLM
        3. 解析流式响应
        4. 如果有工具调用，执行工具
        5. 添加工具结果到上下文
        6. 重复步骤 2-5，直到没有工具调用
        """
        # 添加用户消息到上下文
        self.context.add_user_msg(user_input)
        
        # 创建流式解析器
        interpreter = StreamInterpreter()
        
        # 当前步数计数器
        current_step = 0
        
        # 主循环：最多执行 max_steps 步
        while current_step < self.max_steps:
            # 准备发送的消息
            messages_to_send = list(self.context.history)
            
            # 如果有 TODO 列表，注入到上下文中
            # 这让 AI 知道当前的任务进度
            # 如果有 TODO 列表，注入到上下文中
            # 这让 AI 知道当前的任务进度
            if self.tool_context.todo_state:
                # 将结构化的 todo 状态转换为 JSON 字符串
                todo_json = json.dumps(self.tool_context.todo_state, ensure_ascii=False, indent=2)
                # print(f"\n[DEBUG] Current Context Todos: {todo_json}")
                
                system_injection = {
                    "role": "system", 
                    "content": f"""## Current Todo List Status (JSON)

{todo_json}

CRITICAL INSTRUCTION: 
1. **PRIORITY 1**: Check for any task with status **"in_progress"**.
   - **IF FOUND**: This is your current focus.
     - **CHECK LAST OUTPUT**: Did the previous command succeed?
       - **YES**: Call `update_todo(id=..., status="completed")`.
       - **NO/FAILED**: Retry execution OR call `update_todo(id=..., status="failed")`.
   - **Do NOT** start a new task while one is "in_progress".

2. **PRIORITY 2**: If no "in_progress" tasks, find the *FIRST* task with status **"pending"**.
   - **ACTION**: 
     - 1. Call `update_todo(id=..., status="in_progress")`.
     - 2. **IN THE SAME TURN**: Execute the task's command/action.

3. Use `write_todo` ONLY for refactoring the full list. Use `update_todo` for status updates."""
                }
                messages_to_send.append(system_injection)

            # 步骤 1: 发起流式请求
            stream = await self.transport.send_stream_request(
                messages_to_send, 
                self.executor.get_definitions()
            )
            
            # 步骤 2: 从解析器获取流事件
            full_message = None
            
            # 代理 interpreter 的事件
            async for event in interpreter.parse_stream(stream):
                if event["type"] == "full_message":
                    # 完整消息，保存起来后续处理
                    full_message = event["content"]
                else:
                    # 其他事件直接 yield 给调用者
                    yield event

            # 检查是否收到有效响应
            if not full_message:
                yield {"type": "error", "content": "Encountered empty response from LLM"}
                break

            # 步骤 3: 记录日志
            if self.logger:
                if full_message.get("reasoning_content"):
                    self.logger.log_thinking(full_message.get("reasoning_content"))
            
            # 准备保存的消息
            # 保留 reasoning_content 给前端历史记录查看
            msg_to_save = full_message.copy()

            # 空响应检查
            has_content = bool(msg_to_save.get("content"))
            has_tools = bool(msg_to_save.get("tool_calls"))
            has_reasoning = bool(msg_to_save.get("reasoning_content"))

            # 如果响应完全为空，结束循环
            if not has_content and not has_tools and not has_reasoning:
                print("   ⚠️  [Runtime] Empty response detected. Stopping turn.")
                yield {"type": "finished", "content": "Done"}
                break
            
            # 如果只有思考内容，可能是模型提前停止
            if not has_content and not has_tools and has_reasoning:
                print("   ⚠️  [Runtime] Response only contained reasoning content. Model might have stopped early.")
                msg_to_save["content"] = "(Model stopped after thinking)"
                
            # 添加助手消息到上下文
            self.context.add_assistant_msg(msg_to_save)
            
            # 步骤 4: 检查并执行工具
            tool_calls = full_message.get("tool_calls")
            if tool_calls:
                # 遍历所有工具调用
                for tc in tool_calls:
                    # 提取工具信息
                    func_name = tc['function']['name']
                    args_str = tc['function']['arguments']
                    tool_call_id = tc['id']
                    
                    # 通知外部正在调用工具
                    yield {"type": "tool_call", "content": {"name": func_name, "args": args_str, "id": tool_call_id}}

                    try:
                        # 使用鲁棒的 JSON 解析
                        args = self._robust_json_parse(args_str)
                        
                        # 执行工具
                        result_obj = await self.executor.execute(func_name, args, self.tool_context)
                        
                    except json.JSONDecodeError:
                        # JSON 解析失败
                        result_obj = f"Error: Invalid JSON arguments generated: {args_str}. Please verify the JSON format."
                    except Exception as e:
                        # 其他执行错误
                        result_obj = f"Error: {str(e)}"

                    # 处理结果
                    # 结果可能是 ToolResult 对象或字符串
                    output_str = str(result_obj)
                    if isinstance(result_obj, ToolResult):
                        output_str = result_obj.output
                    
                    # 添加工具输出到上下文
                    self.context.add_tool_output(tool_call_id, output_str)
                    
                    # 通知外部工具执行结果
                    yield {"type": "tool_output", "content": {"id": tool_call_id, "output": output_str}}

                    # === 中断检查 ===
                    # 如果工具返回需要用户输入，暂停执行
                    if isinstance(result_obj, ToolResult) and result_obj.data and result_obj.data.get("action") == "ask_user":
                        yield {"type": "interrupt", "content": result_obj.data}
                        return  # 停止执行循环，等待用户输入

                    # === 特殊处理: attempt_completion ===
                    # 如果是 attempt_completion，任务完成
                    if func_name == "attempt_completion":
                        yield {"type": "finished", "content": output_str}
                        return

                # 当前步骤的工具调用完成，增加步数
                current_step += 1
            else:
                # 没有工具调用，任务完成
                yield {"type": "finished", "content": "Done"}
                break


# =============================================================================
# Layer 1: IDE / UI Layer (CLI 实现)
# =============================================================================
# 这一层是用户界面，负责与用户交互
# =============================================================================

class CLI:
    """
    命令行界面 - 提供终端交互体验。
    
    这个类实现了 Agent 的命令行界面，包括：
    - 用户输入处理
    - 事件渲染（思考过程、文本、工具调用等）
    - 彩色输出
    
    属性:
        runtime (AgentRuntime): Agent 运行时实例
        last_event_type (str): 上一个事件类型，用于控制换行
    """
    
    def __init__(self, runtime: AgentRuntime):
        """
        初始化 CLI。
        
        参数:
            runtime (AgentRuntime): Agent 运行时实例
        """
        self.runtime = runtime
        # 用于控制换行美观的状态标记
        self.last_event_type = None 

    async def run(self):
        """
        运行 CLI 主循环。
        
        这是一个无限循环，不断：
        1. 等待用户输入
        2. 发送给 Runtime 处理
        3. 渲染返回的事件
        4. 直到用户输入 exit/quit
        """
        # 打印欢迎信息
        print("┌──────────────────────────┐")
        print("│   Agent System Online    │")
        print("└──────────────────────────┘")
        
        # 主循环
        while True:
            try:
                # 等待用户输入
                user_input = input("\n[User]: ").strip()
                
                # 跳过空输入
                if not user_input:
                    continue

                # 检查退出命令
                if user_input.lower() in ["exit", "quit"]:
                    break
                
                print("│")
                
                # 重置状态标记
                self.last_event_type = None 
                
                # 调用 Runtime 处理用户输入
                # async for 会逐步获取 Runtime yield 的事件
                async for event in self.runtime.step(user_input):
                    self.render_event(event)
                    
                print("")  # 结束后的换行
                    
            except KeyboardInterrupt:
                # Ctrl+C 退出
                break
    
    def render_event(self, event):
        """
        渲染事件到终端。
        
        参数:
            event (dict): 事件字典，包含 type 和 content
        
        支持的事件类型：
        - thinking_delta: 黄色思考过程
        - content_delta: 绿色正文
        - tool_call: 工具调用信息
        - tool_output: 工具输出（截断显示）
        - finished: 完成信息
        - error: 错误信息（红色）
        """
        etype = event["type"]
        content = event["content"]
        
        if etype == "thinking_delta":
            # 黄色思考过程（ANSI 转义码 \033[93m）
            print(f"\033[93m{content}\033[0m", end="", flush=True)
            self.last_event_type = "thinking"
            
        elif etype == "content_delta":
            # 绿色正文（ANSI 转义码 \033[92m）
            # 如果之前是思考，先换行分隔
            if self.last_event_type == "thinking":
                print("\n\n", end="", flush=True)
                self.last_event_type = "content"
            print(f"\033[92m{content}\033[0m", end="", flush=True)
            
        elif etype == "tool_call":
            # 工具调用信息
            print(f"\n\n⚙️  [Tool Call]: {content['name']} ({content['args']})")
            self.last_event_type = "tool"
            
        elif etype == "tool_output":
            # 工具输出（截断过长的输出）
            out_str = content['output']
            if len(out_str) > 200:
                out_str = out_str[:200] + "..."
            print(f"   └──> [Output]: {out_str}")
            
        elif etype == "finished":
            # 完成信息
            print(f"\n\033[92m[Finished]: {content}\033[0m")
            
        elif etype == "error":
            # 错误信息（红色）
            print(f"\n\033[91m[Error]: {content}\033[0m")


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


# =============================================================================
# 主程序入口
# =============================================================================


if __name__ == "__main__":
    # 从 .env 文件加载环境变量
    # .env 文件包含 API 密钥等敏感配置
    load_dotenv()
    
    # 读取配置
    api_key = os.getenv("OPENAI_API_KEY")      # API 密钥
    base_url = os.getenv("OPENAI_BASE_URL")    # API 基础 URL
    model = os.getenv("OPENAI_MODEL", "Qwen/Qwen3-235B-A22B-Thinking-2507")  # 模型名称
    
    # 步骤 1: 初始化传输层
    # 传输层负责与 LLM API 通信
    transport = LLMTransport(api_key=api_key, base_url=base_url, model=model)
    
    # 步骤 2: 初始化技能系统
    # 技能系统提供可扩展的任务能力
    skills_root = Path(".skills")              # 技能文件目录
    # skills_loader = SkillsLoader(skills_root)  # 技能加载器
    skills_manager = SkillsManager(skills_root)  # 技能管理器
    skills_manager.load_skills()  # 加载所有技能
    
    # 步骤 3: 初始化工具执行器
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
    # --- Todo 工具 ---
    from agent_tools.todo import read_todo, ReadTodoArgs, write_todo, WriteTodoArgs, update_todo, UpdateTodoArgs
    executor.register(read_todo, ReadTodoArgs)
    executor.register(write_todo, WriteTodoArgs)
    executor.register(update_todo, UpdateTodoArgs)
    
    
    # 步骤 4: 初始化核心运行时
    logger = ConversationLogger()  # 对话日志记录器
    runtime = AgentRuntime(
        transport, 
        executor, 
        skills_manager=skills_manager, 
        logger=logger
    )

    # 步骤 5: 初始化 MCP 服务器
    # 注意：这里需要运行异步函数，但 asyncio.run 只能运行一个顶层入口
    # 所以我们在 app.run() 中处理，或者在这里使用 loop.run_until_complete
    # 但由于 app.run() 也是异步的，我们可以把 init 放在 app.run() 之前
    # 或者修改 CLI.run 为接受一个初始化回调
    
    # 简单方案：在这里运行初始化
    # 注意：mcp client 需要保持运行，init_mcp_servers 会启动连接
    # 我们需要确保 runtime 保持对 client 的引用
    async def bootstrap():
        await init_mcp_servers(runtime)
        app = CLI(runtime)
        await app.run()

    asyncio.run(bootstrap())

