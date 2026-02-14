"""
=============================================================================
ownAgent - 文件操作工具模块
=============================================================================

本文件实现了所有文件系统相关的工具：

1. list_files - 列出目录内容
2. read_file - 读取文件内容
3. write_to_file - 写入文件
4. delete_file - 删除文件或目录
5. search_files - 正则搜索文件内容
6. edit_file - 编辑文件（搜索替换）

��有工具都：
- 接受 ToolContext 和对应的参数模型
- 返回 ToolResult 标准格式
- 使用 validate_path 进行安全验证

作者: ownAgent Team
版本: 1.0.0
=============================================================================
"""

# =============================================================================
# 标准库导入
# =============================================================================

import os               # 操作系统接口，用于文件和目录操作
import shutil           # 高级文件操作，用于删除目录树
import re               # 正则表达式，用于搜索文件内容
import glob             # 文件名模式匹配，用于过滤文件类型
from pathlib import Path  # 面向对象的文件路径处理
from typing import List, Optional, Tuple  # 类型提示

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
# 每个 Pydantic 模型定义一个工具的参数结构
# 这些模型会自动生成 OpenAI Function Calling 的 JSON Schema
# =============================================================================

class ListFilesArgs(BaseModel):
    """
    list_files 工具的参数模型。
    
    属性:
        path (str): 要检查的目录路径，相对于工作区
        recursive (bool): 是否递归列出子目录
            - True: 列出所有子目录和文件
            - False: 只列出顶层内容
    
    示例:
        >>> args = ListFilesArgs(path="src", recursive=True)
        >>> args.model_dump()
        {'path': 'src', 'recursive': True}
    """
    path: str = Field(
        ...,  # ... 表示必填字段
        description="Directory path to inspect, relative to the workspace"
    )
    recursive: bool = Field(
        ...,
        description="Set true to list contents recursively; false to show only the top level"
    )


class ReadFileItem(BaseModel):
    """
    单个文件读取项的模型。
    
    read_file 工具支持一次读取多个文件，每个文件用这个模型描述。
    
    属性:
        path (str): 文件路径，相对于工作区
        line_ranges (Optional[List[Tuple[int, int]]]): 可选的行范围列表
            - 每个范围是 [start, end] 元组
            - 行号从 1 开始，包含结束行
            - 例如：[[1, 50], [100, 150]] 读取第 1-50 行和第 100-150 行
    
    示例:
        >>> # 读取整个文件
        >>> item = ReadFileItem(path="main.py")
        
        >>> # 读取特定行范围
        >>> item = ReadFileItem(path="main.py", line_ranges=[[1, 50], [100, 150]])
    """
    path: str = Field(
        ...,
        description="Path to the file to read, relative to the workspace"
    )
    line_ranges: Optional[List[Tuple[int, int]]] = Field(
        None,
        description="Optional line ranges to read. Each range is a [start, end] tuple with 1-based inclusive line numbers. Use multiple ranges for non-contiguous sections."
    )


class ReadFileArgs(BaseModel):
    """
    read_file 工具的参数模型。
    
    属性:
        files (List[ReadFileItem]): 要读取的文件列表
            - 最多 5 个文件
            - 建议同时读取相关文件以提高效率
    
    示例:
        >>> args = ReadFileArgs(files=[
        ...     ReadFileItem(path="main.py"),
        ...     ReadFileItem(path="utils.py", line_ranges=[[1, 30]])
        ... ])
    """
    files: List[ReadFileItem] = Field(
        ...,
        description="List of files to read; request related files together when allowed"
    )


class WriteToFileArgs(BaseModel):
    """
    write_to_file 工具的参数模型。
    
    属性:
        path (str): 文件路径，相对于工作区
        content (str): 要写入的完整内容
            - 必须提供完整的文件内容，不能只提供部分
            - 不能使用占位符如 "// rest of code unchanged"
    
    注意:
        - 如果文件存在，会被覆盖
        - 如果文件不存在，会被创建
        - 会自动创建所需的父目录
    
    示例:
        >>> args = WriteToFileArgs(
        ...     path="src/main.py",
        ...     content='print("Hello, World!")'
        ... )
    """
    path: str = Field(
        ...,
        description="The path of the file to write to (relative to the current workspace directory)"
    )
    content: str = Field(
        ...,
        description="The content to write to the file. ALWAYS provide the COMPLETE intended content of the file, without any truncation or omissions. You MUST include ALL parts of the file, even if they haven't been modified. Do NOT include line numbers in the content."
    )


