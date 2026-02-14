"""
=============================================================================
ownAgent - 差异应用工具模块
=============================================================================

本文件实现了精确的文件差异应用工具：

1. apply_diff - 应用搜索/替换块来修改文件

这个工具提供了比 edit_file 更精确的文件编辑方式：
- 支持指定行号
- 支持多个修改块
- 验证搜索内容匹配

适用场景：
- 需要精确控制修改位置
- 需要在同一文件中进行多处修改
- 需要确保修改的准确性

作者: ownAgent Team
版本: 1.0.0
=============================================================================
"""

# =============================================================================
# 标准库导入
# =============================================================================

import re           # 正则表达式，用于解析 diff 块
from typing import List, Tuple  # 类型提示

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

class ApplyDiffArgs(BaseModel):
    """
    apply_diff 工具的参数模型。
    
    属性:
        path (str): 要修改的文件路径，相对于工作区
        
        diff (str): 包含一个或多个搜索/替换块的字符串
            - 每个块指定起始行号、搜索内容和替换内容
            - 支持多个块进行多处修改
    
    Diff 块格式:
        <<<<<<< SEARCH
        :start_line:[行号]
        -------
        [要搜索的原始内容]
        =======
        [替换后的新内容]
        >>>>>>> REPLACE
    
    示例:
        >>> args = ApplyDiffArgs(
        ...     path="main.py",
        ...     diff='''<<<<<<< SEARCH
        ... :start_line:10
        ... -------
        ... def hello():
        ...     print("world")
        ... =======
        ... def hello():
        ...     print("hello")
        ... >>>>>>> REPLACE'''
        ... )
    
    多块示例:
        >>> # 同时修改文件中的多处
        >>> diff = '''
        ... <<<<<<< SEARCH
        ... :start_line:5
        ... -------
        ... old_line_1
        ... =======
        ... new_line_1
        ... >>>>>>> REPLACE
        ... <<<<<<< SEARCH
        ... :start_line:20
        ... -------
        ... old_line_2
        ... =======
        ... new_line_2
        ... >>>>>>> REPLACE
        ... '''
    """
    path: str = Field(
        ...,
        description="The path of the file to modify, relative to the current workspace directory."
    )
    diff: str = Field(
        ...,
        description="""A string containing one or more search/replace blocks defining the changes. The ':start_line:' is required and indicates the starting line number of the original content. You must not add a start line for the replacement content. Each block must follow this format:
<<<<<<< SEARCH
:start_line:[line_number]
-------
[exact content to find]
=======
[new content to replace with]
>>>>>>> REPLACE"""
    )


# =============================================================================
# 工具实现 (Tool Implementations)
# =============================================================================

def apply_diff(ctx: ToolContext, args: ApplyDiffArgs) -> ToolResult:
    """
    应用差异块来精确修改文件。
    
    这个工具使用特殊的 diff 格式来指定精确的修改位置和内容。
    相比简单的字符串替换，它提供了更好的控制：
    - 指定行号确保修改位置正确
    - 验证搜索内容确保修改的是正确的内容
    - 支持多个修改块
    
    参数:
        ctx (ToolContext): 工具执行上下文
        args (ApplyDiffArgs): 工具参数
    
    返回:
        ToolResult: 操作结果
    
    工作流程:
        1. 验证文件路径
        2. 读取文件内容
        3. 解析所有 diff 块
        4. 验证每个块的搜索内容匹配
        5. 检查块之间是否有重叠
        6. 按逆序应用修改（避免行号偏移）
        7. 写回文件
    
    错误处理:
        - 文件不存在
        - 无效的 diff 格式
        - 行号超出范围
        - 搜索内容不匹配
        - diff 块重叠
    """
    try:
        # 步骤 1: 验证文件路径
        target_path = validate_path(args.path, ctx.workspace_root)
        
        # 检查文件存在
        if not target_path.exists():
            return ToolResult(
                success=False, 
                output=f"错误：文件不存在 / Error: File not found: {args.path}"
            )

        # 步骤 2: 读取文件内容
        with open(target_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 将内容分割成行（保留换行符）
        lines = content.splitlines(keepends=True)
        
        # 步骤 3: 解析 diff 块
        # 正则表达式匹配 diff 块格式
        pattern = re.compile(
            r'<<<<<<< SEARCH\n:start_line:(\d+)\n-------\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE',
            re.DOTALL  # 让 . 匹配换行符
        )
        
        # 找到所有匹配的块
        blocks = list(pattern.finditer(args.diff))
        
        # 检查是否找到有效的 diff 块
        if not blocks:
            return ToolResult(
                success=False, 
                output="错误：未找到有效的 diff 块。请检查格式。 / Error: No valid diff blocks found. Check format."
            )

        # 步骤 4: 收集所有替换操作
        # 需要先验证所有块，然后再应用
        replacements = []
        
        for match in blocks:
            # 提取块信息
            start_line_idx = int(match.group(1)) - 1  # 转换为 0 索引
            search_content = match.group(2)           # 要搜索的内容
            replace_content = match.group(3)          # 替换后的内容
            
            # 正则捕获可能会丢失最后的换行符，需要补回
            if replace_content:
                replace_content += "\n"
            
            # 将搜索内容分割成行
            search_lines = search_content.splitlines(keepends=True)
            
            # 验证行号范围
            if start_line_idx < 0 or start_line_idx >= len(lines):
                return ToolResult(
                    success=False, 
                    output=f"错误：起始行号 {start_line_idx + 1} 超出范围 / Error: Start line {start_line_idx + 1} out of range"
                )
            
            # 验证搜索内容是否匹配
            match_failed = False
            for i, search_line in enumerate(search_lines):
                file_line_idx = start_line_idx + i
                
                # 检查是否超出文件范围
                if file_line_idx >= len(lines):
                    match_failed = True
                    break
                
                # 比较内容（忽略换行符差异）
                if lines[file_line_idx].rstrip('\r\n') != search_line.rstrip('\r\n'):
                    match_failed = True
                    break
            
            # 如果搜索内容不匹配，返回错误
            if match_failed:
                return ToolResult(
                    success=False, 
                    output=f"错误：搜索块在行 {start_line_idx + 1} 处不匹配 / Error: Search block mismatch at line {start_line_idx + 1}"
                )
            
            # 记录替换操作
            replacements.append({
                'start': start_line_idx,                    # 起始行索引
                'end': start_line_idx + len(search_lines),  # 结束行索引（不包含）
                'content': replace_content                  # 替换内容
            })

        # 步骤 5: 检查块是否重叠
        # 按起始位置排序
        replacements.sort(key=lambda x: x['start'])
        
        # 检查相邻块是否重叠
        for i in range(len(replacements) - 1):
            if replacements[i]['end'] > replacements[i+1]['start']:
                return ToolResult(
                    success=False, 
                    output="错误：Diff 块重叠 / Error: Diff blocks overlap"
                )

        # 步骤 6: 应用修改
        # 使用逆序应用，避免行号偏移影响后续修改
        new_lines = list(lines)  # 复制行列表
        
        for rep in reversed(replacements):
            # 将替换内容分割成行
            rep_lines = rep['content'].splitlines(keepends=True)
            # 替换指定范围的行
            new_lines[rep['start']:rep['end']] = rep_lines

        # 步骤 7: 写回文件
        new_content = "".join(new_lines)
        
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        return ToolResult(
            success=True, 
            output="成功应用 Diff / Successfully applied diff"
        )

    except Exception as e:
        return ToolResult(
            success=False, 
            output=f"应用 Diff 失败 / Failed to apply diff: {str(e)}"
        )
