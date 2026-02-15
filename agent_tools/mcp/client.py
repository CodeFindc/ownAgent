import asyncio
import uuid
import sys
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel

from .transport import Transport, StdioTransport, SseTransport
from .models import (
    JsonRpcRequest, JsonRpcResponse, 
    InitializeParams, InitializeResult, 
    ClientCapabilities, Implementation,
    ListToolsResult, CallToolResult, Tool
)

class McpClient:
    """
    MCP 客户端实现。
    
    负责处理 MCP 协议的握手、工具发现和调用。
    
    属性:
        transport (Transport): 传输层实例
        _request_id (int): 请求 ID 计数器
        _pending_requests (Dict): 等待响应的请求 {id: Future}
        server_capabilities (Optional[Any]): 服务器能力信息
        server_info (Optional[Implementation]): 服务器实现信息
    """
    
    def __init__(self, transport: Transport):
        self.transport = transport
        self._request_id = 0
        self._pending_requests: Dict[Union[str, int], asyncio.Future] = {}
        self.server_capabilities = None
        self.server_info = None
        self._receive_task: Optional[asyncio.Task] = None
        self.is_connected = False

    async def connect(self):
        """
        连接到 MCP 服务器并执行握手。
        """
        await self.transport.start()
        
        # 启动接收循环
        self._receive_task = asyncio.create_task(self._receive_loop())
        
        # 发送初始化请求
        init_params = InitializeParams(
            clientInfo=Implementation(name="ownAgent-mcp-client", version="1.0.0"),
            capabilities=ClientCapabilities()
        )
        
        result_data = await self.request("initialize", init_params.model_dump(exclude_none=True))
        
        # 解析初始化结果
        init_result = InitializeResult(**result_data)
        self.server_capabilities = init_result.capabilities
        self.server_info = init_result.serverInfo
        
        # 发送已初始化通知
        await self.notify("notifications/initialized", {})
        
        self.is_connected = True
        print(f"[Info] MCP Client connected to {self.server_info.name} v{self.server_info.version}")

    async def close(self):
        """关闭连接"""
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        await self.transport.close()
        self.is_connected = False

    async def request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        发送 JSON-RPC 请求并等待响应。
        """
        request_id = self._get_next_id()
        future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future
        
        request = JsonRpcRequest(method=method, params=params, id=request_id)
        
        try:
            await self.transport.send(request.model_dump(exclude_none=True))
            return await future
        except Exception as e:
            self._pending_requests.pop(request_id, None)
            raise e

    async def notify(self, method: str, params: Optional[Dict[str, Any]] = None):
        """发送 JSON-RPC 通知（不需要响应）"""
        # 注意：通知不包含 id
        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        await self.transport.send(message)

    async def list_tools(self) -> List[Tool]:
        """获取工具列表"""
        # TODO: 处理分页 (nextCursor)
        result_data = await self.request("tools/list", {})
        result = ListToolsResult(**result_data)
        return result.tools

    async def call_tool(self, name: str, arguments: Dict[str, Any] = {}) -> CallToolResult:
        """调用工具"""
        params = {
            "name": name,
            "arguments": arguments
        }
        result_data = await self.request("tools/call", params)
        # 结果可能直接是 content 列表，也可能是 CallToolResult 结构
        # MCP 规范返回 CallToolResult: { content: [], isError: bool }
        return CallToolResult(**result_data)

    def _get_next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _receive_loop(self):
        """接收消息循环"""
        try:
            async for message in self.transport.receive():
                self._handle_message(message)
        except Exception as e:
            print(f"[Error] MCP receive loop error: {e}")
            # TODO: 可以在这里触发重连或断开连接事件

    def _handle_message(self, message: Dict[str, Any]):
        """处理接收到的消息"""
        # 检查是否是响应
        if "id" in message and message["id"] is not None:
            req_id = message["id"]
            if req_id in self._pending_requests:
                future = self._pending_requests.pop(req_id)
                
                if "error" in message:
                    future.set_exception(Exception(f"MCP Error: {message['error']}"))
                else:
                    future.set_result(message.get("result"))
                return

        # 检查是否是请求（服务器调用客户端，暂不支持）
        if "method" in message and "id" in message:
            # 暂时不支持服务器调用客户端
            pass
            
        # 检查是否是通知
        if "method" in message and "id" not in message:
            # 处理通知 (e.g. logging)
            pass
