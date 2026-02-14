import os
import json
import time
import inspect
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel,Field
from typing import Dict, Any, Callable, Type, List, Generator, Union
from openai import AsyncOpenAI, DefaultHttpxClient
import httpx
# Import tools
from agent_tools.base import ToolContext, ToolResult
from agent_tools.io import (
    list_files, ListFilesArgs,
    read_file, ReadFileArgs,
    write_to_file, WriteToFileArgs,
    delete_file, DeleteFileArgs,
    search_files, SearchFilesArgs,
    edit_file, EditFileArgs
)
from agent_tools.system import execute_command, ExecuteCommandArgs
from agent_tools.browser import browser_action, BrowserActionArgs
from agent_tools.diff import apply_diff, ApplyDiffArgs
from agent_tools.interaction import (
    ask_followup_question, AskFollowupQuestionArgs,
    attempt_completion, AttemptCompletionArgs,
    new_task, NewTaskArgs,
    switch_mode, SwitchModeArgs,
    update_todo_list, UpdateTodoListArgs,
    fetch_instructions, FetchInstructionsArgs
)
from agent_tools.skills import (
    list_skills, ListSkillsArgs,
    search_skills, SearchSkillsArgs,
    get_skill, GetSkillArgs
)
from agent_tools.skills_loader import SkillsLoader
from agent_tools.skills_manager import SkillsManager
from log.logger import ConversationLogger

# ==========================================
# Layer 4: LLM Transport (负责与模型通讯)
# ==========================================
def generate_openai_schema(func: Callable, args_model: Type[BaseModel]) -> dict:
    """
    自动将 函数 + Pydantic类 转换为 OpenAI 要求的 Schema 格式
    """
    # 1. 获取 Pydantic 原生 schema
    raw_schema = args_model.model_json_schema()
    
    # 2. 清理 Pydantic 特有的字段 (OpenAI 不需要 'title' 等字段)
    if "title" in raw_schema:
        del raw_schema["title"]
    
    # 3. 组装成 OpenAI Function 格式
    
    return {
        "type": "function",
        "function": {
            "name": func.__name__,           # 自动取函数名
            "description": func.__doc__ or "", # 自动取函数的 docstring
            "parameters": raw_schema         # 参数定义直接用 Pydantic 生成的
        }
    }



class LLMTransport:
    
    def __init__(self, api_key: str, base_url: str, model: str = "Qwen/Qwen3-235B-A22B-Thinking-2507"):
        http_client = httpx.AsyncClient(verify=False)
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=http_client
        )
        self.model = model
    

    async def send_stream_request(self, messages: List[Dict], tools: List[Dict] = None):
        """返回一个异步生成器(Async Generator)，逐步产出 Chunk"""
        # 安全过滤：移除 reasoning_content 字段，防止 API 报错
        # sanitized_messages = []
        # raw_len = 0
        # sanitized_len = 0
        
        # for msg in messages:
        #     raw_len += len(str(msg))
        #     msg_copy = msg.copy()
        #     if "reasoning_content" in msg_copy:
        #         del msg_copy["reasoning_content"]
        #     sanitized_messages.append(msg_copy)
        #     sanitized_len += len(str(msg_copy))

        # print(f"[Token Optimization] Original Context Size: {raw_len} chars -> Sanitized: {sanitized_len} chars. (Thinking content stripped from context)")

        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto" if tools else None,
                temperature=0,
                stream=True  # <--- 关键点：开启流
            )
            return stream
        except Exception as e:
            print(f"[Transport Error]: {e}")
            return None

