import abc
import asyncio
import json
import os
import sys
from typing import Optional, Dict, Any, AsyncIterator
import httpx
from pydantic import BaseModel

from .models import JsonRpcRequest, JsonRpcResponse, JsonRpcNotification

# =============================================================================
# Transport Abstraction
# =============================================================================

class Transport(abc.ABC):
    """
    MCP 传输层抽象基类。
    负责底层的消息发送和接收。
    """

    @abc.abstractmethod
    async def start(self):
        """启动传输层连接"""
        pass

    @abc.abstractmethod
    async def close(self):
        """关闭传输层连接"""
        pass

    @abc.abstractmethod
    async def send(self, message: Dict[str, Any]):
        """发送消息"""
        pass

    @abc.abstractmethod
    async def receive(self) -> AsyncIterator[Dict[str, Any]]:
        """接收消息流"""
        pass

# =============================================================================
# Stdio Transport
# =============================================================================

class StdioTransport(Transport):
    """
    基于标准输入输出 (Stdio) 的传输层实现。
    用于本地启动的 MCP 服务器进程。
    """
    def __init__(self, command: str, args: list[str], env: Optional[Dict[str, str]] = None):
        self.command = command
        self.args = args
        self.env = env or os.environ.copy()
        self.process: Optional[asyncio.subprocess.Process] = None

    async def start(self):
        """启动子进程"""
        self.process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,  # 捕获错误输出以免干扰 stdout
            env=self.env
        )

    async def close(self):
        """终止子进程"""
        if self.process:
            try:
                self.process.terminate()
                await self.process.wait()
            except Exception:
                pass

    async def send(self, message: Dict[str, Any]):
        """
        发送消息到子进程 stdin。
        使用 JSON-RPC 格式，每行一个 JSON 对象。
        """
        if not self.process or not self.process.stdin:
            raise RuntimeError("Process not started")
        
        json_str = json.dumps(message)
        self.process.stdin.write(f"{json_str}\n".encode())
        await self.process.stdin.drain()

    async def receive(self) -> AsyncIterator[Dict[str, Any]]:
        """
        从子进程 stdout 读取消息。
        """
        if not self.process or not self.process.stdout:
            raise RuntimeError("Process not started")

        while True:
            line = await self.process.stdout.readline()
            if not line:
                break
            try:
                yield json.loads(line.decode())
            except json.JSONDecodeError:
                continue

# =============================================================================
# SSE Transport
# =============================================================================

class SseTransport(Transport):
    """
    基于 SSE (Server-Sent Events) 的传输层实现。
    用于远程 MCP 服务器连接。
    """
    def __init__(self, url: str):
        self.url = url
        self.client: Optional[httpx.AsyncClient] = None
        self.endpoint: Optional[str] = None  # 从 SSE init 事件获取的消息发送端点

    async def start(self):
        """初始化 HTTP 客户端"""
        self.client = httpx.AsyncClient(timeout=None)  # SSE 需要长连接，禁用超时

    async def close(self):
        """关闭 HTTP 客户端"""
        if self.client:
            await self.client.aclose()

    async def send(self, message: Dict[str, Any]):
        """
        发送消息到 POST 端点。
        """
        if not self.client:
            raise RuntimeError("Transport not started")
        if not self.endpoint:
            raise RuntimeError("Endpoint not ready (wait for 'endpoint' event)")
            
        # 拼接完整 URL
        post_url = self.endpoint
        if not post_url.startswith("http"):
             # 这里简化处理，假设 endpoint 是相对路径或绝对路径
             from urllib.parse import urljoin
             post_url = urljoin(self.url, self.endpoint)

        await self.client.post(post_url, json=message)

    async def receive(self) -> AsyncIterator[Dict[str, Any]]:
        """
        连接 SSE 流并读取消息。
        """
        if not self.client:
            raise RuntimeError("Transport not started")

        async with self.client.stream("GET", self.url) as response:
            buffer = []
            async for line in response.aiter_lines():
                if not line.strip():
                    # 空行表示事件结束，处理缓冲区
                    event_data = self._parse_event(buffer)
                    buffer = [] # 重置缓冲区
                    
                    if not event_data:
                        continue
                        
                    event_type = event_data.get("event", "message")
                    data = event_data.get("data", "")
                    
                    if event_type == "endpoint":
                        # 处理 endpoint 事件，用于发送 POST 请求的地址
                        # endpoint 可以是相对路径或绝对路径
                        self.endpoint = data.strip()
                        print(f"[Info] MCP SSE Endpoint set to: {self.endpoint}")
                    elif event_type == "message":
                        try:
                            yield json.loads(data)
                        except json.JSONDecodeError:
                            print(f"[Warning] Failed to decode JSON from SSE message: {data}")
                            continue
                            
                else:
                    # 累积行到缓冲区
                    buffer.append(line)

    def _parse_event(self, buffer: list[str]) -> Dict[str, str]:
        """
        解析 SSE 事件缓冲区。
        返回字典: {"event": "type", "data": "content"}
        """
        event = {}
        for line in buffer:
            if line.startswith("event:"):
                event["event"] = line[6:].strip()
            elif line.startswith("data:"):
                event["data"] = line[5:].strip()
        return event
