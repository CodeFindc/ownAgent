import sys
import os
from datetime import datetime
from loguru import logger

class ConversationLogger:
    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        
        # 生成带时间戳的文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"session_{timestamp}.log")
        
        # 配置 loguru
        # 移除默认 handler 以避免控制台重复输出（如果 ag.py 已经有输出的话）
        logger.remove()
        
        # 添加文件 sink
        # rotation="10 MB" 只是示例，对于单次会话可能不需要 rotation
        # encoding="utf-8" 确保中文正常
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
            level="INFO",
            encoding="utf-8"
        )
        
        # 也可以保留 stderr 用于调试，或者添加特定的 filter
        # logger.add(sys.stderr, level="ERROR") 
        
        logger.info(f"Session started. Log file: {log_file}")

    def log_user(self, content):
        logger.info(f"[USER] {content}")

    def log_assistant(self, content):
        logger.info(f"[ASSISTANT] {content}")
    def log_thinking(self, content):
        logger.info(f"[THINKING] {content}")

    def log_tool(self, tool_id, output):
        logger.info(f"[TOOL:{tool_id}] {output}")
