# MCP Gateway Handlers - 요청 처리 핸들러 가이드

## 개요

`handlers/` 폴더는 MCP Gateway의 특정 프로토콜 요청을 처리하는 핸들러 컴포넌트를 포함합니다. 현재 샘플링 요청을 처리하는 핸들러가 구현되어 있습니다.

## 핸들러 구조 개요

```bash
handlers/
├── __init__.py                     # 핸들러 모듈 초기화
└── sampling.py                     # MCP 샘플링 요청 핸들러
```

## Sampling Handler (`sampling.py`)

**역할**: MCP 샘플링 프로토콜을 통한 LLM 상호작용 처리
**주요 기능**:

- 모델 선택 및 선호도 기반 최적화
- 메시지 생성 및 샘플링
- 컨텍스트 관리 및 검증
- 모의 샘플링 기능

### 지원되는 모델 및 특성

```python
class SamplingHandler:
    def __init__(self):
        # 모델별 특성 점수: (비용 효율성, 속도, 지능)
        self._supported_models = {
            "claude-3-haiku": (0.8, 0.9, 0.7),    # 저비용, 고속, 중간 지능
            "claude-3-sonnet": (0.5, 0.7, 0.9),   # 중간 비용, 중간 속도, 고지능
            "claude-3-opus": (0.2, 0.5, 1.0),     # 고비용, 저속, 최고 지능
            "gemini-1.5-pro": (0.6, 0.8, 0.8),    # 중간 비용, 고속, 고지능
        }
```

### 모델 선택 알고리즘

#### 선호도 기반 모델 선택

```python
def _select_model(self, preferences: ModelPreferences) -> str:
    """사용자 선호도에 기반하여 최적의 모델 선택

    Args:
        preferences: 비용, 속도, 지능 우선순위

    Returns:
        선택된 모델 이름
    """
    if not preferences:
        return "claude-3-haiku"  # 기본 모델

    # 각 모델의 가중 점수 계산
    best_model = None
    best_score = -1

    for model, (cost, speed, intelligence) in self._supported_models.items():
        score = (
            cost * preferences.cost_priority +
            speed * preferences.speed_priority +
            intelligence * preferences.intelligence_priority
        )

        if score > best_score:
            best_score = score
            best_model = model

    return best_model or "claude-3-haiku"
```

#### 모델 선택 예시

```python
# 비용 우선 사용자의 모델 선택
cost_priority_prefs = ModelPreferences(
    cost_priority=0.8,
    speed_priority=0.1,
    intelligence_priority=0.1
)
# 결과: "claude-3-haiku" (가장 저비용 효율적)

# 지능 우선 사용자의 모델 선택
intelligence_priority_prefs = ModelPreferences(
    cost_priority=0.1,
    speed_priority=0.2,
    intelligence_priority=0.7
)
# 결과: "claude-3-opus" (가장 고지능)
```

### 메시지 검증 및 처리

#### 메시지 구조 검증

```python
def _validate_message(self, message: Dict[str, Any]) -> bool:
    """MCP 메시지 구조 검증

    Args:
        message: 검증할 메시지

    Returns:
        유효성 여부
    """
    required_fields = ["role", "content"]

    # 필수 필드 확인
    for field in required_fields:
        if field not in message:
            return False

    # 역할(Role) 검증
    if message["role"] not in ["user", "assistant", "system"]:
        return False

    # 콘텐츠 구조 검증
    content = message["content"]
    if not isinstance(content, dict):
        return False

    # 콘텐츠 타입 검증
    if content.get("type") not in ["text", "image"]:
        return False

    return True
```

#### 샘플링 요청 처리

```python
async def create_message(
    self,
    db: Session,
    messages: List[Dict[str, Any]],
    model_preferences: Optional[ModelPreferences] = None,
    max_tokens: int = 1000
) -> CreateMessageResult:
    """샘플링 요청 처리 및 응답 생성

    Args:
        db: 데이터베이스 세션
        messages: 입력 메시지 목록
        model_preferences: 모델 선호도
        max_tokens: 최대 토큰 수

    Returns:
        샘플링 결과
    """
    # 메시지 검증
    for message in messages:
        if not self._validate_message(message):
            raise SamplingError(f"Invalid message format: {message}")

    # 모델 선택
    selected_model = self._select_model(model_preferences)

    # 컨텍스트 제한 확인
    if len(messages) > self._max_context_length:
        # 오래된 메시지 제거
        messages = messages[-self._max_context_length:]

    # 실제 샘플링 수행 (또는 모의)
    if self._use_mock_sampling:
        response_text = self._mock_sample(messages)
    else:
        response_text = await self._real_sample(messages, selected_model, max_tokens)

    # 결과 구성
    result = CreateMessageResult(
        role=Role.assistant,
        content=TextContent(type="text", text=response_text),
        model=selected_model,
        stop_reason="end_turn"
    )

    return result
```

### 모의 샘플링 기능

#### 개발 및 테스트용 모의 응답 생성

```python
def _mock_sample(self, messages: List[Dict[str, Any]]) -> str:
    """개발 및 테스트용 모의 샘플링

    Args:
        messages: 입력 메시지 목록

    Returns:
        모의 응답 텍스트
    """
    # 마지막 사용자 메시지 추출
    last_user_message = None
    for message in reversed(messages):
        if message["role"] == "user":
            last_user_message = message
            break

    if not last_user_message:
        return "Hello! How can I help you today?"

    user_text = ""
    if isinstance(last_user_message["content"], dict):
        user_text = last_user_message["content"].get("text", "")
    elif isinstance(last_user_message["content"], str):
        user_text = last_user_message["content"]

    # 간단한 응답 생성
    responses = [
        f"You said: {user_text}",
        f"I understand you're asking about: {user_text}",
        f"That's an interesting point about: {user_text}",
        f"Let me think about: {user_text}"
    ]

    import random
    base_response = random.choice(responses)

    return base_response + "\n\nHere is my response..."
```

