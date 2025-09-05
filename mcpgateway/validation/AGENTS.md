# MCP Gateway Validation - 입력 검증 및 정규화 시스템 가이드

## 개요

`validation/` 폴더는 MCP Gateway의 입력 데이터 검증과 정규화 기능을 담당하는 모듈을 포함합니다. JSON-RPC 프로토콜 검증과 태그 정규화를 통해 시스템의 안정성과 일관성을 보장합니다.

## 검증 구조 개요

```
validation/
├── __init__.py                     # 검증 모듈 초기화
├── jsonrpc.py                      # JSON-RPC 프로토콜 검증
└── tags.py                         # 태그 검증 및 정규화
```

## JSON-RPC 검증 (`jsonrpc.py`)

**역할**: JSON-RPC 2.0 프로토콜 준수 여부 검증 및 에러 처리
**주요 기능**:
- 요청/응답 구조 검증
- 표준 에러 코드 관리
- 프로토콜 버전 확인
- 메시지 포맷팅

### JSONRPCError 예외 클래스

#### 에러 구조 및 관리

```python
class JSONRPCError(Exception):
    """JSON-RPC 프로토콜 에러"""

    def __init__(
        self,
        code: int,
        message: str,
        data: Optional[Any] = None,
        request_id: Optional[Union[str, int]] = None,
    ):
        self.code = code
        self.message = message
        self.data = data
        self.request_id = request_id
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """JSON-RPC 에러 응답 딕셔너리 변환"""
        error = {"code": self.code, "message": self.message}
        if self.data is not None:
            error["data"] = self.data

        return {
            "jsonrpc": "2.0",
            "error": error,
            "request_id": self.request_id
        }
```

### 표준 JSON-RPC 에러 코드

```python
# 사전 정의된 표준 에러 코드들
PARSE_ERROR = -32700        # 유효하지 않은 JSON
INVALID_REQUEST = -32600    # 유효하지 않은 요청 객체
METHOD_NOT_FOUND = -32601   # 메소드를 찾을 수 없음
INVALID_PARAMS = -32602     # 유효하지 않은 메소드 파라미터
INTERNAL_ERROR = -32603     # 내부 JSON-RPC 에러
```

#### 에러 코드별 상세 설명

| 에러 코드 | 이름 | 설명 | 사용 사례 |
|-----------|------|------|-----------|
| -32700 | Parse Error | 유효하지 않은 JSON 수신 | malformed JSON, encoding issues |
| -32600 | Invalid Request | 유효하지 않은 요청 객체 | missing jsonrpc field, invalid structure |
| -32601 | Method Not Found | 요청한 메소드 없음 | unknown tool/resource name |
| -32602 | Invalid Params | 파라미터 유효하지 않음 | wrong parameter types, missing required fields |
| -32603 | Internal Error | 서버 내부 에러 | database errors, service failures |

### 요청 검증 함수들

#### 기본 요청 검증

```python
def validate_request(request: Dict[str, Any]) -> None:
    """JSON-RPC 요청의 기본 구조 검증

    Args:
        request: 검증할 요청 딕셔너리

    Raises:
        JSONRPCError: 검증 실패 시
    """
    # 필수 필드 확인
    if not isinstance(request, dict):
        raise JSONRPCError(INVALID_REQUEST, "Request must be a JSON object")

    # jsonrpc 버전 확인
    if request.get("jsonrpc") != "2.0":
        raise JSONRPCError(INVALID_REQUEST, "Invalid JSON-RPC version")

    # method 필드 확인
    if "method" not in request:
        raise JSONRPCError(INVALID_REQUEST, "Missing method field")

    if not isinstance(request["method"], str):
        raise JSONRPCError(INVALID_REQUEST, "Method must be a string")

    # params 필드 검증 (선택적)
    if "params" in request:
        if not isinstance(request["params"], (dict, list)):
            raise JSONRPCError(INVALID_PARAMS, "Params must be an object or array")
```

#### 알림(Notification) 검증

