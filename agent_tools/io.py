import os
import shutil
import re
import glob
from pathlib import Path
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field

from agent_tools.base import ToolContext, ToolResult, validate_path

# --- Argument Models ---

class ListFilesArgs(BaseModel):
    path: str = Field(..., description="Directory path to inspect, relative to the workspace")
    recursive: bool = Field(..., description="Set true to list contents recursively; false to show only the top level")

class ReadFileItem(BaseModel):
    path: str = Field(..., description="Path to the file to read, relative to the workspace")
    line_ranges: Optional[List[Tuple[int, int]]] = Field(None, description="Optional line ranges to read. Each range is a [start, end] tuple with 1-based inclusive line numbers. Use multiple ranges for non-contiguous sections.")

class ReadFileArgs(BaseModel):
    files: List[ReadFileItem] = Field(..., description="List of files to read; request related files together when allowed")

class WriteToFileArgs(BaseModel):
    path: str = Field(..., description="The path of the file to write to (relative to the current workspace directory)")
    content: str = Field(..., description="The content to write to the file. ALWAYS provide the COMPLETE intended content of the file, without any truncation or omissions. You MUST include ALL parts of the file, even if they haven't been modified. Do NOT include line numbers in the content.")

class DeleteFileArgs(BaseModel):
    path: str = Field(..., description="Path to the file or directory to delete, relative to the workspace")

class SearchFilesArgs(BaseModel):
    path: str = Field(..., description="Directory to search recursively, relative to the workspace")
    regex: str = Field(..., description="Rust-compatible regular expression pattern to match")
    file_pattern: Optional[str] = Field(None, description="Optional glob to limit which files are searched (e.g., *.ts)")

class EditFileArgs(BaseModel):
    file_path: str = Field(..., description="The path to the file to modify or create. You can use either a relative path in the workspace or an absolute path. If an absolute path is provided, it will be preserved as is.")
    old_string: str = Field(..., description="The exact literal text to replace (must match the file contents exactly, including all whitespace and indentation). For single replacements (default), include at least 3 lines of context BEFORE and AFTER the target text. Use empty string to create a new file.")
    new_string: str = Field(..., description="The exact literal text to replace old_string with. When creating a new file (old_string is empty), this becomes the file content.")
    expected_replacements: int = Field(1, description="Number of replacements expected. Defaults to 1 if not specified. Use when you want to replace multiple occurrences of the same text.", ge=1)

# --- Tool Implementations ---

def list_files(ctx: ToolContext, args: ListFilesArgs) -> ToolResult:
    """
    Request to list files and directories within the specified directory. If recursive is true, it will list all files and directories recursively. If recursive is false or not provided, it will only list the top-level contents. Do not use this tool to confirm the existence of files you may have created, as the user will let you know if the files were created successfully or not.
    """
    try:
        target_path = validate_path(args.path, ctx.workspace_root)
        
        if not target_path.exists():
             return ToolResult(success=False, output=f"错误：路径不存在 / Error: Path does not exist: {target_path}")
        
        if not target_path.is_dir():
            return ToolResult(success=False, output=f"错误：路径不是目录 / Error: Path is not a directory: {target_path}")

        results = []
        if args.recursive:
            # Recursive traversal
            for root, dirs, files in os.walk(target_path):
                # Calculate relative path
                rel_root = Path(root).relative_to(target_path)
                if rel_root == Path('.'):
                    rel_root = Path('')
                
                for name in dirs:
                    results.append(str(rel_root / name) + "/")
                for name in files:
                    results.append(str(rel_root / name))
        else:
            # Top-level only
            for item in target_path.iterdir():
                name = item.name
                if item.is_dir():
                    name += "/"
                results.append(name)
        
        results.sort()
        return ToolResult(success=True, output="\n".join(results))

    except Exception as e:
        return ToolResult(success=False, output=f"列出文件失败 / Failed to list files: {str(e)}")