### 컨텍스트 관리

#### 대화 컨텍스트 제한

```python
# 최대 컨텍스트 길이 설정
self._max_context_length = 50  # 메시지 수 제한

def _manage_context(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """대화 컨텍스트 관리

    Args:
        messages: 전체 메시지 목록

    Returns:
        제한된 컨텍스트의 메시지 목록
    """
    if len(messages) <= self._max_context_length:
        return messages

    # 최근 메시지만 유지
    return messages[-self._max_context_length:]
```

### 에러 처리 및 로깅

#### 샘플링 에러 클래스

```python
class SamplingError(Exception):
    """샘플링 관련 에러 베이스 클래스"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}
```

#### 포괄적 에러 처리

```python
async def create_message(self, db: Session, messages: List[Dict[str, Any]], **kwargs) -> CreateMessageResult:
    try:
        # 샘플링 로직
        return await self._perform_sampling(messages, **kwargs)
    except SamplingError as e:
        logger.error(f"Sampling error: {e}", extra=e.details)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in sampling: {e}")
        raise SamplingError(f"Internal sampling error: {str(e)}")
```

### 성능 모니터링

#### 샘플링 메트릭 수집

```python
async def create_message(self, db: Session, messages: List[Dict[str, Any]], **kwargs) -> CreateMessageResult:
    import time
    start_time = time.time()

    try:
        result = await self._perform_sampling(messages, **kwargs)

        # 메트릭 기록
        duration = time.time() - start_time
        self._record_metrics(
            model=result.model,
            duration=duration,
            input_tokens=len(str(messages)),
            output_tokens=len(result.content.text)
        )

        return result
    except Exception as e:
        # 에러 메트릭 기록
        self._record_error_metrics(str(e))
        raise
```

### 설정 및 초기화

#### 핸들러 초기화

```python
async def initialize(self) -> None:
    """핸들러 초기화"""
    self._use_mock_sampling = settings.use_mock_sampling
    self._max_context_length = settings.max_context_length

    logger.info("Sampling handler initialized", extra={
        "mock_sampling": self._use_mock_sampling,
        "max_context": self._max_context_length,
        "supported_models": list(self._supported_models.keys())
    })
```

#### 종료 처리

```python
async def shutdown(self) -> None:
    """핸들러 종료"""
    # 리소스 정리
    self._supported_models.clear()

    logger.info("Sampling handler shutdown complete")
```

## 사용 예시

### 기본 샘플링

```python
from mcpgateway.handlers.sampling import SamplingHandler
from mcpgateway.models import ModelPreferences

# 핸들러 초기화
handler = SamplingHandler()
await handler.initialize()

# 메시지 준비
messages = [
    {"role": "user", "content": {"type": "text", "text": "Hello, how are you?"}}
]

# 기본 설정으로 샘플링
result = await handler.create_message(db_session, messages)
print(f"Response: {result.content.text}")
print(f"Model used: {result.model}")

# 종료
await handler.shutdown()
```

### 선호도 기반 모델 선택

```python
# 고성능 모델 선호
preferences = ModelPreferences(
    cost_priority=0.1,
    speed_priority=0.2,
    intelligence_priority=0.7
)

result = await handler.create_message(
    db_session,
    messages,
    model_preferences=preferences,
    max_tokens=2000
)
```

### 모의 샘플링 모드

```python
# 개발 환경에서 모의 응답 사용
import os
os.environ['USE_MOCK_SAMPLING'] = 'true'

handler = SamplingHandler()
await handler.initialize()

# 빠른 테스트를 위한 모의 응답
result = await handler.create_message(db_session, messages)
print(result.content.text)  # "You said: Hello, how are you?..."
```

## 확장 및 커스터마이징

### 사용자 정의 모델 추가

```python
class CustomSamplingHandler(SamplingHandler):
    def __init__(self):
        super().__init__()
        # 사용자 정의 모델 추가
        self._supported_models.update({
            "custom-model-v1": (0.7, 0.8, 0.6),
            "custom-model-v2": (0.4, 0.6, 0.8),
        })

    async def _real_sample(self, messages, model, max_tokens):
        # 사용자 정의 모델에 대한 실제 샘플링 구현
        if model.startswith("custom-model"):
            return await self._call_custom_model_api(messages, model, max_tokens)
        else:
            return await super()._real_sample(messages, model, max_tokens)
```

### 커스텀 검증 로직

```python
class StrictSamplingHandler(SamplingHandler):
    def _validate_message(self, message):
        # 엄격한 검증
        if not super()._validate_message(message):
            return False

        # 추가 검증: 메시지 길이 제한
        content = message.get("content", {})
        if isinstance(content, dict) and "text" in content:
            if len(content["text"]) > 10000:  # 10000자 제한
                return False

        return True
```

## 결론

handlers/ 폴더의 SamplingHandler는 MCP Gateway의 LLM 상호작용을 담당하는 핵심 컴포넌트입니다:

- **지능적 모델 선택**: 비용, 속도, 지능 우선순위 기반 최적화
- **강력한 검증**: 메시지 구조 및 콘텐츠 검증
- **유연한 샘플링**: 실제 API와 모의 모드 지원
- **효율적 컨텍스트 관리**: 메모리 사용량 최적화
- **포괄적 에러 처리**: 안정적인 오류 대응
- **성능 모니터링**: 메트릭 수집 및 분석

이 핸들러를 통해 게이트웨이는 다양한 사용 사례와 요구사항에 맞는 지능적인 샘플링 서비스를 제공할 수 있습니다.
