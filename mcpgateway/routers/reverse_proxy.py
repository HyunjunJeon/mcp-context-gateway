# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/routers/reverse_proxy.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

역방향 프록시 연결을 처리하는 FastAPI 라우터.

이 모듈은 역방향 프록시 클라이언트가 로컬 MCP 서버를 게이트웨이를 통해
터널링할 수 있도록 WebSocket 및 SSE 엔드포인트를 제공합니다.
"""

# Standard
import asyncio
from datetime import datetime
import json
from typing import Any, Dict, Optional
import uuid

# Third-Party
from fastapi import APIRouter, Depends, HTTPException, Request, status, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

# First-Party
from mcpgateway.db import get_db
from mcpgateway.services.logging_service import LoggingService
from mcpgateway.utils.verify_credentials import require_auth

# Initialize logging
logging_service = LoggingService()
LOGGER = logging_service.get_logger("mcpgateway.routers.reverse_proxy")

router = APIRouter(prefix="/reverse-proxy", tags=["reverse-proxy"])


class ReverseProxySession:
    """역방향 프록시 세션을 관리합니다."""

    def __init__(self, session_id: str, websocket: WebSocket, user: Optional[str | dict] = None):
        """역방향 프록시 세션을 초기화합니다.

        Args:
            session_id: 고유한 세션 식별자.
            websocket: WebSocket 연결.
            user: 인증된 사용자 정보 (있는 경우).
        """
        self.session_id = session_id
        self.websocket = websocket
        self.user = user
        self.server_info: Dict[str, Any] = {}
        self.connected_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.message_count = 0
        self.bytes_transferred = 0

    async def send_message(self, message: Dict[str, Any]) -> None:
        """클라이언트에게 메시지를 전송합니다.

        Args:
            message: 전송할 메시지 딕셔너리.
        """
        data = json.dumps(message)
        await self.websocket.send_text(data)
        self.bytes_transferred += len(data)
        self.last_activity = datetime.utcnow()

    async def receive_message(self) -> Dict[str, Any]:
        """클라이언트로부터 메시지를 수신합니다.

        Returns:
            파싱된 메시지 딕셔너리.
        """
        data = await self.websocket.receive_text()
        self.bytes_transferred += len(data)
        self.message_count += 1
        self.last_activity = datetime.utcnow()
        return json.loads(data)


class ReverseProxyManager:
    """모든 역방향 프록시 세션을 관리합니다."""

    def __init__(self):
        """관리자를 초기화합니다."""
        self.sessions: Dict[str, ReverseProxySession] = {}
        self._lock = asyncio.Lock()

    async def add_session(self, session: ReverseProxySession) -> None:
        """새로운 세션을 추가합니다.

        Args:
            session: 추가할 세션.
        """
        async with self._lock:
            self.sessions[session.session_id] = session
            LOGGER.info(f"Added reverse proxy session: {session.session_id}")

    async def remove_session(self, session_id: str) -> None:
        """세션을 제거합니다.

        Args:
            session_id: 제거할 세션 ID.
        """
        async with self._lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                LOGGER.info(f"Removed reverse proxy session: {session_id}")

    def get_session(self, session_id: str) -> Optional[ReverseProxySession]:
        """ID로 세션을 조회합니다.

        Args:
            session_id: 조회할 세션 ID.

        Returns:
            찾은 경우 세션, 그렇지 않으면 None.
        """
        return self.sessions.get(session_id)

    def list_sessions(self) -> list[Dict[str, Any]]:
        """모든 활성 세션을 목록으로 반환합니다.

        Returns:
            세션 정보 딕셔너리의 목록.

        Examples:
            >>> from fastapi import WebSocket
            >>> manager = ReverseProxyManager()
            >>> sessions = manager.list_sessions()
            >>> sessions
            []
            >>> isinstance(sessions, list)
            True
        """
        return [
            {
                "session_id": session.session_id,
                "server_info": session.server_info,
                "connected_at": session.connected_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "message_count": session.message_count,
                "bytes_transferred": session.bytes_transferred,
                "user": session.user if isinstance(session.user, str) else session.user.get("sub") if isinstance(session.user, dict) else None,
            }
            for session in self.sessions.values()
        ]


# Global manager instance
manager = ReverseProxyManager()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    db: Session = Depends(get_db),
):
    """역방향 프록시 연결을 위한 WebSocket 엔드포인트.

    Args:
        websocket: WebSocket 연결.
        db: 데이터베이스 세션.
    """
    await websocket.accept()

    # 1. 세션 ID 획득 (헤더에서 가져오거나 새로 생성)
    session_id = websocket.headers.get("X-Session-ID", uuid.uuid4().hex)

    # 2. 인증 확인
    user = None
    auth_header = websocket.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            # TODO: 토큰 검증 및 사용자 정보 획득
            pass
        except Exception as e:
            LOGGER.warning(f"Authentication failed: {e}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed")
            return

    # 3. 세션 생성 및 관리자에 등록
    session = ReverseProxySession(session_id, websocket, user)
    await manager.add_session(session)

    try:
        LOGGER.info(f"Reverse proxy connected: {session_id}")

        # 4. 메인 메시지 처리 루프
        while True:
            try:
                message = await session.receive_message()
                msg_type = message.get("type")

                if msg_type == "register":
                    # 서버 등록 처리
                    session.server_info = message.get("server", {})
                    LOGGER.info(f"Registered server for session {session_id}: {session.server_info.get('name')}")

                    # 등록 확인 응답 전송
                    await session.send_message({"type": "register_ack", "sessionId": session_id, "status": "success"})

                elif msg_type == "unregister":
                    # 서버 등록 해제 처리
                    LOGGER.info(f"Unregistering server for session {session_id}")
                    break

                elif msg_type == "heartbeat":
                    # 하트비트 응답 처리
                    await session.send_message({"type": "heartbeat", "sessionId": session_id, "timestamp": datetime.utcnow().isoformat()})

                elif msg_type in ("response", "notification"):
                    # 프록시된 서버로부터의 MCP 응답/알림 처리
                    # TODO: 적절한 MCP 클라이언트로 라우팅
                    LOGGER.debug(f"Received {msg_type} from session {session_id}")

                else:
                    LOGGER.warning(f"Unknown message type from session {session_id}: {msg_type}")

            except WebSocketDisconnect:
                # WebSocket 연결 해제 처리
                LOGGER.info(f"WebSocket disconnected: {session_id}")
                break
            except json.JSONDecodeError as e:
                # JSON 파싱 오류 처리
                LOGGER.error(f"Invalid JSON from session {session_id}: {e}")
                await session.send_message({"type": "error", "message": "Invalid JSON format"})
            except Exception as e:
                # 기타 예외 처리
                LOGGER.error(f"Error handling message from session {session_id}: {e}")
                await session.send_message({"type": "error", "message": str(e)})

    finally:
        # 세션 정리
        await manager.remove_session(session_id)
        LOGGER.info(f"Reverse proxy session ended: {session_id}")


@router.get("/sessions")
async def list_sessions(
    request: Request,
    _: str | dict = Depends(require_auth),
):
    """모든 활성 역방향 프록시 세션을 목록으로 반환합니다.

    Args:
        request: HTTP 요청.
        _: 인증된 사용자 정보 (인증 확인용).

    Returns:
        세션 정보 목록.
    """
    return {"sessions": manager.list_sessions(), "total": len(manager.sessions)}


@router.delete("/sessions/{session_id}")
async def disconnect_session(
    session_id: str,
    request: Request,
    _: str | dict = Depends(require_auth),
):
    """역방향 프록시 세션을 연결 해제합니다.

    Args:
        session_id: 연결 해제할 세션 ID.
        request: HTTP 요청.
        _: 인증된 사용자 정보 (인증 확인용).

    Returns:
        연결 해제 상태.

    Raises:
        HTTPException: 세션을 찾을 수 없는 경우.
    """
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session {session_id} not found")

    # WebSocket 연결 종료 및 세션 제거
    await session.websocket.close()
    await manager.remove_session(session_id)

    return {"status": "disconnected", "session_id": session_id}


@router.post("/sessions/{session_id}/request")
async def send_request_to_session(
    session_id: str,
    mcp_request: Dict[str, Any],
    request: Request,
    _: str | dict = Depends(require_auth),
):
    """역방향 프록시 세션에 MCP 요청을 전송합니다.

    Args:
        session_id: 요청을 전송할 세션 ID.
        mcp_request: 전송할 MCP 요청.
        request: HTTP 요청.
        _: 인증된 사용자 정보 (인증 확인용).

    Returns:
        요청 확인 응답.

    Raises:
        HTTPException: 세션을 찾을 수 없거나 요청이 실패한 경우.
    """
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session {session_id} not found")

    # 역방향 프록시 envelope로 요청을 감싸기
    message = {"type": "request", "sessionId": session_id, "payload": mcp_request}

    try:
        # 메시지 전송 및 응답 반환
        await session.send_message(message)
        return {"status": "sent", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to send request: {e}")


@router.get("/sse/{session_id}")
async def sse_endpoint(
    session_id: str,
    request: Request,
):
    """역방향 프록시 세션에서 메시지를 수신하는 SSE 엔드포인트.

    Args:
        session_id: 구독할 세션 ID.
        request: HTTP 요청.

    Returns:
        SSE 스트림.

    Raises:
        HTTPException: 세션을 찾을 수 없는 경우.
    """
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session {session_id} not found")

    async def event_generator():
        """SSE 이벤트를 생성합니다.

        Yields:
            dict: SSE 이벤트 데이터.
        """
        try:
            # 초기 연결 이벤트 전송
            yield {"event": "connected", "data": json.dumps({"sessionId": session_id, "serverInfo": session.server_info})}

            # TODO: SSE 전송을 위한 메시지 큐 구현
            while not await request.is_disconnected():
                await asyncio.sleep(30)  # 연결 유지용 keepalive
                yield {"event": "keepalive", "data": json.dumps({"timestamp": datetime.utcnow().isoformat()})}

        except asyncio.CancelledError:
            # 연결 취소 예외 처리 (정상적인 연결 종료)
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
