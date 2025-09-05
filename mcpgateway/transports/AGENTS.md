# MCP Gateway Transports Layer - 통신 프로토콜 구현 가이드

## 개요

`transports/` 폴더는 MCP Gateway와 클라이언트 간의 다양한 통신 프로토콜을 구현합니다. 이 계층은 MCP 프로토콜 메시지를 다양한 전송 방식을 통해 안전하고 효율적으로 주고받을 수 있게 해줍니다.

## 전송 계층 구조 개요

```
transports/
├── __init__.py                     # 전송 계층 초기화
├── base.py                         # 추상 전송 기본 클래스
├── sse_transport.py                # Server-Sent Events 전송
├── websocket_transport.py          # WebSocket 전송
├── stdio_transport.py              # 표준 입출력 전송
└── streamablehttp_transport.py     # 스트리밍 HTTP 전송
```

## 추상 기본 클래스 (`base.py`)

**역할**: 모든 전송 구현의 공통 인터페이스 정의
**주요 기능**:
- 연결 관리 표준화
- 메시지 송수신 인터페이스 정의
- 연결 상태 모니터링

**핵심 인터페이스**:
```python
class Transport(ABC):
    """모든 전송 구현의 추상 기본 클래스"""

    @abstractmethod
    async def connect(self) -> None:
        """전송 연결 초기화"""

    @abstractmethod
    async def disconnect(self) -> None:
        """전송 연결 종료"""

    @abstractmethod
    async def send_message(self, message: Dict[str, Any]) -> None:
        """메시지 전송"""

    @abstractmethod
    async def receive_message(self) -> AsyncGenerator[Dict[str, Any], None]:
        """메시지 수신 (비동기 제너레이터)"""

    @abstractmethod
    async def is_connected(self) -> bool:
        """연결 상태 확인"""
```

## 전송 구현 방식

### 1. Server-Sent Events (SSE) 전송 (`sse_transport.py`)

**역할**: 서버에서 클라이언트로의 단방향 스트리밍 통신
**주요 특징**:
- 서버 → 클라이언트 단방향 스트리밍
- HTTP 기반으로 방화벽 친화적
- 자동 재연결 지원
- 세션 기반 메시지 관리

**적용 사례**:
- 실시간 알림 및 업데이트
- 로그 스트리밍
- 상태 모니터링

**구현 특징**:
```python
class SSETransport(Transport):
    def __init__(self, base_url: str = None):
        self._base_url = base_url or f"http://{settings.host}:{settings.port}"
        self._connected = False
        self._message_queue = asyncio.Queue()
        self._client_gone = asyncio.Event()
        self._session_id = str(uuid.uuid4())

    async def connect(self) -> None:
        """SSE 연결 설정"""
        self._connected = True
        logger.info(f"SSE transport connected: {self._session_id}")

    async def send_message(self, message: Dict[str, Any]) -> None:
        """메시지를 큐에 추가하여 클라이언트로 스트리밍"""
        await self._message_queue.put(message)

    async def receive_message(self) -> AsyncGenerator[Dict[str, Any], None]:
        """큐에서 메시지를 가져와 스트리밍"""
        try:
            while not self._client_gone.is_set():
                try:
                    message = await asyncio.wait_for(
                        self._message_queue.get(),
                        timeout=1.0
                    )
                    yield message
                except asyncio.TimeoutError:
                    # Keep-alive 메시지 전송
                    yield {"type": "keepalive", "timestamp": datetime.utcnow()}
        except Exception as e:
            logger.error(f"SSE message reception error: {e}")
            raise
```

**장점**:
- HTTP 표준 지원으로 호환성 높음
- 방화벽 및 프록시 친화적
- 구현이 상대적으로 단순
- 브라우저 네이티브 지원

**단점**:
- 클라이언트 → 서버 방향 통신 제한적
- 메시지 순서 보장 어려움
- 연결 끊김 시 메시지 손실 가능성

### 2. WebSocket 전송 (`websocket_transport.py`)

**역할**: 양방향 실시간 통신
**주요 특징**:
- 완전한 양방향 통신
- 낮은 오버헤드와 지연 시간
- 실시간 상호작용 지원
- 연결 상태 모니터링