# ==========================================
# Layer 3: Agent Runtime Core (核心大脑: 上下文+规划+工具)
# ==========================================
class ContextManager:
    """管理对话历史"""
    def __init__(self, skills_manager=None, logger=None, autosave_file: str = None):
        workspace = os.getcwd()
        self.skills_manager = skills_manager
        self.logger = logger
        self.autosave_file = autosave_file
        
        # 构建系统提示词（包含技能元信息摘要）
        system_prompt = self._build_system_prompt(workspace)
        
        self.history: List[Dict] = [
            {"role": "system", "content": system_prompt}
        ]


    def add_user_msg(self, content: str):
        user_msg = {"role": "user", "content": content}
        if self.logger:
            self.logger.log_user(user_msg)
        self.history.append(user_msg)
        if self.autosave_file:
            self.save_history(self.autosave_file)

    def add_assistant_msg(self, message: Any):
        if self.logger:
            self.logger.log_assistant(str(message))
        self.history.append(message)
        if self.autosave_file:
            self.save_history(self.autosave_file)

    def add_tool_output(self, tool_call_id: str, content: str):
        tool_output = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content
        }
        if self.logger:
            self.logger.log_tool(tool_call_id, tool_output)
        self.history.append(tool_output)
        if self.autosave_file:
            self.save_history(self.autosave_file)

    def save_history(self, filepath: str):
        """Save current history to a JSON file."""
        import json
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)

    def load_history(self, filepath: str):
        """Load history from a JSON file, keeping the current System Prompt (index 0)."""
        import json
        with open(filepath, 'r', encoding='utf-8') as f:
            loaded_history = json.load(f)
        
        if not loaded_history:
            return

        # Preserve the current system prompt (self.history[0]) 
        # and replace the rest with the loaded history (skipping its system prompt if present)
        current_system = self.history[0]
        
        # Check if loaded history has system prompt at index 0
        start_idx = 0
        if loaded_history[0].get("role") == "system":
            start_idx = 1
            
        self.history = [current_system] + loaded_history[start_idx:]

    def reset(self):
        """Reset history to just the system prompt."""
        workspace = os.getcwd() # Re-evaluate workspace if needed
        # Or just keep current system prompt structure but refresh content?
        # For simplicity, we keep the *instantiated* logic or just reset to index 0 if it was dynamic
        # But _build_system_prompt was called in init. 
        # Let's just keep the 0-th element if we assume it's the system prompt.
        if self.history:
              self.history = [self.history[0]]
        else:
              # Should not happen unless manually cleared, but safe fallback
              system_prompt = self._build_system_prompt(workspace)
              self.history = [{"role": "system", "content": system_prompt}]


    
    def _build_system_prompt(self, workspace: str) -> str:
        """构建系统提示词，包含技能元信息摘要"""
        base_prompt = f"""You are  Code, a highly skilled software engineer with extensive knowledge in many programming languages, frameworks, design patterns, and best practices.\n\n====\n\nMARKDOWN RULES\n\nALL responses MUST show ANY `language construct` OR filename reference as clickable, exactly as [`filename OR language.declaration()`](relative/file/path.ext:line); line is required for `syntax` and optional for filename links. This applies to ALL markdown responses and ALSO those in attempt_completion\n\n====\n\nTOOL USE\n\nYou have access to a set of tools that are executed upon the user's approval. Use the provider-native tool-calling mechanism. Do not include XML markup or examples. **CRITICAL RULES:**
1. **You must use EXACTLY ONE tool call per assistant response.** 
2. **Do NOT call zero tools.** If you think the task is done, you MUST use the `attempt_completion` tool.
3. **Do NOT return a final answer as plain text.** You must encapsulate your final response in the `attempt_completion` tool arguments.
4. **Do NOT output conversational text without a tool call.**\n\n# Tool Use Guidelines\n\n1. Assess what information you already have and what information you need to proceed with the task.\n2. Choose the most appropriate tool based on the task and tool descriptions provided. Assess if you need additional information to proceed, and which of the available tools would be most effective for gathering this information. For example using the list_files tool is more effective than running a command like `ls` in the terminal. It's critical that you think about each available tool and use the one that best fits the current step in the task.\n3. If multiple actions are needed, use one tool at a time per message to accomplish the task iteratively, with each tool use being informed by the result of the previous tool use. Do not assume the outcome of any tool use. Each step must be informed by the previous step's result.\n4. After each tool use, the user will respond with the result of that tool use. This result will provide you with the necessary information to continue your task or make further decisions. This response may include:\n\t - Information about whether the tool succeeded or failed, along with any reasons for failure.\n\t - Linter errors that may have arisen from the changes you made, which you'll need to address.\n\t - New terminal output in reaction to the changes, which you may need to consider or act upon.\n\t - Any other relevant feedback or information related to the tool use.\n\nBy carefully considering the user's response after tool executions, you can react accordingly and make informed decisions about how to proceed with the task. This iterative process helps ensure the overall success and accuracy of your work.\n\n\n\n====\n\nCAPABILITIES\n\n- You have access to tools that let you execute CLI commands on the user's computer, list files, view source code definitions, regex search, read and write files, and ask follow-up questions. These tools help you effectively accomplish a wide range of tasks, such as writing code, making edits or improvements to existing files, understanding the current state of a project, performing system operations, and much more.\n- When the user initially gives you a task, a recursive list of all filepaths in the current workspace directory ({workspace}) will be included in environment_details. This provides an overview of the project's file structure, offering key insights into the project from directory/file names (how developers conceptualize and organize their code) and file extensions (the language used). This can also guide decision-making on which files to explore further. If you need to further explore directories such as outside the current workspace directory, you can use the list_files tool. If you pass 'true' for the recursive parameter, it will list files recursively. Otherwise, it will list files at the top level, which is better suited for generic directories where you don't necessarily need the nested structure, like the Desktop.\n- You can use the execute_command tool to run commands on the user's computer whenever you feel it can help accomplish the user's task. When you need to execute a CLI command, you must provide a clear explanation of what the command does. Prefer to execute complex CLI commands over creating executable scripts, since they are more flexible and easier to run. Interactive and long-running commands are allowed, since the commands are run in the user's VSCode terminal. The user may keep commands running in the background and you will be kept updated on their status along the way. Each command you execute is run in a new terminal instance.\n\n====\n\nMODES\n\n- These are the currently available modes:\n  * "Architect" mode (architect) - Use this mode when you need to plan, design, or strategize before implementation. Perfect for breaking down complex problems, creating technical specifications, designing system architecture, or brainstorming solutions before coding.\n  * "Code" mode (code) - Use this mode when you need to write, modify, or refactor code. Ideal for implementing features, fixing bugs, creating new files, or making code improvements across any programming language or framework.\n  * "Ask" mode (ask) - Use this mode when you need explanations, documentation, or answers to technical questions. Best for understanding concepts, analyzing existing code, getting recommendations, or learning about technologies without making changes.\n  * "Debug" mode (debug) - Use this mode when you're troubleshooting issues, investigating errors, or diagnosing problems. Specialized in systematic debugging, adding logging, analyzing stack traces, and identifying root causes before applying fixes.\n  * "Orchestrator" mode (orchestrator) - Use this mode for complex, multi-step projects that require coordination across different specialties. Ideal when you need to break down large tasks into subtasks, manage workflows, or coordinate work that spans multiple domains or expertise areas.\nIf the user asks you to create or edit a new mode for this project, you should read the instructions by using the fetch_instructions tool, like this:\n<fetch_instructions>\n<task>create_mode</task>\n</fetch_instructions>\n\n\n====\n\nRULES\n\n- The project base directory is: {workspace}\n- All file paths must be relative to this directory. However, commands may change directories in terminals, so respect working directory specified by the response to execute_command.\n- You cannot `cd` into a different directory to complete a task. You are stuck operating from '{workspace}', so be sure to pass in the correct 'path' parameter when using tools that require a path.\n- Do not use the ~ character or $HOME to refer to the home directory.\n- Before using the execute_command tool, you must first think about the SYSTEM INFORMATION context provided to understand the user's environment and tailor your commands to ensure they are compatible with their system. You must also consider if the command you need to run should be executed in a specific directory outside of the current working directory '{workspace}', and if so prepend with `cd`'ing into that directory && then executing the command (as one command since you are stuck operating from '{workspace}'). For example, if you needed to run `npm install` in a project outside of '{workspace}', you would need to prepend with a `cd` i.e. pseudocode for this would be `cd (path to project) && (command, in this case npm install)`.\n\n- Some modes have restrictions on which files they can edit. If you attempt to edit a restricted file, the operation will be rejected with a FileRestrictionError that will specify which file patterns are allowed for the current mode.\n- Be sure to consider the type of project (e.g. Python, JavaScript, web application) when determining the appropriate structure and files to include. Also consider what files may be most relevant to accomplishing the task, for example looking at a project's manifest file would help you understand the project's dependencies, which you could incorporate into any code you write.\n  * For example, in architect mode trying to edit app.js would be rejected because architect mode can only edit files matching "\\\.md$"\n- When making changes to code, always consider the context in which the code is being used. Ensure that your changes are compatible with the existing codebase and that they follow the project's coding standards and best practices.\n- Do not ask for more information than necessary. Use the tools provided to accomplish your user's request efficiently and effectively. When you've completed your user's task, you must use the attempt_completion tool to present the result of the task to the user. The user may provide feedback, which you can use to make improvements and try again.\n- You are only allowed to ask the user questions using the ask_followup_question tool. Use this tool only when you need additional details to complete a task, and be sure to provide a clear and concise question that will help you move forward with the task. When you ask a question, provide the user with 2-4 suggested answers based on your question so they don't need to do so much typing. The suggestions should be specific, actionable, and directly related to the completed task. They should be ordered by priority or logical sequence. However if you can use the available tools to avoid having to ask the user questions, you should do so. For example, if the user mentions a file that may be in an outside directory like the Desktop, you should use the list_files tool to list the files in the Desktop and check if the file they are talking about is there, rather than asking the user to provide the file path themselves.\n- When executing commands, if you don't see the expected output, assume the terminal executed the command successfully and proceed with the task. The user's terminal may be unable to stream the output back properly. If you absolutely need to see the actual terminal output, use the ask_followup_question tool to request the user to copy and paste it back to you.\n- The user may provide a file's contents directly in their message, in which case you shouldn't use the read_file tool to get the file contents again since you already have it.\n- Your goal is to try to accomplish the user's task, NOT engage in a back and forth conversation.\n- NEVER end attempt_completion result with a question or request to engage in further conversation! Formulate the end of your result in a way that is final and does not require further input from the user.\n- You are STRICTLY FORBIDDEN from starting your messages with "Great", "Certainly", "Okay", "Sure". You should NOT be conversational in your responses, but rather direct and to the point. For example you should NOT say "Great, I've updated the CSS" but instead something like "I've updated the CSS". It is important you be clear and technical in your messages.\n- When presented with images, utilize your vision capabilities to thoroughly examine them and extract meaningful information. Incorporate these insights into your thought process as you accomplish the user's task.\n- At the end of each user message, you will automatically receive environment_details. This information is not written by the user themselves, but is auto-generated to provide potentially relevant context about the project structure and environment. While this information can be valuable for understanding the project context, do not treat it as an explicit part of the user's request or response. Use it to inform your actions and decisions, but don't assume the user is explicitly asking about or referring to this information unless they clearly do so in their message. When using environment_details, explain your actions clearly to ensure the user understands, as they may not be aware of these details.\n- Before executing commands, check the "Actively Running Terminals" section in environment_details. If present, consider how these active processes might impact your task. For example, if a local development server is already running, you wouldn't need to start it again. If no active terminals are listed, proceed with command execution as normal.\n- MCP operations should be used one at a time, similar to other tool usage. Wait for confirmation of success before proceeding with additional operations.\n- It is critical you wait for the user's response after each tool use, in order to confirm the success of the tool use. For example, if asked to make a todo app, you would create a file, wait for the user's response it was created successfully, then create another file if needed, wait for the user's response it was created successfully, etc.\n\n====\n\nSYSTEM INFORMATION\n\nOperating System: Windows Server 2016\nDefault Shell: C:\\Windows\\system32\\cmd.exe\nHome Directory: C:/Users/xsc\nCurrent Workspace Directory: {workspace}\n\nThe Current Workspace Directory is the active VS Code project directory, and is therefore the default directory for all tool operations. New terminals will be created in the current workspace directory, however if you change directories in a terminal it will then have a different working directory; changing directories in a terminal does not modify the workspace directory, because you do not have access to change the workspace directory. When the user initially gives you a task, a recursive list of all filepaths in the current workspace directory ('/test/path') will be included in environment_details. This provides an overview of the project's file structure, offering key insights into the project from directory/file names (how developers conceptualize and organize their code) and file extensions (the language used). This can also guide decision-making on which files to explore further. If you need to further explore directories such as outside the current workspace directory, you can use the list_files tool. If you pass 'true' for the recursive parameter, it will list files recursively. Otherwise, it will list files at the top level, which is better suited for generic directories where you don't necessarily need the nested structure, like the Desktop.\n\n====\n\nOBJECTIVE\n\nYou accomplish a given task iteratively, breaking it down into clear steps and working through them methodically.\n\n1. Analyze the user's task and set clear, achievable goals to accomplish it. Prioritize these goals in a logical order.\n2. Work through these goals sequentially, utilizing available tools one at a time as necessary. Each goal should correspond to a distinct step in your problem-solving process. You will be informed on the work completed and what's remaining as you go.\n3. Remember, you have extensive capabilities with access to a wide range of tools that can be used in powerful and clever ways as necessary to accomplish each goal. Before calling a tool, do some analysis. First, analyze the file structure provided in environment_details to gain context and insights for proceeding effectively. Next, think about which of the provided tools is the most relevant tool to accomplish the user's task. Go through each of the required parameters of the relevant tool and determine if the user has directly provided or given enough information to infer a value. When deciding if the parameter can be inferred, carefully consider all the context to see if it supports a specific value. If all of the required parameters are present or can be reasonably inferred, proceed with the tool use. BUT, if one of the values for a required parameter is missing, DO NOT invoke the tool (not even with fillers for the missing params) and instead, ask the user to provide the missing parameters using the ask_followup_question tool. DO NOT ask for more information on optional parameters if it is not provided.\n4. Once you've completed the user's task, you must use the attempt_completion tool to present the result of the task to the user.\n5. The user may provide feedback, which you can use to make improvements and try again. But DO NOT continue in pointless back and forth conversations, i.e. don't end your results with questions or offers for further assistance.\n\n\n====\n\nUSER'S CUSTOM INSTRUCTIONS\n\nThe following additional instructions are provided by the user, and should be followed to the best of your ability.\n\nLanguage Preference:\nYou should always speak and think in the "English" (en) language unless the user gives you instructions below to do otherwise.\n\nRules:\n\n# Agent Rules Standard (AGENTS.md):\n# AGENTS.md\n\n"""
        
        # 如果有 skills manager，添加技能元信息摘要（轻量级）
        if self.skills_manager:
            skills_summary = self.skills_manager.get_metadata_summary()
            base_prompt += f"""\n\n## Available Skills\n\nThe following skills are available to assist with specific tasks:\n\n{skills_summary}\n\nWhen a task matches a skill's description, you can use the `get_skill` tool to retrieve the full skill content and follow its instructions.\n"""
        
        return base_prompt