```python
def validate_notification(notification: Dict[str, Any]) -> None:
    """JSON-RPC 알림 검증 (응답 불필요)

    Args:
        notification: 검증할 알림 딕셔너리

    Raises:
        JSONRPCError: 검증 실패 시
    """
    # 기본 요청 검증 실행
    validate_request(notification)

    # 알림은 id 필드를 가지면 안 됨
    if "id" in notification:
        raise JSONRPCError(
            INVALID_REQUEST,
            "Notifications must not have an id field"
        )
```

#### 배치 요청 검증

```python
def validate_batch_request(batch: List[Dict[str, Any]]) -> None:
    """JSON-RPC 배치 요청 검증

    Args:
        batch: 요청 배치 리스트

    Raises:
        JSONRPCError: 검증 실패 시
    """
    if not isinstance(batch, list):
        raise JSONRPCError(INVALID_REQUEST, "Batch request must be an array")

    if not batch:
        raise JSONRPCError(INVALID_REQUEST, "Batch request cannot be empty")

    if len(batch) > MAX_BATCH_SIZE:
        raise JSONRPCError(
            INVALID_REQUEST,
            f"Batch size exceeds maximum ({MAX_BATCH_SIZE})"
        )

    # 각 요청 개별 검증
    for request in batch:
        validate_request(request)
```

### 응답 검증 함수들

#### 성공 응답 검증

```python
def validate_success_response(response: Dict[str, Any]) -> None:
    """JSON-RPC 성공 응답 검증

    Args:
        response: 검증할 응답 딕셔너리

    Raises:
        JSONRPCError: 검증 실패 시
    """
    # 필수 필드 확인
    required_fields = ["jsonrpc", "result", "id"]
    for field in required_fields:
        if field not in response:
            raise JSONRPCError(
                INVALID_REQUEST,
                f"Success response missing required field: {field}"
            )

    # jsonrpc 버전 확인
    if response["jsonrpc"] != "2.0":
        raise JSONRPCError(INVALID_REQUEST, "Invalid JSON-RPC version")
```

#### 에러 응답 검증

```python
def validate_error_response(response: Dict[str, Any]) -> None:
    """JSON-RPC 에러 응답 검증

    Args:
        response: 검증할 에러 응답 딕셔너리

    Raises:
        JSONRPCError: 검증 실패 시
    """
    # 필수 필드 확인
    required_fields = ["jsonrpc", "error", "id"]
    for field in required_fields:
        if field not in response:
            raise JSONRPCError(
                INVALID_REQUEST,
                f"Error response missing required field: {field}"
            )

    # 에러 객체 구조 검증
    error = response["error"]
    if not isinstance(error, dict):
        raise JSONRPCError(INVALID_REQUEST, "Error must be an object")

    # 에러 필드 검증
    if "code" not in error or "message" not in error:
        raise JSONRPCError(
            INVALID_REQUEST,
            "Error object must have code and message fields"
        )

    if not isinstance(error["code"], int):
        raise JSONRPCError(INVALID_REQUEST, "Error code must be an integer")

    if not isinstance(error["message"], str):
        raise JSONRPCError(INVALID_REQUEST, "Error message must be a string")
```

## 태그 검증 (`tags.py`)

**역할**: 엔티티 태그의 검증과 정규화
**주요 기능**:
- 태그 포맷 검증
- 자동 정규화 (소문자, 공백 처리)
- 길이 제한 적용
- 중복 제거

### TagValidator 클래스

#### 태그 검증 규칙

```python
class TagValidator:
    """태그 검증 및 정규화 유틸리티"""

    MIN_LENGTH = 2              # 최소 길이
    MAX_LENGTH = 50             # 최대 길이
    ALLOWED_PATTERN = r"^[a-z0-9]([a-z0-9\-\:\.]*[a-z0-9])?$"  # 허용 패턴
```

#### 태그 정규화

```python
@staticmethod
def normalize(tag: str) -> str:
    """태그를 표준 포맷으로 정규화

    Args:
        tag: 정규화할 태그 문자열

    Returns:
        정규화된 태그 문자열
    """
    # 공백 제거 및 소문자 변환
    normalized = tag.strip().lower()

    # 공백을 하이픈으로 변환
    normalized = "-".join(normalized.split())

    # 언더스코어를 하이픈으로 변환 (일관성)
    normalized = normalized.replace("_", "-")

    return normalized
```

