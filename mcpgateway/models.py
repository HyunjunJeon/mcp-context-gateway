# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/models.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

MCP 프로토콜 타입 정의.
이 모듈은 사양에 따라 모든 핵심 MCP 프로토콜 타입을 정의합니다.
포함되는 내용:
  - 메시지 콘텐츠 타입 (텍스트, 이미지, 리소스)
  - 도구 정의 및 스키마
  - 리소스 타입 및 템플릿
  - 프롬프트 구조
  - 프로토콜 초기화 타입
  - 샘플링 메시지 타입
  - 기능 정의

사용 예시:
    >>> from mcpgateway.models import Role, LogLevel, TextContent
    >>> Role.USER.value
    'user'
    >>> Role.ASSISTANT.value
    'assistant'
    >>> LogLevel.ERROR.value
    'error'
    >>> LogLevel.INFO.value
    'info'
    >>> content = TextContent(type='text', text='Hello')
    >>> content.text
    'Hello'
    >>> content.type
    'text'
"""

# Standard
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

# Third-Party
from pydantic import AnyHttpUrl, AnyUrl, BaseModel, ConfigDict, Field


class Role(str, Enum):
    """대화에서 메시지의 역할.

    Attributes:
        ASSISTANT (str): 어시스턴트의 역할을 나타냅니다.
        USER (str): 사용자의 역할을 나타냅니다.

    Examples:
        >>> Role.USER.value
        'user'
        >>> Role.ASSISTANT.value
        'assistant'
        >>> Role.USER == 'user'
        True
        >>> list(Role)
        [<Role.ASSISTANT: 'assistant'>, <Role.USER: 'user'>]
    """

    ASSISTANT = "assistant"
    USER = "user"


class LogLevel(str, Enum):
    """RFC 5424에 정의된 표준 syslog 심각도 수준.

    Attributes:
        DEBUG (str): 디버그 수준.
        INFO (str): 정보 수준.
        NOTICE (str): 알림 수준.
        WARNING (str): 경고 수준.
        ERROR (str): 오류 수준.
        CRITICAL (str): 심각 수준.
        ALERT (str): 경보 수준.
        EMERGENCY (str): 긴급 수준.
    """

    DEBUG = "debug"
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    ALERT = "alert"
    EMERGENCY = "emergency"


# Base content types
class TextContent(BaseModel):
    """메시지의 텍스트 콘텐츠.

    Attributes:
        type (Literal["text"]): 텍스트의 고정 콘텐츠 타입 식별자.
        text (str): 실제 텍스트 메시지.

    Examples:
        >>> content = TextContent(type='text', text='Hello World')
        >>> content.text
        'Hello World'
        >>> content.type
        'text'
        >>> content.model_dump()
        {'type': 'text', 'text': 'Hello World'}
    """

    type: Literal["text"]
    text: str


class JSONContent(BaseModel):
    """메시지의 JSON 콘텐츠.
    Attributes:
        type (Literal["text"]): 텍스트의 고정 콘텐츠 타입 식별자.
        json (dict): 실제 JSON 메시지.
    """

    type: Literal["text"]
    text: dict


class ImageContent(BaseModel):
    """메시지의 이미지 콘텐츠.

    Attributes:
        type (Literal["image"]): 이미지의 고정 콘텐츠 타입 식별자.
        data (bytes): 이미지의 바이너리 데이터.
        mime_type (str): 이미지의 MIME 타입 (예: "image/png").
    """

    type: Literal["image"]
    data: bytes
    mime_type: str


class ResourceContent(BaseModel):
    """임베드될 수 있는 리소스 콘텐츠.

    Attributes:
        type (Literal["resource"]): 리소스의 고정 콘텐츠 타입 식별자.
        uri (str): 리소스를 식별하는 URI.
        mime_type (Optional[str]): 알려진 경우 리소스의 MIME 타입.
        text (Optional[str]): 적용 가능한 경우 리소스의 텍스트 표현.
        blob (Optional[bytes]): 적용 가능한 경우 리소스의 바이너리 데이터.
    """

    type: Literal["resource"]
    uri: str
    mime_type: Optional[str] = None
    text: Optional[str] = None
    blob: Optional[bytes] = None


ContentType = Union[TextContent, JSONContent, ImageContent, ResourceContent]


# Reference types - needed early for completion
class PromptReference(BaseModel):
    """Reference to a prompt or prompt template.

    Attributes:
        type (Literal["ref/prompt"]): The fixed reference type identifier for prompts.
        name (str): The unique name of the prompt.
    """

    type: Literal["ref/prompt"]
    name: str


class ResourceReference(BaseModel):
    """Reference to a resource or resource template.

    Attributes:
        type (Literal["ref/resource"]): The fixed reference type identifier for resources.
        uri (str): The URI of the resource.
    """

    type: Literal["ref/resource"]
    uri: str


# Completion types
class CompleteRequest(BaseModel):
    """Request for completion suggestions.

    Attributes:
        ref (Union[PromptReference, ResourceReference]): A reference to a prompt or resource.
        argument (Dict[str, str]): A dictionary containing arguments for the completion.
    """

    ref: Union[PromptReference, ResourceReference]
    argument: Dict[str, str]


class CompleteResult(BaseModel):
    """Result for a completion request.

    Attributes:
        completion (Dict[str, Any]): A dictionary containing the completion results.
    """

    completion: Dict[str, Any] = Field(..., description="Completion results")


# Implementation info
class Implementation(BaseModel):
    """MCP implementation information.

    Attributes:
        name (str): The name of the implementation.
        version (str): The version of the implementation.
    """

    name: str
    version: str


# Model preferences
class ModelHint(BaseModel):
    """Hint for model selection.

    Attributes:
        name (Optional[str]): An optional hint for the model name.
    """

    name: Optional[str] = None


class ModelPreferences(BaseModel):
    """Server preferences for model selection.

    Attributes:
        cost_priority (float): Priority for cost efficiency (0 to 1).
        speed_priority (float): Priority for speed (0 to 1).
        intelligence_priority (float): Priority for intelligence (0 to 1).
        hints (List[ModelHint]): A list of model hints.
    """

    cost_priority: float = Field(ge=0, le=1)
    speed_priority: float = Field(ge=0, le=1)
    intelligence_priority: float = Field(ge=0, le=1)
    hints: List[ModelHint] = []


# Capability types
class ClientCapabilities(BaseModel):
    """Capabilities that a client may support.

    Attributes:
        roots (Optional[Dict[str, bool]]): Capabilities related to root management.
        sampling (Optional[Dict[str, Any]]): Capabilities related to LLM sampling.
        experimental (Optional[Dict[str, Dict[str, Any]]]): Experimental capabilities.
    """

    roots: Optional[Dict[str, bool]] = None
    sampling: Optional[Dict[str, Any]] = None
    experimental: Optional[Dict[str, Dict[str, Any]]] = None


class ServerCapabilities(BaseModel):
    """Capabilities that a server may support.

    Attributes:
        prompts (Optional[Dict[str, bool]]): Capability for prompt support.
        resources (Optional[Dict[str, bool]]): Capability for resource support.
        tools (Optional[Dict[str, bool]]): Capability for tool support.
        logging (Optional[Dict[str, Any]]): Capability for logging support.
        experimental (Optional[Dict[str, Dict[str, Any]]]): Experimental capabilities.
    """

    prompts: Optional[Dict[str, bool]] = None
    resources: Optional[Dict[str, bool]] = None
    tools: Optional[Dict[str, bool]] = None
    logging: Optional[Dict[str, Any]] = None
    experimental: Optional[Dict[str, Dict[str, Any]]] = None


# Initialization types
class InitializeRequest(BaseModel):
    """Initial request sent from the client to the server.

    Attributes:
        protocol_version (str): The protocol version (alias: protocolVersion).
        capabilities (ClientCapabilities): The client's capabilities.
        client_info (Implementation): The client's implementation information (alias: clientInfo).

    Note:
        The alias settings allow backward compatibility with older Pydantic versions.
    """

    protocol_version: str = Field(..., alias="protocolVersion")
    capabilities: ClientCapabilities
    client_info: Implementation = Field(..., alias="clientInfo")

    model_config = ConfigDict(
        populate_by_name=True,
    )


class InitializeResult(BaseModel):
    """Server's response to the initialization request.

    Attributes:
        protocol_version (str): The protocol version used.
        capabilities (ServerCapabilities): The server's capabilities.
        server_info (Implementation): The server's implementation information.
        instructions (Optional[str]): Optional instructions for the client.
    """

    protocol_version: str = Field(..., alias="protocolVersion")
    capabilities: ServerCapabilities = Field(..., alias="capabilities")
    server_info: Implementation = Field(..., alias="serverInfo")
    instructions: Optional[str] = Field(None, alias="instructions")

    model_config = ConfigDict(
        populate_by_name=True,
    )


# Message types
class Message(BaseModel):
    """A message in a conversation.

    Attributes:
        role (Role): The role of the message sender.
        content (ContentType): The content of the message.
    """

    role: Role
    content: ContentType


class SamplingMessage(BaseModel):
    """A message used in LLM sampling requests.

    Attributes:
        role (Role): The role of the sender.
        content (ContentType): The content of the sampling message.
    """

    role: Role
    content: ContentType


# Sampling types for the client features
class CreateMessageResult(BaseModel):
    """Result from a sampling/createMessage request.

    Attributes:
        content (Union[TextContent, ImageContent]): The generated content.
        model (str): The model used for generating the content.
        role (Role): The role associated with the content.
        stop_reason (Optional[str]): An optional reason for why sampling stopped.
    """

    content: Union[TextContent, ImageContent]
    model: str
    role: Role
    stop_reason: Optional[str] = None


# Prompt types
class PromptArgument(BaseModel):
    """An argument that can be passed to a prompt.

    Attributes:
        name (str): The name of the argument.
        description (Optional[str]): An optional description of the argument.
        required (bool): Whether the argument is required. Defaults to False.
    """

    name: str
    description: Optional[str] = None
    required: bool = False


class Prompt(BaseModel):
    """A prompt template offered by the server.

    Attributes:
        name (str): The unique name of the prompt.
        description (Optional[str]): A description of the prompt.
        arguments (List[PromptArgument]): A list of expected prompt arguments.
    """

    name: str
    description: Optional[str] = None
    arguments: List[PromptArgument] = []


class PromptResult(BaseModel):
    """Result of rendering a prompt template.

    Attributes:
        messages (List[Message]): The list of messages produced by rendering the prompt.
        description (Optional[str]): An optional description of the rendered result.
    """

    messages: List[Message]
    description: Optional[str] = None


# Tool types
class Tool(BaseModel):
    """호출될 수 있는 도구.

    Attributes:
        name (str): 도구의 고유 이름.
        url (AnyHttpUrl): 도구의 URL.
        description (Optional[str]): 도구에 대한 설명.
        integrationType (str): 도구의 통합 타입 (예: MCP 또는 REST).
        requestType (str): 도구 호출에 사용되는 HTTP 메소드 (GET, POST, PUT, DELETE, SSE, STDIO).
        headers (Dict[str, Any]): HTTP 헤더를 나타내는 JSON 객체.
        input_schema (Dict[str, Any]): 도구의 입력을 검증하기 위한 JSON 스키마.
        annotations (Optional[Dict[str, Any]]): 동작 힌트를 위한 도구 어노테이션.
        auth_type (Optional[str]): 사용되는 인증 타입 ("basic", "bearer", 또는 None).
        auth_username (Optional[str]): 기본 인증을 위한 사용자 이름.
        auth_password (Optional[str]): 기본 인증을 위한 비밀번호.
        auth_token (Optional[str]): Bearer 인증을 위한 토큰.
    """

    name: str
    url: AnyHttpUrl
    description: Optional[str] = None
    integration_type: str = "MCP"
    request_type: str = "SSE"
    headers: Dict[str, Any] = Field(default_factory=dict)
    input_schema: Dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})
    annotations: Optional[Dict[str, Any]] = Field(default_factory=dict, description="동작 힌트를 위한 도구 어노테이션")
    auth_type: Optional[str] = None
    auth_username: Optional[str] = None
    auth_password: Optional[str] = None
    auth_token: Optional[str] = None


class ToolResult(BaseModel):
    """도구 호출의 결과.

    Attributes:
        content (List[ContentType]): 도구가 반환한 콘텐츠 항목들의 목록.
        is_error (bool): 도구 호출이 오류를 초래했는지 나타내는 플래그.
    """

    content: List[ContentType]
    is_error: bool = False


# Resource types
class Resource(BaseModel):
    """서버에서 사용할 수 있는 리소스.

    Attributes:
        uri (str): 리소스의 고유 URI.
        name (str): 사람이 읽을 수 있는 리소스 이름.
        description (Optional[str]): 리소스에 대한 설명.
        mime_type (Optional[str]): 리소스의 MIME 타입.
        size (Optional[int]): 리소스의 크기.
    """

    uri: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None
    size: Optional[int] = None


class ResourceTemplate(BaseModel):
    """리소스 URI를 구성하기 위한 템플릿.

    Attributes:
        uri_template (str): URI 템플릿 문자열.
        name (str): 템플릿의 고유 이름.
        description (Optional[str]): 템플릿에 대한 설명.
        mime_type (Optional[str]): 템플릿과 연관된 MIME 타입.
    """

    uri_template: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None


class ListResourceTemplatesResult(BaseModel):
    """클라이언트의 resources/templates/list 요청에 대한 서버의 응답.

    Attributes:
        meta (Optional[Dict[str, Any]]): 메타데이터를 위한 예약된 속성.
        next_cursor (Optional[str]): 다음 결과 페이지의 페이지네이션 커서.
        resource_templates (List[ResourceTemplate]): 리소스 템플릿 목록.
    """

    meta: Optional[Dict[str, Any]] = Field(
        None, alias="_meta", description="이 결과 속성은 프로토콜에 의해 예약되어 클라이언트와 서버가 응답에 추가 메타데이터를 첨부할 수 있도록 합니다."
    )
    next_cursor: Optional[str] = Field(None, description="마지막으로 반환된 결과 이후의 페이지네이션 위치를 나타내는 불투명 토큰.\n존재하는 경우 더 많은 결과를 사용할 수 있습니다.")
    resource_templates: List[ResourceTemplate] = Field(default_factory=list, description="서버에서 사용할 수 있는 리소스 템플릿 목록")

    model_config = ConfigDict(
        populate_by_name=True,
    )


# Root types
class FileUrl(AnyUrl):
    """A specialized URL type for local file-scheme resources.

    Key characteristics
    -------------------
    * Scheme restricted - only the "file" scheme is permitted
      (e.g. file:///path/to/file.txt).
    * No host required - "file" URLs typically omit a network host;
      therefore, the host component is not mandatory.
    * String-friendly equality - developers naturally expect
      FileUrl("file:///data") == "file:///data" to evaluate True.
      AnyUrl (Pydantic) does not implement that, so we override
      __eq__ to compare against plain strings transparently.
      Hash semantics are kept consistent by delegating to the parent class.

    Examples
    --------
    >>> url = FileUrl("file:///etc/hosts")
    >>> url.scheme
    'file'
    >>> url == "file:///etc/hosts"
    True
    >>> {"path": url}  # hashable
    {'path': FileUrl('file:///etc/hosts')}

    Notes
    -----
    The override does not interfere with comparisons to other
    AnyUrl/FileUrl instances; those still use the superclass
    implementation.
    """

    # Restrict to the "file" scheme and omit host requirement
    allowed_schemes = {"file"}
    host_required = False

    def __eq__(self, other):  # type: ignore[override]
        """Return True when other is an equivalent URL or string.

        If other is a str it is coerced with str(self) for comparison;
        otherwise defer to AnyUrl's comparison.

        Args:
            other (Any): The object to compare against. May be a str, FileUrl, or AnyUrl.

        Returns:
            bool: True if the other value is equal to this URL, either as a string
            or as another URL object. False otherwise.
        """
        if isinstance(other, str):
            return str(self) == other
        return super().__eq__(other)

    # Keep hashing behaviour aligned with equality
    __hash__ = AnyUrl.__hash__


class Root(BaseModel):
    """A root directory or file.

    Attributes:
        uri (Union[FileUrl, AnyUrl]): The unique identifier for the root.
        name (Optional[str]): An optional human-readable name.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    uri: Union[FileUrl, AnyUrl] = Field(..., description="Unique identifier for the root")
    name: Optional[str] = Field(None, description="Optional human-readable name")


# Progress types
class ProgressToken(BaseModel):
    """Token for associating progress notifications.

    Attributes:
        value (Union[str, int]): The token value.
    """

    value: Union[str, int]


class Progress(BaseModel):
    """Progress update for long-running operations.

    Attributes:
        progress_token (ProgressToken): The token associated with the progress update.
        progress (float): The current progress value.
        total (Optional[float]): The total progress value, if known.
    """

    progress_token: ProgressToken
    progress: float
    total: Optional[float] = None


# JSON-RPC types
class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 request.

    Attributes:
        jsonrpc (Literal["2.0"]): The JSON-RPC version.
        id (Optional[Union[str, int]]): The request identifier.
        method (str): The method name.
        params (Optional[Dict[str, Any]]): The parameters for the request.
    """

    jsonrpc: Literal["2.0"]
    id: Optional[Union[str, int]] = None
    method: str
    params: Optional[Dict[str, Any]] = None


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 response.

    Attributes:
        jsonrpc (Literal["2.0"]): The JSON-RPC version.
        id (Optional[Union[str, int]]): The request identifier.
        result (Optional[Any]): The result of the request.
        error (Optional[Dict[str, Any]]): The error object if an error occurred.
    """

    jsonrpc: Literal["2.0"]
    id: Optional[Union[str, int]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 error.

    Attributes:
        code (int): The error code.
        message (str): A short description of the error.
        data (Optional[Any]): Additional data about the error.
    """

    code: int
    message: str
    data: Optional[Any] = None


# Global configuration types
class GlobalConfig(BaseModel):
    """Global server configuration.

    Attributes:
        passthrough_headers (Optional[List[str]]): List of headers allowed to be passed through globally
    """

    passthrough_headers: Optional[List[str]] = Field(default=None, description="List of headers allowed to be passed through globally")


# Transport message types
class SSEEvent(BaseModel):
    """Server-Sent Events message.

    Attributes:
        id (Optional[str]): The event identifier.
        event (Optional[str]): The event type.
        data (str): The event data.
        retry (Optional[int]): The retry timeout in milliseconds.
    """

    id: Optional[str] = None
    event: Optional[str] = None
    data: str
    retry: Optional[int] = None


class WebSocketMessage(BaseModel):
    """WebSocket protocol message.

    Attributes:
        type (str): The type of the WebSocket message.
        data (Any): The message data.
    """

    type: str
    data: Any


# Notification types
class ResourceUpdateNotification(BaseModel):
    """Notification of resource changes.

    Attributes:
        method (Literal["notifications/resources/updated"]): The notification method.
        uri (str): The URI of the updated resource.
    """

    method: Literal["notifications/resources/updated"]
    uri: str


class ResourceListChangedNotification(BaseModel):
    """Notification of resource list changes.

    Attributes:
        method (Literal["notifications/resources/list_changed"]): The notification method.
    """

    method: Literal["notifications/resources/list_changed"]


class PromptListChangedNotification(BaseModel):
    """Notification of prompt list changes.

    Attributes:
        method (Literal["notifications/prompts/list_changed"]): The notification method.
    """

    method: Literal["notifications/prompts/list_changed"]


class ToolListChangedNotification(BaseModel):
    """Notification of tool list changes.

    Attributes:
        method (Literal["notifications/tools/list_changed"]): The notification method.
    """

    method: Literal["notifications/tools/list_changed"]


class CancelledNotification(BaseModel):
    """Notification of request cancellation.

    Attributes:
        method (Literal["notifications/cancelled"]): The notification method.
        request_id (Union[str, int]): The ID of the cancelled request.
        reason (Optional[str]): An optional reason for cancellation.
    """

    method: Literal["notifications/cancelled"]
    request_id: Union[str, int]
    reason: Optional[str] = None


class ProgressNotification(BaseModel):
    """Notification of operation progress.

    Attributes:
        method (Literal["notifications/progress"]): The notification method.
        progress_token (ProgressToken): The token associated with the progress.
        progress (float): The current progress value.
        total (Optional[float]): The total progress value, if known.
    """

    method: Literal["notifications/progress"]
    progress_token: ProgressToken
    progress: float
    total: Optional[float] = None


class LoggingNotification(BaseModel):
    """Notification of log messages.

    Attributes:
        method (Literal["notifications/message"]): The notification method.
        level (LogLevel): The log level of the message.
        logger (Optional[str]): The logger name.
        data (Any): The log message data.
    """

    method: Literal["notifications/message"]
    level: LogLevel
    logger: Optional[str] = None
    data: Any


# Federation types
class FederatedTool(Tool):
    """A tool from a federated gateway.

    Attributes:
        gateway_id (str): The identifier of the gateway.
        gateway_name (str): The name of the gateway.
    """

    gateway_id: str
    gateway_name: str


class FederatedResource(Resource):
    """A resource from a federated gateway.

    Attributes:
        gateway_id (str): The identifier of the gateway.
        gateway_name (str): The name of the gateway.
    """

    gateway_id: str
    gateway_name: str


class FederatedPrompt(Prompt):
    """A prompt from a federated gateway.

    Attributes:
        gateway_id (str): The identifier of the gateway.
        gateway_name (str): The name of the gateway.
    """

    gateway_id: str
    gateway_name: str


class Gateway(BaseModel):
    """A federated gateway peer.

    Attributes:
        id (str): The unique identifier for the gateway.
        name (str): The name of the gateway.
        url (AnyHttpUrl): The URL of the gateway.
        capabilities (ServerCapabilities): The capabilities of the gateway.
        last_seen (Optional[datetime]): Timestamp when the gateway was last seen.
    """

    id: str
    name: str
    url: AnyHttpUrl
    capabilities: ServerCapabilities
    last_seen: Optional[datetime] = None