class ToolExecutor:
    def __init__(self):
        # 存储执行逻辑: { "name": (func, args_model) }
        self._execution_map: Dict[str, tuple] = {}
        
        # 存储对外定义: [ schema1, schema2, ... ]
        self._schemas: List[dict] = []

    def register(self, func: Callable, args_model: Type[BaseModel]):
        """
        一次注册，搞定所有（执行逻辑 + Schema定义）
        """
        name = func.__name__
        
        # 1. 存入执行表
        self._execution_map[name] = (func, args_model)
        
        # 2. 自动生成并存入 Schema 列表
        schema = generate_openai_schema(func, args_model)
        self._schemas.append(schema)
        
        print(f"[INFO] 工具 [{name}] 已注册 (Schema 已自动生成)")

    # --- 给 LLM 看的方法 ---
    def get_definitions(self) -> List[dict]:
        """直接传给 OpenAI 的 tools 参数"""
        return self._schemas

    # --- 给后端执行用的方法 ---
    async def execute(self, name: str, raw_args: dict, ctx: ToolContext) -> Any:
        if name not in self._execution_map:
            return f"Error: Tool {name} not found"
            
        func, args_model = self._execution_map[name]
        try:
            # 自动转换 + 执行
            args_instance = args_model(**raw_args)
            # 传入 ToolContext
            if inspect.iscoroutinefunction(func):
                 result = await func(ctx, args_instance)
            else:
                 result = func(ctx, args_instance)
                 
            # 统一处理 ToolResult -> 现在由 Runtime 处理
            # if isinstance(result, ToolResult):
            #     return result.output
            return result
        except Exception as e:
            return f"Error executing {name}: {str(e)}"

