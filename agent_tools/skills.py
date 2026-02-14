"""
=============================================================================
ownAgent - 技能检索工具模块
=============================================================================

本文件实现了技能系统的检索工具：

1. list_skills - 列出所有可用技能
2. search_skills - 搜索相关技能
3. get_skill - 获取技能完整内容

技能系统概述：
- 技能是预定义的任务模板，存储在 .skills/ 目录
- 每个技能是一个 Markdown 文件，包含元信息和详细指令
- AI 可以根据任务描述自动匹配合适的技能
- 技能让 AI 能够执行特定领域的专业任务

技能文件结构：
    .skills/
    ├── create_api/
    │   └── SKILL.md
    ├── write_tests/
    │   └── SKILL.md
    └── ...

作者: ownAgent Team
版本: 1.0.0
=============================================================================
"""

# =============================================================================
# 标准库导入
# =============================================================================

from typing import List, Optional  # 类型提示

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

class ListSkillsArgs(BaseModel):
    """
    list_skills 工具的参数模型。
    
    这个工具不需要任何参数，它会返回所有可用技能的列表。
    
    示例:
        >>> args = ListSkillsArgs()
        >>> result = list_skills(ctx, args)
    """
    pass  # 不需要参数


class SearchSkillsArgs(BaseModel):
    """
    search_skills 工具的参数模型。
    
    属性:
        query (str): 搜索查询文本
            - 可以是关键词或描述性语句
            - 会与技能的名称和描述进行匹配
        
        limit (int): 返回结果数量限制
            - 默认为 3
            - 避免返回过多结果
    
    示例:
        >>> args = SearchSkillsArgs(query="创建 API", limit=5)
        >>> result = search_skills(ctx, args)
    """
    query: str = Field(
        ...,
        description="搜索查询文本"
    )
    limit: int = Field(
        default=3,
        description="返回结果数量限制"
    )


class GetSkillArgs(BaseModel):
    """
    get_skill 工具的参数模型。
    
    属性:
        name (str): 技能名称
            - 必须是已存在的技能
            - 可以通过 list_skills 获取可用技能名称
    
    示例:
        >>> args = GetSkillArgs(name="create_api")
        >>> result = get_skill(ctx, args)
    """
    name: str = Field(
        ...,
        description="技能名称"
    )


# =============================================================================
# 工具实现 (Tool Implementations)
# =============================================================================

def list_skills(ctx: ToolContext, args: ListSkillsArgs) -> ToolResult:
    """
    列出所有可用的技能及其元信息。
    
    这个工具返回技能名称和描述，不包含完整内容。
    用于让 AI 了解有哪些技能可用。
    
    参数:
        ctx (ToolContext): 工具执行上下文
        args (ListSkillsArgs): 工具参数（无）
    
    返回:
        ToolResult: 包含技能列表的结果
    
    输出格式:
        可用的技能 / Available Skills:
        - **技能名称**: 技能描述
        - **技能名称**: 技能描述
        ...
    
    使用场景:
        - AI 想了解有哪些技能可用
        - 用户询问系统能力
        - 调试技能系统
    """
    # 检查技能管理器是否初始化
    if not ctx.skills_manager:
        return ToolResult(
            success=False, 
            output="错误：技能管理器未初始化 / Error: Skills manager not initialized"
        )
    
    # 获取所有技能的元信息
    metadata_list = ctx.skills_manager.get_all_metadata()
    
    # 检查是否有技能
    if not metadata_list:
        return ToolResult(
            success=True, 
            output="没有可用的技能 / No skills available"
        )
    
    # 格式化输出
    output_lines = ["可用的技能 / Available Skills:"]
    for metadata in metadata_list:
        output_lines.append(f"- **{metadata.name}**: {metadata.description}")
    
    return ToolResult(success=True, output="\n".join(output_lines))


def search_skills(ctx: ToolContext, args: SearchSkillsArgs) -> ToolResult:
    """
    根据查询搜索相关技能。
    
    这个工具会根据查询文本匹配技能的名称和描述，
    返回最相关的技能列表。
    
    参数:
        ctx (ToolContext): 工具执行上下文
        args (SearchSkillsArgs): 工具参数
    
    返回:
        ToolResult: 包含匹配技能列表的结果
    
    匹配算法:
        - 名称匹配权重更高（0.8）
        - 描述匹配权重较低（0.6）
        - 只返回得分超过 0.3 的技能
        - 按相关性排序
    
    输出格式:
        找到 N 个相关技能 / Found N relevant skills:
        1. **技能名称**: 技能描述
        2. **技能名称**: 技能描述
        ...
    
    使用场景:
        - AI 根据任务描述查找合适的技能
        - 用户想找到特定功能的技能
    """
    # 检查技能管理器是否初始化
    if not ctx.skills_manager:
        return ToolResult(
            success=False, 
            output="错误：技能管理器未初始化 / Error: Skills manager not initialized"
        )
    
    # 执行搜索
    matched_skills = ctx.skills_manager.search_skills(args.query, args.limit)
    
    # 检查是否有匹配结果
    if not matched_skills:
        return ToolResult(
            success=True, 
            output=f"未找到与 '{args.query}' 相关的技能 / No skills found matching '{args.query}'"
        )
    
    # 格式化输出
    output_lines = [f"找到 {len(matched_skills)} 个相关技能 / Found {len(matched_skills)} relevant skills:"]
    for i, metadata in enumerate(matched_skills, 1):
        output_lines.append(f"{i}. **{metadata.name}**: {metadata.description}")
    
    return ToolResult(success=True, output="\n".join(output_lines))


def get_skill(ctx: ToolContext, args: GetSkillArgs) -> ToolResult:
    """
    获取特定技能的完整内容。
    
    这个工具返回技能的完整 Markdown 文档，
    包括详细说明和使用方法。
    
    参数:
        ctx (ToolContext): 工具执行上下文
        args (GetSkillArgs): 工具参数
    
    返回:
        ToolResult: 包含技能完整内容的结果
    
    输出格式:
        === 技能名称 ===
        
        [技能的完整 Markdown 内容]
    
    使用场景:
        - AI 决定使用某个技能后，获取详细指令
        - 用户想查看技能的完整内容
        - 调试技能内容
    
    注意:
        - 技能内容可能很长
        - AI 应该在获取技能后按照其中的指令执行任务
    """
    # 检查技能管理器是否初始化
    if not ctx.skills_manager:
        return ToolResult(
            success=False, 
            output="错误：技能管理器未初始化 / Error: Skills manager not initialized"
        )
    
    # 获取技能内容
    content = ctx.skills_manager.get_skill_content(args.name)
    
    # 检查技能是否存在
    if not content:
        return ToolResult(
            success=False, 
            output=f"错误：技能 '{args.name}' 不存在 / Error: Skill '{args.name}' not found"
        )
    
    # 返回完整内容
    return ToolResult(
        success=True, 
        output=f"=== {args.name} ===\n\n{content}"
    )