class DeleteFileArgs(BaseModel):
    """
    delete_file 工具的参数模型。
    
    属性:
        path (str): 要删除的文件或目录路径，相对于工作区
    
    注意:
        - 删除操作不可逆
        - 删除目录时会删除其中所有内容
        - 需要用户确认
    
    示例:
        >>> # 删除文件
        >>> args = DeleteFileArgs(path="temp.txt")
        
        >>> # 删除目录
        >>> args = DeleteFileArgs(path="build/")
    """
    path: str = Field(
        ...,
        description="Path to the file or directory to delete, relative to the workspace"
    )


class SearchFilesArgs(BaseModel):
    """
    search_files 工具的参数模型。
    
    属性:
        path (str): 搜索的根目录，相对于工作区
        regex (str): 正则表达式模式（Rust 兼容语法）
        file_pattern (Optional[str]): 文件名过滤模式
            - 例如："*.py" 只搜索 Python 文件
            - 例如："*.ts" 只搜索 TypeScript 文件
    
    示例:
        >>> # 搜索所有文件中的 "TODO"
        >>> args = SearchFilesArgs(path="src", regex="TODO")
        
        >>> # 只在 Python 文件中搜索函数定义
        >>> args = SearchFilesArgs(
        ...     path="src",
        ...     regex="def \\w+",
        ...     file_pattern="*.py"
        ... )
    """
    path: str = Field(
        ...,
        description="Directory to search recursively, relative to the workspace"
    )
    regex: str = Field(
        ...,
        description="Rust-compatible regular expression pattern to match"
    )
    file_pattern: Optional[str] = Field(
        None,
        description="Optional glob to limit which files are searched (e.g., *.ts)"
    )


class EditFileArgs(BaseModel):
    """
    edit_file 工具的参数模型。
    
    这个工具用于精确替换文件中的文本，或创建新文件。
    
    属性:
        file_path (str): 文件路径，相对于工作区
        old_string (str): 要查找的文本
            - 必须与文件内容完全匹配（包括空格和缩进）
            - 设为空字符串 "" 可创建新文件
        new_string (str): 替换后的文本
        expected_replacements (int): 预期的替换次数
            - 默认为 1
            - 如果要替换多个相同的文本，设置实际数量
    
    使用模式:
        1. 修改现有文件：
           - 提供所有三个参数
           - old_string 必须完全匹配
        
        2. 创建新文件：
           - old_string 设为 ""
           - new_string 为文件内容
    
    示例:
        >>> # 替换单处文本
        >>> args = EditFileArgs(
        ...     file_path="main.py",
        ...     old_string="print('hello')",
        ...     new_string="print('world')"
        ... )
        
        >>> # 创建新文件
        >>> args = EditFileArgs(
        ...     file_path="new_file.py",
        ...     old_string="",
        ...     new_string="# New file\\nprint('hello')"
        ... )
    """
    file_path: str = Field(
        ...,
        description="The path to the file to modify or create. You can use either a relative path in the workspace or an absolute path. If an absolute path is provided, it will be preserved as is."
    )
    old_string: str = Field(
        ...,
        description="The exact literal text to replace (must match the file contents exactly, including all whitespace and indentation). For single replacements (default), include at least 3 lines of context BEFORE and AFTER the target text. Use empty string to create a new file."
    )
    new_string: str = Field(
        ...,
        description="The exact literal text to replace old_string with. When creating a new file (old_string is empty), this becomes the file content."
    )
    expected_replacements: int = Field(
        1,
        description="Number of replacements expected. Defaults to 1 if not specified. Use when you want to replace multiple occurrences of the same text.",
        ge=1  # ge=1 表示值必须 >= 1
    )


# =============================================================================
# 工具实现 (Tool Implementations)
# =============================================================================