class StreamInterpreter:
    """
    流式解析器：
    1. 实时 yield 事件给 Runtime (UI/Web)
    2. 默默拼接工具调用的参数
    3. 流结束后，返回完整的 Message 对象供 Runtime 存储
    """
    async def parse_stream(self, stream_generator):
        # 累加器状态
        final_content = ""
        reasoning_content = ""
        tool_calls_buffer = {}  # index -> {id, name, args_str}

        # yield {"type": "stream_start", "content": ""}

        if not stream_generator:
             yield {"type": "error", "content": "Error: No stream"}
             return

        async for chunk in stream_generator:
            if not chunk.choices:
                continue
                
            delta = chunk.choices[0].delta
            # print(f"DEBUG: Chunk received: content={bool(delta.content)}, tools={bool(delta.tool_calls)}, thinking={bool(getattr(delta, 'reasoning_content', None))}")
            
            # === Case A: 处理思考过程 (DeepSeek/Qwen 等) ===
            if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                reasoning_content += delta.reasoning_content
                yield {"type": "thinking_delta", "content": delta.reasoning_content}

            # === Case B: 处理文本内容 (实时渲染) ===
            if delta.content:
                final_content += delta.content
                yield {"type": "content_delta", "content": delta.content}

            # === Case C: 处理工具调用 (累加拼接) ===
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    
                    # 初始化 buffer槽位
                    if idx not in tool_calls_buffer:
                        tool_calls_buffer[idx] = {"id": "", "name": "", "args": ""}
                    
                    # 拼接 ID
                    if tc.id:
                        tool_calls_buffer[idx]["id"] += tc.id
                    
                    # 拼接函数名
                    if tc.function.name:
                        tool_calls_buffer[idx]["name"] += tc.function.name
                        
                    # 拼接参数
                    if tc.function.arguments:
                        tool_calls_buffer[idx]["args"] += tc.function.arguments

        # ... (Stream finish logic stays same) ... 



        # === 流结束：组装完整的 Message 对象 ===
        assembled_tool_calls = []
        if tool_calls_buffer:
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
        
        # 返回完整消息作为最后一个 yield，带上特殊标记
        full_message = {
            "role": "assistant",
            "reasoning_content": reasoning_content if reasoning_content else None,
            "content": final_content if final_content else None,
            "tool_calls": assembled_tool_calls if assembled_tool_calls else None
        }
        
        yield {"type": "full_message", "content": full_message}


