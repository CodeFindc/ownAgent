import re
from typing import List, Tuple
from pydantic import BaseModel, Field
from agent_tools.base import ToolContext, ToolResult, validate_path

class ApplyDiffArgs(BaseModel):
    path: str = Field(..., description="The path of the file to modify, relative to the current workspace directory.")
    diff: str = Field(..., description="A string containing one or more search/replace blocks defining the changes. The ':start_line:' is required and indicates the starting line number of the original content. You must not add a start line for the replacement content. Each block must follow this format:\n<<<<<<< SEARCH\n:start_line:[line_number]\n-------\n[exact content to find]\n=======\n[new content to replace with]\n>>>>>>> REPLACE")

def apply_diff(ctx: ToolContext, args: ApplyDiffArgs) -> ToolResult:
    """
    Apply precise, targeted modifications to an existing file using one or more search/replace blocks. This tool is for surgical edits only; the 'SEARCH' block must exactly match the existing content, including whitespace and indentation. To make multiple targeted changes, provide multiple SEARCH/REPLACE blocks in the 'diff' parameter. Use the 'read_file' tool first if you are not confident in the exact content to search for.
    """
    try:
        target_path = validate_path(args.path, ctx.workspace_root)
        if not target_path.exists():
            return ToolResult(success=False, output=f"错误：文件不存在 / Error: File not found: {args.path}")

        with open(target_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.splitlines(keepends=True)
        
        # Parse diff blocks
        pattern = re.compile(
            r'<<<<<<< SEARCH\n:start_line:(\d+)\n-------\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE',
            re.DOTALL
        )
        
        blocks = list(pattern.finditer(args.diff))
        
        if not blocks:
            return ToolResult(success=False, output="错误：未找到有效的 diff 块。请检查格式。 / Error: No valid diff blocks found. Check format.")

        # Apply in reverse order of line number to avoid offset issues
        # But we need to verify all blocks match first, then apply
        
        replacements = []
        
        for match in blocks:
            start_line_idx = int(match.group(1)) - 1 # 0-indexed
            search_content = match.group(2)
            replace_content = match.group(3)
            # Regex captures up to the newline before >>>>>>>, effectively stripping the last newline
            # of the intended replacement block. we need to add it back if the block meant to have content.
            if replace_content:
                replace_content += "\n"
            
            # Verify search_content matches
            search_lines = search_content.splitlines(keepends=True)
            
            # Check from start_line_idx
            if start_line_idx < 0 or start_line_idx >= len(lines):
                 return ToolResult(success=False, output=f"错误：起始行号 {start_line_idx + 1} 超出范围 / Error: Start line {start_line_idx + 1} out of range")
            
            # Check if each line matches
            match_failed = False
            for i, search_line in enumerate(search_lines):
                file_line_idx = start_line_idx + i
                if file_line_idx >= len(lines):
                    match_failed = True
                    break
                
                # Compare content, ignoring line ending differences
                if lines[file_line_idx].rstrip('\r\n') != search_line.rstrip('\r\n'):
                    match_failed = True
                    break
            
            if match_failed:
                return ToolResult(success=False, output=f"错误：搜索块在行 {start_line_idx + 1} 处不匹配 / Error: Search block mismatch at line {start_line_idx + 1}")
                
            replacements.append({
                'start': start_line_idx,
                'end': start_line_idx + len(search_lines),
                'content': replace_content
            })

        # Check for overlaps
        replacements.sort(key=lambda x: x['start'])
        for i in range(len(replacements) - 1):
            if replacements[i]['end'] > replacements[i+1]['start']:
                 return ToolResult(success=False, output="错误：Diff 块重叠 / Error: Diff blocks overlap")

        # Apply changes (reverse order)
        new_lines = list(lines)
        for rep in reversed(replacements):
            rep_lines = rep['content'].splitlines(keepends=True)
            new_lines[rep['start']:rep['end']] = rep_lines

        new_content = "".join(new_lines)
        
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        return ToolResult(success=True, output="成功应用 Diff / Successfully applied diff")

    except Exception as e:
        return ToolResult(success=False, output=f"应用 Diff 失败 / Failed to apply diff: {str(e)}")
