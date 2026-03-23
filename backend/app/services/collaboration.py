"""
实时协作服务 (WebSockets)
"""
from typing import Dict, List, Set
from fastapi import WebSocket
import json
import asyncio
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # article_id -> set of websockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # article_id -> list of active user info
        self.active_users: Dict[str, List[dict]] = {}

    async def connect(self, websocket: WebSocket, article_id: str, user_info: dict):
        await websocket.accept()
        if article_id not in self.active_connections:
            self.active_connections[article_id] = set()
            self.active_users[article_id] = []
            
        self.active_connections[article_id].add(websocket)
        self.active_users[article_id].append(user_info)
        
        # 广播新用户加入
        await self.broadcast(article_id, {
            "type": "presence",
            "action": "join",
            "user": user_info,
            "total_users": self.active_users[article_id]
        })

    def disconnect(self, websocket: WebSocket, article_id: str, user_id: str):
        if article_id in self.active_connections:
            self.active_connections[article_id].remove(websocket)
            self.active_users[article_id] = [u for u in self.active_users[article_id] if u['id'] != user_id]
            
            if not self.active_connections[article_id]:
                del self.active_connections[article_id]
                del self.active_users[article_id]

    async def broadcast(self, article_id: str, message: dict):
        if article_id in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[article_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.warning(f"WebSocket 广播失败: {e}")
                    disconnected.add(connection)
            
            for conn in disconnected:
                self.active_connections[article_id].remove(conn)

manager = ConnectionManager()