class AgentRuntime:
    """核心循环 (Planner / Loop)"""
    def __init__(self, transport: LLMTransport, executor: ToolExecutor, skills_manager=None, logger=None, env: str = "cli", autosave_file: str = None):
        self.transport = transport
        self.executor = executor
        self.context = ContextManager(skills_manager=skills_manager, logger=logger, autosave_file=autosave_file)
        self.logger = logger
        self.max_steps = 100  # 防止死循环
        
        # 初始化 ToolContext（包含 skills_manager）
        self.tool_context = ToolContext(
            workspace_root=Path(os.getcwd()),
            skills_manager=skills_manager,
            env=env
        )

    def _robust_json_parse(self, args_str: str) -> dict:
        """Attempt to parse JSON arguments even if malformed or truncated.
        (尝试解析 JSON 参数，即使格式错误或被截断)
        """
        # Clean up markdown code blocks if present
        # 1. 清理可能存在的 Markdown 代码块标记 (```json ... ```)
        clean_str = args_str.strip()
        if not clean_str:
             return {}
        if clean_str.startswith("```"):
            lines = clean_str.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean_str = "\n".join(lines).strip()
            
        try:
            return json.loads(clean_str)
        except json.JSONDecodeError:
            pass
            
        # Attempt simple repairs for truncation
        # 2. 尝试简单的截断修复 (补充缺失的引号或括号)
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
                
        # Re-raise original error if all repairs fail
        # 3. 如果所有尝试都失败，重新抛出原始错误，以便外层捕获
        return json.loads(clean_str)

    async def step(self, user_input: str):
        """
        生成器函数，yield 各种事件供 CLI 或 Web 使用
        事件类型: 
          - thinking_delta
          - content_delta
          - tool_call
          - tool_output
          - error
          - finished
        """
        self.context.add_user_msg(user_input)
        interpreter = StreamInterpreter()
        
        current_step = 0
        while current_step < self.max_steps:
            # 准备发送的消息
            messages_to_send = list(self.context.history)
            
            # 如果有 todo list，注入到上下文中
            if self.tool_context.todos:
                print(f"\n[DEBUG] Current Context Todos: {self.tool_context.todos}")
                todo_str = "\n".join(self.tool_context.todos)
                system_injection = {
                    "role": "system", 
                    "content": f"## Current Todo List Status\n\n{todo_str}\n\nCRITICAL INSTRUCTION: \n1. Identify the *FIRST* unchecked task (marked `[ ]`). \n2. **CHECK HISTORY**: Did you just finish this task's work (e.g., ran the command) in the last turn? \n   - **YES**: Do NOT do it again. Call `update_todo_list` IMMEDIATELY to mark it `[x]`. \n   - **NO**: Execute the task's work. Then, in the **SAME TURN**, call `update_todo_list` to mark it `[x]`.\n3. Do NOT use `[-]`. Only `[ ]` and `[x]`."
                }
                messages_to_send.append(system_injection)

            # 1. 发起流式请求
            stream = await self.transport.send_stream_request(
                messages_to_send, 
                self.executor.get_definitions()
            )
            
            # 2. 从解析器获取流事件
            full_message = None
            
            # 代理 interpreter 的事件
            async for event in interpreter.parse_stream(stream):
                if event["type"] == "full_message":
                    full_message = event["content"]
                else:
                    yield event

            if not full_message:
                yield {"type": "error", "content": "Encountered empty response from LLM"}
                break

            # 3. 记录日志和历史
            if self.logger:
                if full_message.get("reasoning_content"):
                     self.logger.log_thinking(full_message.get("reasoning_content"))
            
            # 不要删除 reasoning_content，保留给前端历史记录查看
            msg_to_save = full_message.copy()
            # if "reasoning_content" in msg_to_save:
            #     del msg_to_save["reasoning_content"]

            # 空响应检查
            has_content = bool(msg_to_save.get("content"))
            has_tools = bool(msg_to_save.get("tool_calls"))
            has_reasoning = bool(msg_to_save.get("reasoning_content"))

            if not has_content and not has_tools and not has_reasoning:
                print("   ⚠️  [Runtime] Empty response detected. Stopping turn.")
                yield {"type": "finished", "content": "Done"}
                break
            
            if not has_content and not has_tools and has_reasoning:
                print("   ⚠️  [Runtime] Response only contained reasoning content. Model might have stopped early.")
                # We save it anyway so the user sees the thought process
                msg_to_save["content"] = "(Model stopped after thinking)"
                
            self.context.add_assistant_msg(msg_to_save)
            
            # 4. 检查并执行工具
            tool_calls = full_message.get("tool_calls")
            if tool_calls:
                # yield {"type": "tool_calls_detected", "content": tool_calls}
                
                for tc in tool_calls:
                    func_name = tc['function']['name']
                    args_str = tc['function']['arguments']
                    tool_call_id = tc['id']
                    
                    # 通知外部正在调用工具
                    yield {"type": "tool_call", "content": {"name": func_name, "args": args_str, "id": tool_call_id}}

                    try:
                        # 使用鲁棒的 JSON 解析
                        args = self._robust_json_parse(args_str)
                        # Executing async now
                        result_obj = await self.executor.execute(func_name, args, self.tool_context)
                    except json.JSONDecodeError:
                        result_obj = f"Error: Invalid JSON arguments generated: {args_str}. Please verify the JSON format."
                    except Exception as e:
                         result_obj = f"Error: {str(e)}"

                    # Handle Result (String or ToolResult)
                    output_str = str(result_obj)
                    if isinstance(result_obj, ToolResult):
                        output_str = result_obj.output
                    
                    self.context.add_tool_output(tool_call_id, output_str)
                    
                    # 通知外部工具执行结果
                    yield {"type": "tool_output", "content": {"id": tool_call_id, "output": output_str}}

                    # === Interruption Check (Ask User) ===
                    if isinstance(result_obj, ToolResult) and result_obj.data and result_obj.data.get("action") == "ask_user":
                        yield {"type": "interrupt", "content": result_obj.data}
                        return # <--- Stop execution loop to wait for user input

                    # 特殊处理: 如果是 attempt_completion
                    if func_name == "attempt_completion":
                        yield {"type": "finished", "content": output_str}
                        return

                current_step += 1
            else:
                yield {"type": "finished", "content": "Done"}
                break

