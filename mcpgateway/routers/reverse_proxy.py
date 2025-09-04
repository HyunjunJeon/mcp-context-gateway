# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/routers/reverse_proxy.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

역방향 프록시 연결을 처리하는 FastAPI 라우터.

이 모듈은 역방향 프록시 클라이언트가 로컬 MCP 서버를 게이트웨이를 통해
터널링할 수 있도록 WebSocket 및 SSE 엔드포인트를 제공합니다.
"""

# Standard - 표준 라이브러리
import asyncio  # 비동기 작업 지원
from datetime import datetime  # 시간 처리
import json  # JSON 데이터 처리
from typing import Any, Dict, Optional  # 타입 힌트
import uuid  # 고유 식별자 생성

# Third-Party - 외부 라이브러리
from fastapi import APIRouter, Depends, HTTPException, Request, status, WebSocket, WebSocketDisconnect  # FastAPI 컴포넌트
from fastapi.responses import StreamingResponse  # 스트리밍 응답
from sqlalchemy.orm import Session  # 데이터베이스 세션

# First-Party - 내부 모듈
from mcpgateway.db import get_db  # 데이터베이스 세션 의존성
from mcpgateway.services.logging_service import LoggingService  # 로깅 서비스
from mcpgateway.utils.verify_credentials import require_auth  # 인증 검증

# 로깅 서비스 초기화 - 역방향 프록시 관련 로그 기록
logging_service = LoggingService()
LOGGER = logging_service.get_logger("mcpgateway.routers.reverse_proxy")

# 역방향 프록시 라우터 생성 - /reverse-proxy 경로의 모든 엔드포인트 처리
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
        # 세션 기본 정보 설정
        self.session_id = session_id
        self.websocket = websocket
        self.user = user

        # 서버 정보 및 통계 초기화
        self.server_info: Dict[str, Any] = {}  # 연결된 서버의 메타데이터
        self.connected_at = datetime.utcnow()  # 세션 연결 시간
        self.last_activity = datetime.utcnow()  # 마지막 활동 시간
        self.message_count = 0  # 처리한 메시지 수
        self.bytes_transferred = 0  # 전송된 총 바이트 수

    async def send_message(self, message: Dict[str, Any]) -> None:
        """클라이언트에게 메시지를 전송합니다.

        Args:
            message: 전송할 메시지 딕셔너리.
        """
        # 메시지를 JSON 문자열로 변환
        data = json.dumps(message)
        # WebSocket을 통해 텍스트 메시지 전송
        await self.websocket.send_text(data)
        # 전송 바이트 수 및 마지막 활동 시간 업데이트
        self.bytes_transferred += len(data)
        self.last_activity = datetime.utcnow()

    async def receive_message(self) -> Dict[str, Any]:
        """클라이언트로부터 메시지를 수신합니다.

        Returns:
            파싱된 메시지 딕셔너리.
        """
        # WebSocket으로부터 텍스트 메시지 수신
        data = await self.websocket.receive_text()
        # 수신 바이트 수, 메시지 수, 마지막 활동 시간 업데이트
        self.bytes_transferred += len(data)
        self.message_count += 1
        self.last_activity = datetime.utcnow()
        # JSON 문자열을 파싱하여 딕셔너리로 반환
        return json.loads(data)


class ReverseProxyManager:
    """모든 역방향 프록시 세션을 관리합니다."""

    def __init__(self):
        """역방향 프록시 세션 관리자를 초기화합니다."""
        self.sessions: Dict[str, ReverseProxySession] = {}  # 세션 ID를 키로 하는 세션 저장소
        self._lock = asyncio.Lock()  # 동시성 제어를 위한 비동기 락

    async def add_session(self, session: ReverseProxySession) -> None:
        """새로운 세션을 추가합니다.

        Args:
            session: 추가할 세션.
        """
        # 동시성 제어를 위해 락을 획득
        async with self._lock:
            # 세션을 저장소에 추가
            self.sessions[session.session_id] = session
            LOGGER.info(f"Added reverse proxy session: {session.session_id}")

    async def remove_session(self, session_id: str) -> None:
        """세션을 제거합니다.

        Args:
            session_id: 제거할 세션 ID.
        """
        # 동시성 제어를 위해 락을 획득
        async with self._lock:
            # 세션이 존재하는 경우에만 제거
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
        # 세션 저장소에서 해당 ID의 세션을 조회 (존재하지 않으면 None 반환)
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
        # 모든 활성 세션에 대해 정보를 수집하여 목록으로 반환
        return [
            {
                "session_id": session.session_id,  # 세션 고유 ID
                "server_info": session.server_info,  # 연결된 서버 정보
                "connected_at": session.connected_at.isoformat(),  # 연결 시각 (ISO 형식)
                "last_activity": session.last_activity.isoformat(),  # 마지막 활동 시각
                "message_count": session.message_count,  # 처리한 메시지 수
                "bytes_transferred": session.bytes_transferred,  # 전송된 바이트 수
                # 사용자 정보 (문자열 또는 JWT 클레임에서 추출)
                "user": session.user if isinstance(session.user, str) else session.user.get("sub") if isinstance(session.user, dict) else None,
            }
            for session in self.sessions.values()  # 모든 세션 순회
        ]


# 전역 세션 관리자 인스턴스 - 모든 WebSocket 연결에서 공유
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