#### 정규화 예시

```python
# 입력 → 출력 매핑
"Finance" → "finance"
"  ANALYTICS  " → "analytics"
"data  processing" → "data-processing"
"Machine Learning" → "machine-learning"
"under_score" → "under-score"
```

#### 태그 검증

```python
@staticmethod
def validate(tag: str) -> bool:
    """단일 태그의 유효성 검증

    Args:
        tag: 검증할 태그 문자열

    Returns:
        유효성 여부
    """
    # 길이 검증
    if not (TagValidator.MIN_LENGTH <= len(tag) <= TagValidator.MAX_LENGTH):
        return False

    # 패턴 검증 (영문자, 숫자, 하이픈, 콜론, 점만 허용)
    import re
    if not re.match(TagValidator.ALLOWED_PATTERN, tag):
        return False

    return True
```

#### 태그 리스트 검증 및 정규화

```python
@staticmethod
def validate_list(tags: List[str]) -> List[str]:
    """태그 리스트 검증 및 정규화

    Args:
        tags: 검증할 태그 리스트

    Returns:
        유효하고 정규화된 태그 리스트 (중복 제거)
    """
    normalized_tags = []

    for tag in tags:
        if not isinstance(tag, str):
            continue

        # 정규화
        normalized = TagValidator.normalize(tag)

        # 검증
        if TagValidator.validate(normalized):
            normalized_tags.append(normalized)

    # 중복 제거 및 정렬
    return sorted(list(set(normalized_tags)))
```

### 검증 규칙 상세

#### 허용되는 문자 패턴
- **시작과 끝**: 영문자 또는 숫자만 허용
- **중간**: 영문자, 숫자, 하이픈(`-`), 콜론(`:`), 점(`.`) 허용
- **길이**: 2-50자 사이
- **대소문자**: 자동 소문자 변환
- **공백**: 하이픈으로 변환

#### 유효한 태그 예시
```python
# 유효한 태그들
"analytics"      # 기본 영문
"data-2024"      # 하이픈 포함
"ml.model.v1"    # 점 포함
"api:v2"         # 콜론 포함
"tool-123"       # 숫자 포함
```

#### 유효하지 않은 태그 예시
```python
# 유효하지 않은 태그들
"a"              # 너무 짧음 (1자)
""               # 빈 문자열
"-tag"           # 하이픈으로 시작
"tag-"           # 하이픈으로 끝
"tag space"      # 공백 포함 (원본 형태)
"tag@domain"     # 허용되지 않는 특수문자
```

## 검증 사용 예시

### JSON-RPC 요청 검증

```python
from mcpgateway.validation.jsonrpc import validate_request, JSONRPCError

def handle_jsonrpc_request(request_data):
    try:
        # 요청 구조 검증
        validate_request(request_data)

        # 비즈니스 로직 처리
        result = process_request(request_data)

        return {
            "jsonrpc": "2.0",
            "result": result,
            "id": request_data.get("id")
        }

    except JSONRPCError as e:
        # 검증 실패 시 표준 에러 응답
        return e.to_dict()
```

### 태그 검증 및 정규화

```python
from mcpgateway.validation.tags import TagValidator

def create_entity_with_tags(name, raw_tags):
    # 태그 정규화 및 검증
    normalized_tags = TagValidator.validate_list(raw_tags)

    # 유효하지 않은 태그 로깅
    invalid_count = len(raw_tags) - len(normalized_tags)
    if invalid_count > 0:
        logger.warning(f"{invalid_count} invalid tags filtered out")

    # 엔티티 생성
    entity = Entity(name=name, tags=normalized_tags)
    return entity
```

### 배치 검증

```python
def validate_entity_batch(entities):
    """엔티티 배치 검증"""
    valid_entities = []
    errors = []

    for i, entity in enumerate(entities):
        try:
            # JSON 구조 검증
            if not isinstance(entity, dict):
                raise JSONRPCError(INVALID_PARAMS, "Entity must be an object")

            # 태그 검증
            if "tags" in entity:
                entity["tags"] = TagValidator.validate_list(entity["tags"])

            valid_entities.append(entity)

        except JSONRPCError as e:
            errors.append({
                "index": i,
                "error": e.to_dict()
            })

    return valid_entities, errors
```