**적용 사례**:
- 실시간 협업 애플리케이션
- 게임 및 채팅 시스템
- 라이브 데이터 피드

**구현 특징**:
```python
class WebSocketTransport(Transport):
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self._connected = False
        self._receive_task = None

    async def connect(self) -> None:
        """WebSocket 연결 수락"""
        await self.websocket.accept()
        self._connected = True
        logger.info("WebSocket transport connected")

    async def send_message(self, message: Dict[str, Any]) -> None:
        """JSON 메시지를 WebSocket으로 전송"""
        try:
            await self.websocket.send_json(message)
        except Exception as e:
            logger.error(f"WebSocket send error: {e}")
            raise

    async def receive_message(self) -> AsyncGenerator[Dict[str, Any], None]:
        """WebSocket에서 메시지 수신"""
        try:
            while self._connected:
                try:
                    message = await self.websocket.receive_json()
                    yield message
                except WebSocketDisconnect:
                    logger.info("WebSocket disconnected")
                    break
                except Exception as e:
                    logger.error(f"WebSocket receive error: {e}")
                    break
        finally:
            await self.disconnect()
```

**장점**:
- 양방향 실시간 통신
- 낮은 오버헤드
- 메시지 순서 보장
- 연결 상태 실시간 모니터링

**단점**:
- 방화벽 및 프록시에서 차단될 수 있음
- HTTP 폴백이 어려움
- 구현 복잡도 높음

### 3. 표준 입출력 전송 (`stdio_transport.py`)

**역할**: 프로세스 간 통신을 위한 STDIO 기반 전송
**주요 특징**:
- 프로세스 간 직접 통신
- 외부 MCP 서버와의 통합
- 간단한 프로세스 관리

**적용 사례**:
- 외부 MCP 서버 실행
- 테스트 환경
- 로컬 개발

**구현 특징**:
```python
class StdioTransport(Transport):
    def __init__(self, command: str):
        self.command = command
        self.process = None
        self._connected = False

    async def connect(self) -> None:
        """자식 프로세스 시작"""
        self.process = await asyncio.create_subprocess_exec(
            *self.command.split(),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        self._connected = True

    async def send_message(self, message: Dict[str, Any]) -> None:
        """JSON 메시지를 프로세스 stdin으로 전송"""
        if self.process and self.process.stdin:
            json_message = json.dumps(message) + "\n"
            self.process.stdin.write(json_message.encode())
            await self.process.stdin.drain()

    async def receive_message(self) -> AsyncGenerator[Dict[str, Any], None]:
        """프로세스 stdout에서 메시지 읽기"""
        if self.process and self.process.stdout:
            while self._connected:
                line = await self.process.stdout.readline()
                if not line:
                    break
                try:
                    message = json.loads(line.decode().strip())
                    yield message
                except json.JSONDecodeError:
                    continue
```

**장점**:
- 프로세스 간 직접 통신
- 외부 의존성 최소화
- 디버깅 및 테스트 용이

**단점**:
- 네트워크 통신 불가
- 확장성 제한
- 프로세스 관리 복잡

### 4. 스트리밍 HTTP 전송 (`streamablehttp_transport.py`)

**역할**: HTTP 기반 양방향 스트리밍 통신
**주요 특징**:
- HTTP/1.1 및 HTTP/2 지원
- 양방향 스트리밍
- REST API와의 호환성

**적용 사례**:
- REST API 통합
- 클라우드 서비스 연동
- 엔터프라이즈 환경

**구현 특징**:
```python
class StreamableHTTPTransport(Transport):
    def __init__(self, base_url: str, session_id: str = None):
        self.base_url = base_url
        self.session_id = session_id or str(uuid.uuid4())
        self._http_client = httpx.AsyncClient(timeout=30.0)

    async def connect(self) -> None:
        """HTTP 연결 준비"""
        self._connected = True

    async def send_message(self, message: Dict[str, Any]) -> None:
        """HTTP POST로 메시지 전송"""
        async with self._http_client.stream(
            "POST",
            f"{self.base_url}/message",
            json=message,
            headers={"X-Session-ID": self.session_id}
        ) as response:
            response.raise_for_status()

    async def receive_message(self) -> AsyncGenerator[Dict[str, Any], None]:
        """HTTP GET으로 스트리밍 응답 수신"""
        async with self._http_client.stream(
            "GET",
            f"{self.base_url}/stream",
            headers={"X-Session-ID": self.session_id}
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.strip():
                    try:
                        message = json.loads(line)
                        yield message
                    except json.JSONDecodeError:
                        continue
```

