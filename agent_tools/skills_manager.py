"""
=============================================================================
ownAgent - 技���管理器模块
=============================================================================

本文件实现了技能系统的管理功能：

1. SkillsManager - 技能管理器类
2. 技能搜索和匹配算法
3. 技能元信息管理

功能说明：
- 管理所有已加载的技能
- 提供技能搜索功能
- 实现相关性匹配算法
- 支持按名称获取技能

设计模式：
- 单例模式：全局只有一个技能管理器实例
- 代理模式：代理 SkillsLoader 的加载功能
- 策略模式：可配置的搜索匹配策略

作者: ownAgent Team
版本: 1.0.0
=============================================================================
"""

# =============================================================================
# 标准库导入
# =============================================================================

from pathlib import Path  # 面向对象的文件路径处理
from typing import List, Optional  # 类型提示
import re  # 正则表达式，用于文本匹配

# =============================================================================
# 项目内部模块导入
# =============================================================================

from agent_tools.skills_loader import SkillsLoader, SkillMetadata


# =============================================================================
# 技能管理器类
# =============================================================================

class SkillsManager:
    """
    技能管理器 - 管理技能的搜索和获取。
    
    这个类是技能系统的核心，提供：
    - 技能元信息管理
    - 技能搜索功能
    - 技能内容获取
    
    与 SkillsLoader 的关系：
    - SkillsLoader 负责从文件加载技能
    - SkillsManager 负责管理和检索技能
    - SkillsManager 内部使用 SkillsLoader
    
    属性:
        loader (SkillsLoader): 技能加载器实例
        skills (List[SkillMetadata]): 已加载的技能元信息列表
    
    使用示例:
        >>> manager = SkillsManager(Path(".skills"))
        >>> manager.load_skills()
        >>> results = manager.search_skills("创建 API")
        >>> content = manager.get_skill_content("create_api")
    """
    
    def __init__(self, skills_root: Path):
        """
        初始化技能管理器。
        
        参数:
            skills_root (Path): 技能根目录路径
                - 默认为 .skills
                - 会在初始化时创建加载器
        """
        # 创建技能加载器
        self.loader = SkillsLoader(skills_root)
        # 存储已加载的技能元信息
        self.skills: List[SkillMetadata] = []
    
    def load_skills(self) -> int:
        """
        加载所有技能的元信息。
        
        这个方法应该在初始化后调用。
        只加载元信息，不加载完整内容。
        
        返回:
            int: 成功加载的技能数量
        
        流程:
            1. 调用加载器的 load_all_metadata
            2. 存储结果到 self.skills
            3. 返回加载数量
        """
        # 加载所有元信息
        self.skills = self.loader.load_all_metadata()
        # 返回加载数量
        return len(self.skills)
    
    def get_all_metadata(self) -> List[SkillMetadata]:
        """
        获取所有技能的元信息。
        
        返回已加载的所有技能元信息列表。
        用于展示可用技能。
        
        返回:
            List[SkillMetadata]: 技能元信息列表
        
        使用场景:
            - 列出所有可用技能
            - 展示技能目录
            - 调试技能系统
        """
        return self.skills
    
    def search_skills(self, query: str, limit: int = 3) -> List[SkillMetadata]:
        """
        搜索相关技能。
        
        根据查询文本匹配技能的名称和描述。
        使用简单的相关性评分算法。
        
        参数:
            query (str): 搜索查询文本
                - 可以是关键词或描述性语句
                - 会与技能名称和描述进行匹配
            
            limit (int): 返回结果数量限制
                - 默认为 3
                - 避免返回过多结果
        
        返回:
            List[SkillMetadata]: 匹配的技能元信息列表
                - 按相关性排序
                - 最多返回 limit 个结果
        
        匹配算法:
            1. 将查询分词
            2. 计算每个技能的相关性得分
            3. 名称匹配权重 0.8，描述匹配权重 0.6
            4. 只返回得分超过 0.3 的技能
            5. 按得分降序排序
        
        示例:
            >>> results = manager.search_skills("创建 REST API", limit=5)
            >>> for skill in results:
            ...     print(f"{skill.name}: {skill.description}")
        """
        # 存储匹配结果和得分
        matches = []
        
        # 将查询转换为小写并分词
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        # 遍历所有技能
        for skill in self.skills:
            # 计算相关性得分
            score = self._calculate_relevance(skill, query_lower, query_words)
            
            # 只保留得分超过阈值的结果
            if score > 0.3:
                matches.append((skill, score))
        
        # 按得分降序排序
        matches.sort(key=lambda x: x[1], reverse=True)
        
        # 返回前 limit 个结果
        return [skill for skill, score in matches[:limit]]
    
    def _calculate_relevance(
        self, 
        skill: SkillMetadata, 
        query_lower: str, 
        query_words: set
    ) -> float:
        """
        计算技能与查询的相关性得分。
        
        内部方法，用于搜索匹配。
        
        参数:
            skill (SkillMetadata): 技能元信息
            query_lower (str): 小写的查询文本
            query_words (set): 查询分词集合
        
        返回:
            float: 相关性得分（0.0 - 1.0）
        
        评分规则:
            - 名称完全匹配：0.8 分
            - 名称部分匹配：0.5 分
            - 描述完全匹配：0.6 分
            - 描述部分匹配：0.3 分
            - 取最高分
        """
        score = 0.0
        
        # 名称匹配（权重更高）
        name_lower = skill.name.lower()
        if query_lower in name_lower:
            # 查询包含在名称中
            score = max(score, 0.8)
        elif any(word in name_lower for word in query_words):
            # 名称包含查询的某个词
            score = max(score, 0.5)
        
        # 描述匹配
        desc_lower = skill.description.lower()
        if query_lower in desc_lower:
            # 查询包含在描述中
            score = max(score, 0.6)
        elif any(word in desc_lower for word in query_words):
            # 描述包含查询的某个词
            score = max(score, 0.3)
        
        return score
    
    def get_skill_content(self, skill_name: str) -> Optional[str]:
        """
        获取技能的完整内容。
        
        按需加载技能的完整 Markdown 内容。
        用于实际执行技能任务。
        
        参数:
            skill_name (str): 技能名称
        
        返回:
            Optional[str]: 技能完整内容，不存在返回 None
        
        流程:
            1. 检查技能是否存在
            2. 调用加载器获取内容
            3. 返回内容
        """
        # 检查技能是否存在
        if not any(s.name == skill_name for s in self.skills):
            return None
        
        # 调用加载器获取内容
        return self.loader.load_skill_content(skill_name)
    
    def get_skill_by_name(self, skill_name: str) -> Optional[SkillMetadata]:
        """
        按名称获取技能元信息。
        
        精确匹配技能名称。
        
        参数:
            skill_name (str): 技能名称
        
        返回:
            Optional[SkillMetadata]: 技能元信息，不存在返回 None
        """
        for skill in self.skills:
            if skill.name == skill_name:
                return skill
        return None
    
    def reload_skills(self) -> int:
        """
        重新加载所有技能。
        
        清空缓存并重新加载技能。
        用于技能文件更新后刷新。
        
        返回:
            int: 成功加载的技能数量
        """
        # 清空加载器缓存
        self.loader.clear_cache()
        # 清空技能列表
        self.skills = []
        # 重新加载
        return self.load_skills()
    
    def get_skill_count(self) -> int:
        """
        获取已加载的技能数量。
        
        返回:
            int: 技能数量
        """
        return len(self.skills)
    
    def skill_exists(self, skill_name: str) -> bool:
        """
        检查技能是否存在。
        
        参数:
            skill_name (str): 技能名称
        
        返回:
            bool: 存在返回 True，否则返回 False
        """
        return any(s.name == skill_name for s in self.skills)
