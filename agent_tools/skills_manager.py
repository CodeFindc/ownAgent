"""
技能管理器模块
负责技能元信息检索、匹配和按需加载
"""

from typing import List, Optional
from agent_tools.skills_loader import SkillsLoader, SkillMetadata


class SkillsManager:
    """技能管理器，负责技能元信息检索和按需加载"""
    
    def __init__(self, loader: SkillsLoader):
        """初始化管理器
        
        Args:
            loader: 技能加载器实例
        """
        self.loader = loader
        self.metadata_list = loader.load_all_metadata()
        print(f"[INFO] SkillsManager 初始化完成，共加载 {len(self.metadata_list)} 个技能元信息")
    
    def search_skills(self, query: str, limit: int = 3) -> List[SkillMetadata]:
        """根据查询搜索相关技能（仅返回元信息）
        
        Args:
            query: 查询文本
            limit: 返回结果数量限制
            
        Returns:
            匹配的技能元信息列表（按相关性排序）
        """
        if not self.metadata_list:
            return []
        
        # 计算每个技能的匹配得分
        scored_skills = []
        for metadata in self.metadata_list:
            score = self._calculate_match_score(query, metadata)
            if score > 0.3:  # 只保留得分超过阈值的技能
                scored_skills.append((score, metadata))
        
        # 按得分降序排序
        scored_skills.sort(key=lambda x: x[0], reverse=True)
        
        # 返回前 limit 个结果
        return [metadata for score, metadata in scored_skills[:limit]]
    
    def get_skill_content(self, skill_name: str) -> Optional[str]:
        """获取技能的完整内容（按需加载）
        
        Args:
            skill_name: 技能名称
            
        Returns:
            技能的完整 markdown 内容
        """
        return self.loader.load_skill_content(skill_name)
    
    def get_metadata_summary(self) -> str:
        """获取所有技能的元信息摘要（用于系统提示词）
        
        Returns:
            格式化的技能元信息摘要字符串
        """
        if not self.metadata_list:
            return "No skills available."
        
        summary_lines = []
        for metadata in self.metadata_list:
            summary_lines.append(f"- **{metadata.name}**: {metadata.description}")
        
        return "\n".join(summary_lines)
    
    def get_all_metadata(self) -> List[SkillMetadata]:
        """获取所有已加载的技能元信息
        
        Returns:
            所有技能元信息列表
        """
        return self.metadata_list
    
    def _calculate_match_score(self, query: str, metadata: SkillMetadata) -> float:
        """计算查询与技能的匹配得分
        
        Args:
            query: 用户查询文本
            metadata: 技能元信息
            
        Returns:
            匹配得分（0-1 之间）
        """
        query_lower = query.lower()
        name_lower = metadata.name.lower()
        desc_lower = metadata.description.lower()
        
        # 名称匹配权重更高
        name_score = 0.0
        if query_lower in name_lower:
            name_score = 0.8
        elif any(word in name_lower for word in query_lower.split()):
            name_score = 0.5
        
        # 描述匹配
        desc_score = 0.0
        if query_lower in desc_lower:
            desc_score = 0.6
        elif any(word in desc_lower for word in query_lower.split()):
            desc_score = 0.3
        
        # 综合得分
        return max(name_score, desc_score)