**장점**:
- HTTP 표준 완전 지원
- 방화벽 및 프록시 친화적
- REST API와의 통합 용이

**단점**:
- WebSocket보다 오버헤드 높음
- 실시간성이 WebSocket보다 낮음

## 전송 방식 비교

| 특징 | SSE | WebSocket | STDIO | Streamable HTTP |
|------|-----|-----------|-------|-----------------|
| **방향성** | 서버→클라이언트 | 양방향 | 양방향 | 양방향 |
| **프로토콜** | HTTP | WS | STDIO | HTTP |
| **실시간성** | 높음 | 매우 높음 | 높음 | 중간 |
| **호환성** | 우수 | 제한적 | 낮음 | 우수 |
| **복잡도** | 낮음 | 중간 | 낮음 | 중간 |
| **확장성** | 중간 | 높음 | 낮음 | 높음 |

## 전송 선택 가이드라인

### SSE (Server-Sent Events) 선택 시기:
- 서버에서 클라이언트로의 단방향 데이터 스트리밍이 주된 경우
- 브라우저 기반 클라이언트가 많은 경우
- 방화벽 제한이 엄격한 기업 환경
- 간단한 구현이 필요한 경우

### WebSocket 선택 시기:
- 실시간 양방향 통신이 필요한 경우
- 낮은 지연 시간이 중요한 경우
- 연결 상태 모니터링이 필요한 경우
- 게임이나 협업 애플리케이션

### STDIO 선택 시기:
- 외부 프로세스와의 통합이 필요한 경우
- 로컬 개발 및 테스트 환경
- 간단한 프로세스 간 통신
- 네트워크 오버헤드를 피해야 하는 경우

### Streamable HTTP 선택 시기:
- 기존 REST API와의 통합이 필요한 경우
- 엔터프라이즈 환경의 보안 정책 준수
- HTTP/2의 멀티플렉싱 기능 활용
- 클라우드 서비스와의 연동

## 전송 계층 아키텍처 패턴

### 1. 팩토리 패턴을 통한 전송 생성
```python
class TransportFactory:
    @staticmethod
    def create_transport(transport_type: str, **kwargs) -> Transport:
        if transport_type == "sse":
            return SSETransport(**kwargs)
        elif transport_type == "websocket":
            return WebSocketTransport(**kwargs)
        elif transport_type == "stdio":
            return StdioTransport(**kwargs)
        elif transport_type == "streamablehttp":
            return StreamableHTTPTransport(**kwargs)
        else:
            raise ValueError(f"Unknown transport type: {transport_type}")
```

### 2. 어댑터 패턴을 통한 통합
```python
class MCPTransportAdapter:
    def __init__(self, transport: Transport):
        self.transport = transport
        self._message_handlers = []

    async def send_mcp_message(self, message: MCPMessage) -> None:
        """MCP 메시지를 전송 계층에 맞게 변환하여 전송"""
        transport_message = self._mcp_to_transport(message)
        await self.transport.send_message(transport_message)

    async def receive_mcp_message(self) -> AsyncGenerator[MCPMessage, None]:
        """전송 계층 메시지를 MCP 메시지로 변환"""
        async for transport_message in self.transport.receive_message():
            mcp_message = self._transport_to_mcp(transport_message)
            yield mcp_message
```

### 3. 디코레이터 패턴을 통한 기능 확장
```python
class LoggingTransport:
    def __init__(self, transport: Transport):
        self._transport = transport

    async def connect(self) -> None:
        logger.info("Connecting to transport")
        await self._transport.connect()
        logger.info("Transport connected")

    async def send_message(self, message: Dict[str, Any]) -> None:
        logger.debug(f"Sending message: {message}")
        await self._transport.send_message(message)

    async def disconnect(self) -> None:
        logger.info("Disconnecting from transport")
        await self._transport.disconnect()
```

## 오류 처리 및 복원력