# ==========================================
# Layer 1: IDE / UI Layer (CLI 实现)
# ==========================================
class CLI:
    def __init__(self, runtime: AgentRuntime):
        self.runtime = runtime
        # CLI 不需要复杂的 Interpreter 了，直接在在这里处理打印逻辑，或者保留一个简单的 helper

    async def run(self):
        print("┌──────────────────────────┐")
        print("│   Agent System Online    │")
        print("└──────────────────────────┘")
        
        while True:
            try:
                user_input = input("\n[User]: ").strip()
                
                if not user_input:
                    continue

                if user_input.lower() in ["exit", "quit"]:
                    break
                
                print("│")
                
                # 状态标记，用于控制换行美观
                self.last_event_type = None 
                
                async for event in self.runtime.step(user_input):
                    self.render_event(event)
                    
                print("") # 结束后的换行
                    
            except KeyboardInterrupt:
                break
    
    def render_event(self, event):
        etype = event["type"]
        content = event["content"]
        
        if etype == "thinking_delta":
            # 黄色思考过程
            print(f"\033[93m{content}\033[0m", end="", flush=True)
            self.last_event_type = "thinking"
            
        elif etype == "content_delta":
            # 绿色正文
            # 如果之前是思考，先换行
            if self.last_event_type == "thinking":
                print("\n\n", end="", flush=True)
                self.last_event_type = "content"
            print(f"\033[92m{content}\033[0m", end="", flush=True)
            
        elif etype == "tool_call":
            print(f"\n\n⚙️  [Tool Call]: {content['name']} ({content['args']})")
            self.last_event_type = "tool"
            
        elif etype == "tool_output":
            # 截断过长的输出
            out_str = content['output']
            if len(out_str) > 200:
                out_str = out_str[:200] + "..."
            print(f"   └──> [Output]: {out_str}")
            
        elif etype == "finished":
            # 结束
            print(f"\n\033[92m[Finished]: {content}\033[0m")
            pass
        elif etype == "error":
            print(f"\n\033[91m[Error]: {content}\033[0m")