## 에러 처리 및 로깅

### 검증 에러 포맷팅

```python
def format_validation_error(error: JSONRPCError) -> Dict[str, Any]:
    """검증 에러를 구조화된 포맷으로 변환"""
    return {
        "type": "validation_error",
        "code": error.code,
        "message": error.message,
        "details": error.data,
        "timestamp": datetime.utcnow().isoformat(),
        "request_id": error.request_id
    }
```

### 검증 메트릭 수집

```python
class ValidationMetrics:
    """검증 관련 메트릭 수집"""

    def __init__(self):
        self.requests_validated = 0
        self.requests_failed = 0
        self.tags_normalized = 0
        self.validation_errors = {}

    def record_validation(self, success: bool, error_type: Optional[str] = None):
        """검증 결과 기록"""
        if success:
            self.requests_validated += 1
        else:
            self.requests_failed += 1
            if error_type:
                self.validation_errors[error_type] = self.validation_errors.get(error_type, 0) + 1

    def get_stats(self) -> Dict[str, Any]:
        """검증 통계 반환"""
        total = self.requests_validated + self.requests_failed
        success_rate = self.requests_validated / total if total > 0 else 0

        return {
            "total_validated": total,
            "success_rate": success_rate,
            "error_breakdown": self.validation_errors,
            "tags_normalized": self.tags_normalized
        }
```

## 테스트 및 검증

### 단위 테스트 예시

```python
import pytest
from mcpgateway.validation.jsonrpc import validate_request, JSONRPCError, INVALID_REQUEST

def test_valid_request():
    """유효한 요청 검증"""
    request = {
        "jsonrpc": "2.0",
        "method": "test_method",
        "params": {"key": "value"},
        "id": 1
    }

    # 검증 통과해야 함
    validate_request(request)

def test_invalid_request_missing_jsonrpc():
    """jsonrpc 필드 누락 검증"""
    request = {
        "method": "test_method",
        "id": 1
    }

    with pytest.raises(JSONRPCError) as exc_info:
        validate_request(request)

    assert exc_info.value.code == INVALID_REQUEST
    assert "Invalid JSON-RPC version" in exc_info.value.message
```

### 태그 검증 테스트

```python
def test_tag_normalization():
    """태그 정규화 테스트"""
    test_cases = [
        ("Finance", "finance"),
        ("  ANALYTICS  ", "analytics"),
        ("data  processing", "data-processing"),
        ("Machine Learning", "machine-learning"),
    ]

    for input_tag, expected in test_cases:
        result = TagValidator.normalize(input_tag)
        assert result == expected

def test_tag_validation():
    """태그 유효성 검증 테스트"""
    valid_tags = ["analytics", "data-2024", "ml.model.v1", "api:v2"]
    invalid_tags = ["a", "", "-tag", "tag-", "tag space", "tag@domain"]

    for tag in valid_tags:
        assert TagValidator.validate(tag)

    for tag in invalid_tags:
        assert not TagValidator.validate(tag)
```

## 결론

validation/ 폴더의 컴포넌트들은 MCP Gateway의 데이터 무결성과 프로토콜 준수를 보장하는 핵심 요소입니다:

- **JSON-RPC 검증**: 프로토콜 준수와 표준 에러 처리
- **태그 정규화**: 일관된 태그 포맷과 검증
- **강력한 에러 처리**: 명확한 에러 메시지와 코드
- **성능 모니터링**: 검증 메트릭 수집 및 분석
- **포괄적 테스트**: 다양한 엣지 케이스 커버

이러한 검증 시스템을 통해 게이트웨이는 신뢰할 수 있는 API 서비스를 제공하고, 잘못된 입력으로 인한 시스템 장애를 방지할 수 있습니다.

## 탐색

- **⬆️ mcpgateway**: [../AGENTS.md](../AGENTS.md)
- **⬆️ 프로젝트 루트**: [../../AGENTS.md](../../AGENTS.md)