def list_files(ctx: ToolContext, args: ListFilesArgs) -> ToolResult:
    """
    列出指定目录中的文件和子目录。
    
    参数:
        ctx (ToolContext): 工具执行上下文
        args (ListFilesArgs): 工具参数
    
    返回:
        ToolResult: 包含目录列表的结果
            - 成功时：每行一个条目，目录以 "/" 结尾
            - 失败时：错误信息
    
    功能说明:
        - recursive=True: 递归列出所有子目录和文件
        - recursive=False: 只列出顶层内容
        - 结果按字母顺序排序
    
    示例输出:
        src/
        src/main.py
        src/utils.py
        tests/
        tests/test_main.py
    """
    try:
        # 步骤 1: 验证路径安全性
        target_path = validate_path(args.path, ctx.workspace_root)
        
        # 步骤 2: 检查路径是否存在
        if not target_path.exists():
            return ToolResult(
                success=False, 
                output=f"错误：路径不存在 / Error: Path does not exist: {target_path}"
            )
        
        # 步骤 3: 检查是否为目录
        if not target_path.is_dir():
            return ToolResult(
                success=False, 
                output=f"错误：路径不是目录 / Error: Path is not a directory: {target_path}"
            )

        # 步骤 4: 收集文件列表
        results = []
        
        if args.recursive:
            # 递归遍历模式
            # os.walk 会遍历所有子目录
            for root, dirs, files in os.walk(target_path):
                # 计算相对路径
                rel_root = Path(root).relative_to(target_path)
                if rel_root == Path('.'):
                    rel_root = Path('')
                
                # 添加目录（带 / 后缀）
                for name in dirs:
                    results.append(str(rel_root / name) + "/")
                
                # 添加文件
                for name in files:
                    results.append(str(rel_root / name))
        else:
            # 顶层列表模式
            for item in target_path.iterdir():
                name = item.name
                if item.is_dir():
                    name += "/"  # 目录添加 / 后缀
                results.append(name)
        
        # 步骤 5: 排序并返回结果
        results.sort()
        return ToolResult(success=True, output="\n".join(results))

    except Exception as e:
        return ToolResult(
            success=False, 
            output=f"列出文件失败 / Failed to list files: {str(e)}"
        )