# ==========================================
# Main
# ==========================================

if __name__ == "__main__":
    # 从 .env 文件加载环境变量
    load_dotenv()
    
    # 配置
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("OPENAI_MODEL", "Qwen/Qwen3-235B-A22B-Thinking-2507")
    
    # 1. 初始化 Transport
    transport = LLMTransport(api_key=api_key, base_url=base_url, model=model)
    
    # 2. 初始化技能系统
    skills_root = Path(".skills")
    skills_loader = SkillsLoader(skills_root)
    skills_manager = SkillsManager(skills_loader)
    
    # 3. 初始化工具执行器
    executor = ToolExecutor()
    
    # 注册所有工具
    # IO Tools
    executor.register(list_files, ListFilesArgs)
    executor.register(read_file, ReadFileArgs)
    executor.register(write_to_file, WriteToFileArgs)
    executor.register(delete_file, DeleteFileArgs)
    executor.register(search_files, SearchFilesArgs)
    executor.register(edit_file, EditFileArgs)
    
    # System Tools
    executor.register(execute_command, ExecuteCommandArgs)
    
    # Browser Tools
    executor.register(browser_action, BrowserActionArgs)
    
    # Diff Tools
    executor.register(apply_diff, ApplyDiffArgs)
    
    # Interaction Tools
    executor.register(ask_followup_question, AskFollowupQuestionArgs)
    executor.register(attempt_completion, AttemptCompletionArgs)
    executor.register(new_task, NewTaskArgs)
    executor.register(switch_mode, SwitchModeArgs)
    executor.register(update_todo_list, UpdateTodoListArgs)
    executor.register(fetch_instructions, FetchInstructionsArgs)
    
    # Skills Tools
    executor.register(list_skills, ListSkillsArgs)
    executor.register(search_skills, SearchSkillsArgs)
    executor.register(get_skill, GetSkillArgs)
    
    
    # 4. 初始化核心运行时（传入 skills_manager）
    logger = ConversationLogger()
    runtime = AgentRuntime(transport, executor, skills_manager=skills_manager, logger=logger)
    
    # 5. 启动 UI
    app = CLI(runtime)
    asyncio.run(app.run())