def read_file(ctx: ToolContext, args: ReadFileArgs) -> ToolResult:
    """
    Read one or more files and return their contents with line numbers for diffing or discussion. IMPORTANT: You can read a maximum of 5 files in a single request. If you need to read more files, use multiple sequential read_file requests. Structure: { files: [{ path: 'relative/path.ts', line_ranges: [[1, 50], [100, 150]] }] }. The 'path' is required and relative to workspace. The 'line_ranges' is optional for reading specific sections. Each range is a [start, end] tuple (1-based inclusive). Supports text extraction from PDF and DOCX files, but may not handle other binary files properly. Example single file: { files: [{ path: 'src/app.ts' }] }. Example with line ranges: { files: [{ path: 'src/app.ts', line_ranges: [[1, 50], [100, 150]] }] }. Example multiple files (within 5-file limit): { files: [{ path: 'file1.ts', line_ranges: [[1, 50]] }, { path: 'file2.ts' }] }
    """
    output_parts = []
    
    for file_item in args.files:
        try:
            target_path = validate_path(file_item.path, ctx.workspace_root)
            
            if not target_path.exists():
                output_parts.append(f"错误：文件不存在 / Error: File not found: {file_item.path}")
                continue
            
            if not target_path.is_file():
                output_parts.append(f"错误：路径不是文件 / Error: Path is not a file: {file_item.path}")
                continue

            # Read file content
            try:
                with open(target_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except UnicodeDecodeError:
                output_parts.append(f"错误：无法解码文件 (可能是二进制文件) / Error: Cannot decode file (binary?): {file_item.path}")
                continue

            content_display = []
            
            # If line ranges are specified
            if file_item.line_ranges:
                for start, end in file_item.line_ranges:
                    # Adjust to 0-indexed, end is inclusive
                    # start 1 -> index 0
                    chunk = lines[start-1:end]
                    # Add line numbers
                    for i, line in enumerate(chunk):
                        content_display.append(f"{start + i:4d} | {line.rstrip()}")
            else:
                # Show entire file
                for i, line in enumerate(lines):
                    content_display.append(f"{i + 1:4d} | {line.rstrip()}")
            
            output_parts.append(f"--- {file_item.path} ---\n" + "\n".join(content_display))

        except Exception as e:
            output_parts.append(f"读取文件 {file_item.path} 失败 / Failed to read {file_item.path}: {str(e)}")

    return ToolResult(success=True, output="\n\n".join(output_parts))

def write_to_file(ctx: ToolContext, args: WriteToFileArgs) -> ToolResult:
    """
    Request to write content to a file. This tool is primarily used for creating new files or for scenarios where a complete rewrite of an existing file is intentionally required. If the file exists, it will be overwritten. If it doesn't exist, it will be created. This tool will automatically create any directories needed to write the file.

    **Important:** You should prefer using other editing tools over write_to_file when making changes to existing files, since write_to_file is slower and cannot handle large files. Use write_to_file primarily for new file creation.

    When using this tool, use it directly with the desired content. You do not need to display the content before using the tool. ALWAYS provide the COMPLETE file content in your response. This is NON-NEGOTIABLE. Partial updates or placeholders like '// rest of code unchanged' are STRICTLY FORBIDDEN. Failure to do so will result in incomplete or broken code.

    When creating a new project, organize all new files within a dedicated project directory unless the user specifies otherwise. Structure the project logically, adhering to best practices for the specific type of project being created.
    """
    try:
        target_path = validate_path(args.path, ctx.workspace_root)
        
        # Create parent directories
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(args.content)
            
        return ToolResult(success=True, output=f"成功写入文件 / Successfully wrote to: {args.path}")
    except Exception as e:
        return ToolResult(success=False, output=f"写入文件失败 / Failed to write file: {str(e)}")

def delete_file(ctx: ToolContext, args: DeleteFileArgs) -> ToolResult:
    """
    Delete a file or directory from the workspace. This action is irreversible and requires user approval. For directories, all contained files are validated against protection rules and .kilocodeignore before deletion. Cannot delete write-protected files or paths outside the workspace.
    """
    try:
        target_path = validate_path(args.path, ctx.workspace_root)
        
        if not target_path.exists():
            return ToolResult(success=False, output=f"错误：路径不存在 / Error: Path does not exist: {args.path}")
            
        if target_path.is_dir():
            shutil.rmtree(target_path)
            return ToolResult(success=True, output=f"成功删除目录 / Successfully deleted directory: {args.path}")
        else:
            os.remove(target_path)
            return ToolResult(success=True, output=f"成功删除文件 / Successfully deleted file: {args.path}")
            
    except Exception as e:
        return ToolResult(success=False, output=f"删除失败 / Failed to delete: {str(e)}")

def search_files(ctx: ToolContext, args: SearchFilesArgs) -> ToolResult:
    """
    Request to perform a regex search across files in a specified directory, providing context-rich results. This tool searches for patterns or specific content across multiple files, displaying each match with encapsulating context.

    Craft your regex patterns carefully to balance specificity and flexibility. Use this tool to find code patterns, TODO comments, function definitions, or any text-based information across the project. The results include surrounding context, so analyze the surrounding code to better understand the matches. Leverage this tool in combination with other tools for more comprehensive analysis.
    """
    try:
        search_root = validate_path(args.path, ctx.workspace_root)
        if not search_root.is_dir():
             return ToolResult(success=False, output=f"错误：路径不是目录 / Error: Path is not a directory: {args.path}")

        regex = re.compile(args.regex)
        matches = []
        
        # Walk through files
        for root, _, files in os.walk(search_root):
            for file in files:
                # Check file pattern filter
                if args.file_pattern:
                    if not glob.fnmatch.fnmatch(file, args.file_pattern):
                        continue
                
                file_path = Path(root) / file
                try:
                    # Try reading file
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        
                    for i, line in enumerate(lines):
                        if regex.search(line):
                            rel_path = file_path.relative_to(ctx.workspace_root)
                            # Simple context: show matching line
                            matches.append(f"{rel_path}:{i+1}: {line.strip()}")
                            
                except (UnicodeDecodeError, OSError):
                    # Skip binary or unreadable files
                    continue
                    
        if not matches:
            return ToolResult(success=True, output="未找到匹配项 / No matches found.")
            
        return ToolResult(success=True, output="\n".join(matches))

    except re.error as e:
        return ToolResult(success=False, output=f"无效的正则表达式 / Invalid regex: {str(e)}")
    except Exception as e:
        return ToolResult(success=False, output=f"搜索失败 / Search failed: {str(e)}")

def edit_file(ctx: ToolContext, args: EditFileArgs) -> ToolResult:
    """
    Use this tool to replace text in an existing file, or create a new file.

    This tool performs literal string replacement with support for multiple occurrences.

    USAGE PATTERNS:

    1. MODIFY EXISTING FILE (default):
       - Provide file_path, old_string (text to find), and new_string (replacement)
       - By default, expects exactly 1 occurrence of old_string
       - Use expected_replacements to replace multiple occurrences

    2. CREATE NEW FILE:
       - Set old_string to empty string ""
       - new_string becomes the entire file content
       - File must not already exist

    CRITICAL REQUIREMENTS:

    1. EXACT MATCHING: The old_string must match the file contents EXACTLY, including:
       - All whitespace (spaces, tabs, newlines)
       - All indentation
       - All punctuation and special characters

    2. CONTEXT FOR UNIQUENESS: For single replacements (default), include at least 3 lines of context BEFORE and AFTER the target text to ensure uniqueness.

    3. MULTIPLE REPLACEMENTS: If you need to replace multiple identical occurrences:
       - Set expected_replacements to the exact count you expect to replace
       - ALL occurrences will be replaced

    4. NO ESCAPING: Provide the literal text - do not escape special characters.
    """
    try:
        target_path = validate_path(args.file_path, ctx.workspace_root)
        
        # Case 2: Create new file
        if args.old_string == "":
            if target_path.exists():
                return ToolResult(success=False, output=f"错误：文件已存在，无法创建 / Error: File already exists, cannot create: {args.file_path}")
            
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(args.new_string)
            return ToolResult(success=True, output=f"成功创建文件 / Successfully created file: {args.file_path}")
            
        # Case 1: Modify existing file
        if not target_path.exists():
             return ToolResult(success=False, output=f"错误：文件不存在 / Error: File not found: {args.file_path}")
             
        with open(target_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        count = content.count(args.old_string)
        
        if count == 0:
            return ToolResult(success=False, output=f"错误：未在文件中找到 'old_string' / Error: 'old_string' not found in file.")
            
        if count != args.expected_replacements:
            return ToolResult(success=False, output=f"错误：预期替换 {args.expected_replacements} 处，但找到 {count} 处。请提供更具体的上下文。 / Error: Expected {args.expected_replacements} replacements, found {count}. Please provide more context.")
            
        new_content = content.replace(args.old_string, args.new_string)
        
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        return ToolResult(success=True, output=f"成功替换 {count} 处内容 / Successfully replaced {count} occurrence(s).")

    except Exception as e:
        return ToolResult(success=False, output=f"编辑文件失败 / Failed to edit file: {str(e)}")