### 연결 실패 처리
```python
async def _handle_connection_error(self, error: Exception) -> None:
    """연결 오류 처리 및 재시도 로직"""
    logger.error(f"Connection error: {error}")

    if isinstance(error, (ConnectionError, TimeoutError)):
        # 지수 백오프를 통한 재연결 시도
        await self._retry_connection()

    elif isinstance(error, AuthenticationError):
        # 인증 오류 처리
        await self._handle_auth_error()

    else:
        # 기타 오류 처리
        await self._handle_generic_error(error)
```

### 메시지 검증 및 오류 처리
```python
async def _validate_message(self, message: Dict[str, Any]) -> bool:
    """메시지 유효성 검증"""
    try:
        # 필수 필드 확인
        if not all(key in message for key in ['id', 'method']):
            return False

        # 메시지 스키마 검증
        if not self._validate_schema(message):
            return False

        return True
    except Exception as e:
        logger.error(f"Message validation error: {e}")
        return False
```

## 성능 최적화

### 연결 풀 관리
```python
class ConnectionPool:
    def __init__(self, max_connections: int = 100):
        self.max_connections = max_connections
        self._pool = asyncio.Queue(maxsize=max_connections)

    async def get_connection(self) -> Transport:
        """연결 풀에서 사용 가능한 연결 가져오기"""
        if self._pool.empty():
            return await self._create_connection()
        return await self._pool.get()

    async def return_connection(self, connection: Transport) -> None:
        """연결을 풀에 반환"""
        if self._pool.qsize() < self.max_connections:
            await self._pool.put(connection)
        else:
            await connection.disconnect()
```

### 메시지 배치 처리
```python
class MessageBatcher:
    def __init__(self, batch_size: int = 10, flush_interval: float = 1.0):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._batch = []
        self._last_flush = time.time()

    async def add_message(self, message: Dict[str, Any]) -> None:
        """메시지를 배치에 추가"""
        self._batch.append(message)

        if (len(self._batch) >= self.batch_size or
            time.time() - self._last_flush >= self.flush_interval):
            await self._flush_batch()

    async def _flush_batch(self) -> None:
        """배치를 전송하고 초기화"""
        if self._batch:
            await self._transport.send_batch(self._batch)
            self._batch.clear()
            self._last_flush = time.time()
```

## 모니터링 및 관측성

### 메트릭 수집
```python
class TransportMetrics:
    def __init__(self):
        self.messages_sent = 0
        self.messages_received = 0
        self.connection_errors = 0
        self.average_response_time = 0.0

    async def record_send(self, message_size: int) -> None:
        """메시지 전송 메트릭 기록"""
        self.messages_sent += 1
        # Prometheus 메트릭 업데이트
        MESSAGES_SENT.inc()
        MESSAGE_SIZE.observe(message_size)

    async def record_receive(self, response_time: float) -> None:
        """메시지 수신 메트릭 기록"""
        self.messages_received += 1
        self.average_response_time = (
            self.average_response_time + response_time
        ) / 2
```

### 헬스 체크
```python
async def health_check(self) -> Dict[str, Any]:
    """전송 계층 헬스 체크"""
    return {
        "transport_type": self.__class__.__name__,
        "connected": await self.is_connected(),
        "messages_sent": self._metrics.messages_sent,
        "messages_received": self._metrics.messages_received,
        "connection_errors": self._metrics.connection_errors,
        "average_response_time": self._metrics.average_response_time,
        "uptime": time.time() - self._start_time
    }
```

## 결론

transports/ 폴더는 MCP Gateway의 통신 기반을 제공하며, 다음과 같은 특징을 가집니다:

- **다양성**: 4가지 주요 전송 방식을 지원
- **확장성**: 새로운 전송 방식의 추가가 용이
- **안정성**: 오류 처리 및 재시도 로직 내장
- **성능**: 연결 풀 및 메시지 배치 처리로 최적화
- **호환성**: 다양한 네트워크 환경 및 요구사항 지원

이러한 설계를 통해 MCP Gateway는 다양한 클라이언트 환경과 네트워크 조건에서 안정적이고 효율적인 통신을 제공할 수 있습니다.

## 탐색

- **⬆️ mcpgateway**: [../AGENTS.md](../AGENTS.md)
- **⬆️ 프로젝트 루트**: [../../AGENTS.md](../../AGENTS.md)
