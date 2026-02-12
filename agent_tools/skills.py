"""
技能检索工具模块
提供列出、搜索和获取技能的工具函数
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from agent_tools.base import ToolContext, ToolResult


class ListSkillsArgs(BaseModel):
    """列出所有技能的参数"""
    pass


class SearchSkillsArgs(BaseModel):
    """搜索技能的参数"""
    query: str = Field(..., description="搜索查询文本")
    limit: int = Field(default=3, description="返回结果数量限制")


class GetSkillArgs(BaseModel):
    """获取特定技能的参数"""
    name: str = Field(..., description="技能名称")


def list_skills(ctx: ToolContext, args: ListSkillsArgs) -> ToolResult:
    """
    列出所有可用的技能及其元信息。返回技能名称和描述，不包含完整内容。
    """
    if not ctx.skills_manager:
        return ToolResult(success=False, output="错误：技能管理器未初始化 / Error: Skills manager not initialized")
    
    metadata_list = ctx.skills_manager.get_all_metadata()
    
    if not metadata_list:
        return ToolResult(success=True, output="没有可用的技能 / No skills available")
    
    output_lines = ["可用的技能 / Available Skills:"]
    for metadata in metadata_list:
        output_lines.append(f"- **{metadata.name}**: {metadata.description}")
    
    return ToolResult(success=True, output="\n".join(output_lines))


def search_skills(ctx: ToolContext, args: SearchSkillsArgs) -> ToolResult:
    """
    根据查询搜索相关技能。返回匹配的技能元信息列表，按相关性排序。
    """
    if not ctx.skills_manager:
        return ToolResult(success=False, output="错误：技能管理器未初始化 / Error: Skills manager not initialized")
    
    matched_skills = ctx.skills_manager.search_skills(args.query, args.limit)
    
    if not matched_skills:
        return ToolResult(success=True, output=f"未找到与 '{args.query}' 相关的技能 / No skills found matching '{args.query}'")
    
    output_lines = [f"找到 {len(matched_skills)} 个相关技能 / Found {len(matched_skills)} relevant skills:"]
    for i, metadata in enumerate(matched_skills, 1):
        output_lines.append(f"{i}. **{metadata.name}**: {metadata.description}")
    
    return ToolResult(success=True, output="\n".join(output_lines))


def get_skill(ctx: ToolContext, args: GetSkillArgs) -> ToolResult:
    """
    获取特定技能的完整内容。返回技能的完整 markdown 文档，包括详细说明和使用方法。
    """
    if not ctx.skills_manager:
        return ToolResult(success=False, output="错误：技能管理器未初始化 / Error: Skills manager not initialized")
    
    content = ctx.skills_manager.get_skill_content(args.name)
    
    if not content:
        return ToolResult(success=False, output=f"错误：技能 '{args.name}' 不存在 / Error: Skill '{args.name}' not found")
    
    return ToolResult(success=True, output=f"=== {args.name} ===\n\n{content}")