def read_file(ctx: ToolContext, args: ReadFileArgs) -> ToolResult:
    """
    读取一个或多个文件的内容。
    
    参数:
        ctx (ToolContext): 工具执行上下文
        args (ReadFileArgs): 工具参数
    
    返回:
        ToolResult: 包含文件内容的结果
            - 每个文件用 "--- 文件名 ---" 分隔
            - 每行带有行号前缀
    
    功能说明:
        - 支持一次读取最多 5 个文件
        - 支持指定行范围读取
        - 自动跳过二进制文件
        - 输出格式：行号 | 内容
    
    示例输出:
        --- main.py ---
           1 | #!/usr/bin/env python
           2 | print("Hello, World!")
           3 |
    """
    output_parts = []  # 收集各文件的输出
    
    # 遍历每个要读取的文件
    for file_item in args.files:
        try:
            # 步骤 1: 验证路径
            target_path = validate_path(file_item.path, ctx.workspace_root)
            
            # 步骤 2: 检查文件存在
            if not target_path.exists():
                output_parts.append(f"错误：文件不存在 / Error: File not found: {file_item.path}")
                continue
            
            # 步骤 3: 检查是否为文件
            if not target_path.is_file():
                output_parts.append(f"错误：路径不是文件 / Error: Path is not a file: {file_item.path}")
                continue

            # 步骤 4: 读取文件内容
            try:
                with open(target_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()  # 读取所有行
            except UnicodeDecodeError:
                # 无法解码，可能是二进制文件
                output_parts.append(f"错误：无法解码文件 (可能是二进制文件) / Error: Cannot decode file (binary?): {file_item.path}")
                continue

            # 步骤 5: 格式化输出
            content_display = []
            
            if file_item.line_ranges:
                # 指定了行范围：只显示指定范围
                for start, end in file_item.line_ranges:
                    # 转换为 0 索引，end 是包含的
                    # start 1 -> index 0
                    chunk = lines[start-1:end]
                    # 添加行号
                    for i, line in enumerate(chunk):
                        content_display.append(f"{start + i:4d} | {line.rstrip()}")
            else:
                # 没有指定范围：显示整个文件
                for i, line in enumerate(lines):
                    content_display.append(f"{i + 1:4d} | {line.rstrip()}")
            
            # 添加文件分隔符和内容
            output_parts.append(f"--- {file_item.path} ---\n" + "\n".join(content_display))

        except Exception as e:
            output_parts.append(f"读取文件 {file_item.path} 失败 / Failed to read {file_item.path}: {str(e)}")

    # 合并所有文件的输出
    return ToolResult(success=True, output="\n\n".join(output_parts))


def write_to_file(ctx: ToolContext, args: WriteToFileArgs) -> ToolResult:
    """
    将内容写入文件。
    
    参数:
        ctx (ToolContext): 工具执行上下文
        args (WriteToFileArgs): 工具参数
    
    返回:
        ToolResult: 操作结果
    
    功能说明:
        - 如果文件存在，会被覆盖
        - 如果文件不存在，会被创建
        - 自动创建所需的父目录
    
    注意:
        - 必须提供完整的文件内容
        - 不支持部分更新
        - 对于大文件或小修改，建议使用 edit_file
    """
    try:
        # 步骤 1: 验证路径
        target_path = validate_path(args.path, ctx.workspace_root)
        
        # 步骤 2: 创建父目录（如果不存在）
        # parents=True: 创建所有缺失的父目录
        # exist_ok=True: 如果目录已存在不报错
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 步骤 3: 写入文件
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(args.content)
            
        return ToolResult(
            success=True, 
            output=f"成功写入文件 / Successfully wrote to: {args.path}"
        )
        
    except Exception as e:
        return ToolResult(
            success=False, 
            output=f"写入文件失败 / Failed to write file: {str(e)}"
        )


def delete_file(ctx: ToolContext, args: DeleteFileArgs) -> ToolResult:
    """
    删除文件或目录。
    
    参数:
        ctx (ToolContext): 工具执行上下文
        args (DeleteFileArgs): 工具参数
    
    返回:
        ToolResult: 操作结果
    
    功能说明:
        - 删除文件：使用 os.remove()
        - 删除目录：使用 shutil.rmtree() 删除整个目录树
        - 操作不可逆，需要用户确认
    
    安全检查:
        - 路径必须在工作区内
        - 路径必须存在
    """
    try:
        # 步骤 1: 验证路径
        target_path = validate_path(args.path, ctx.workspace_root)
        
        # 步骤 2: 检查存在性
        if not target_path.exists():
            return ToolResult(
                success=False, 
                output=f"错误：路径不存在 / Error: Path does not exist: {args.path}"
            )
            
        # 步骤 3: 根据类型执行删除
        if target_path.is_dir():
            # 删除目录及其所有内容
            shutil.rmtree(target_path)
            return ToolResult(
                success=True, 
                output=f"成功删除目录 / Successfully deleted directory: {args.path}"
            )
        else:
            # 删除文件
            os.remove(target_path)
            return ToolResult(
                success=True, 
                output=f"成功删除文件 / Successfully deleted file: {args.path}"
            )
            
    except Exception as e:
        return ToolResult(
            success=False, 
            output=f"删除失败 / Failed to delete: {str(e)}"
        )


def search_files(ctx: ToolContext, args: SearchFilesArgs) -> ToolResult:
    """
    在文件中搜索正则表达式模式。
    
    参数:
        ctx (ToolContext): 工具执行上下文
        args (SearchFilesArgs): 工具参数
    
    返回:
        ToolResult: 搜索结果
            - 每个匹配占一行
            - 格式：文件路径:行号: 匹配内容
    
    功能说明:
        - 递归搜索指定目录
        - 支持正则表达式
        - 可选的文件类型过滤
        - 自动跳过二进制文件
    
    示例输出:
        src/main.py:10: def hello():
        src/utils.py:25: def hello_world():
    """
    try:
        # 步骤 1: 验证路径
        search_root = validate_path(args.path, ctx.workspace_root)
        
        # 检查是否为目录
        if not search_root.is_dir():
            return ToolResult(
                success=False, 
                output=f"错误：路径不是目录 / Error: Path is not a directory: {args.path}"
            )

        # 步骤 2: 编译正则表达式
        regex = re.compile(args.regex)
        matches = []  # 收集所有匹配
        
        # 步骤 3: 遍历文件
        for root, _, files in os.walk(search_root):
            for file in files:
                # 检查文件名模式过滤
                if args.file_pattern:
                    if not glob.fnmatch.fnmatch(file, args.file_pattern):
                        continue  # 跳过不匹配的文件
                
                file_path = Path(root) / file
                
                try:
                    # 尝试读取文件
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        
                    # 搜索每一行
                    for i, line in enumerate(lines):
                        if regex.search(line):
                            # 计算相对路径
                            rel_path = file_path.relative_to(ctx.workspace_root)
                            # 格式化匹配结果
                            matches.append(f"{rel_path}:{i+1}: {line.strip()}")
                            
                except (UnicodeDecodeError, OSError):
                    # 跳过二进制文件或无法读取的文件
                    continue
                    
        # 步骤 4: 返回结果
        if not matches:
            return ToolResult(
                success=True, 
                output="未找到匹配项 / No matches found."
            )
            
        return ToolResult(success=True, output="\n".join(matches))

    except re.error as e:
        # 正则表达式语法错误
        return ToolResult(
            success=False, 
            output=f"无效的正则表达式 / Invalid regex: {str(e)}"
        )
    except Exception as e:
        return ToolResult(
            success=False, 
            output=f"搜索失败 / Search failed: {str(e)}"
        )


def edit_file(ctx: ToolContext, args: EditFileArgs) -> ToolResult:
    """
    编辑文件 - 精确替换文本或创建新文件。
    
    参数:
        ctx (ToolContext): 工具执行上下文
        args (EditFileArgs): 工具参数
    
    返回:
        ToolResult: 操作结果
    
    使用模式:
        1. 修改现有文件：
           - old_string 必须与文件内容完全匹配
           - 默认预期替换 1 处
           - 可设置 expected_replacements 替换多处
        
        2. 创建新文件：
           - old_string 设为 ""
           - new_string 为文件内容
    
    安全检查:
        - 创建新文件时检查文件是否已存在
        - 修改文件时检查 old_string 是否存在
        - 检查替换次数是否符合预期
    """
    try:
        # 步骤 1: 验证路径
        target_path = validate_path(args.file_path, ctx.workspace_root)
        
        # === 情况 2: 创建新文件 ===
        if args.old_string == "":
            # 检查文件是否已存在
            if target_path.exists():
                return ToolResult(
                    success=False, 
                    output=f"错误：文件已存在，无法创建 / Error: File already exists, cannot create: {args.file_path}"
                )
            
            # 创建父目录
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入新文件
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(args.new_string)
                
            return ToolResult(
                success=True, 
                output=f"成功创建文件 / Successfully created file: {args.file_path}"
            )
            
        # === 情况 1: 修改现有文件 ===
        
        # 检查文件存在
        if not target_path.exists():
            return ToolResult(
                success=False, 
                output=f"错误：文件不存在 / Error: File not found: {args.file_path}"
            )
            
        # 读取��件内容
        with open(target_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 统计 old_string 出现次数
        count = content.count(args.old_string)
        
        # 检查是否找到
        if count == 0:
            return ToolResult(
                success=False, 
                output=f"错误：未在文件中找到 'old_string' / Error: 'old_string' not found in file."
            )
            
        # 检查次数是否符合预期
        if count != args.expected_replacements:
            return ToolResult(
                success=False, 
                output=f"错误：预期替换 {args.expected_replacements} 处，但找到 {count} 处。请提供更具体的上下文。 / Error: Expected {args.expected_replacements} replacements, found {count}. Please provide more context."
            )
            
        # 执行替换
        new_content = content.replace(args.old_string, args.new_string)
        
        # 写回文件
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        return ToolResult(
            success=True, 
            output=f"成功替换 {count} 处内容 / Successfully replaced {count} occurrence(s)."
        )

    except Exception as e:
        return ToolResult(
            success=False, 
            output=f"编辑文件失败 / Failed to edit file: {str(e)}"
        )
