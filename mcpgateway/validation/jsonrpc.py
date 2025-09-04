# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/validation/jsonrpc.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

JSON-RPC 검증 모듈.
https://www.jsonrpc.org/specification에 따른 JSON-RPC 2.0 요청 및 응답 검증 기능을 제공합니다.

포함 사항:
- 요청 검증
- 응답 검증
- 표준 에러 코드
- 에러 메시지 포맷팅

예시:
    >>> from mcpgateway.validation.jsonrpc import JSONRPCError, validate_request
    >>> error = JSONRPCError(-32600, "Invalid Request")
    >>> error.code
    -32600
    >>> error.message
    'Invalid Request'
    >>> validate_request({'jsonrpc': '2.0', 'method': 'test', 'id': 1})
    >>> validate_request({'jsonrpc': '2.0', 'method': 'test'})  # notification
    >>> try:
    ...     validate_request({'method': 'test'})  # missing jsonrpc
    ... except JSONRPCError as e:
    ...     e.code
    -32600
"""

# 표준 라이브러리 임포트
from typing import Any, Dict, Optional, Union


class JSONRPCError(Exception):
    """JSON-RPC 프로토콜 에러 클래스.

    JSON-RPC 2.0 사양에 따른 표준화된 에러를 표현합니다.
    """

    def __init__(
        self,
        code: int,
        message: str,
        data: Optional[Any] = None,
        request_id: Optional[Union[str, int]] = None,
    ):
        """JSON-RPC 에러를 초기화합니다.

        Args:
            code: 에러 코드 (정수)
            message: 에러 메시지 (문자열)
            data: 추가적인 에러 데이터 (선택사항)
            request_id: 요청 ID (선택사항)
        """
        # 에러 정보를 인스턴스 변수에 저장
        self.code = code
        self.message = message
        self.data = data
        self.request_id = request_id
        # 부모 Exception 클래스 초기화
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """에러를 JSON-RPC 에러 응답 딕셔너리로 변환합니다.

        Returns:
            JSON-RPC 에러 응답 딕셔너리

        Examples:
            기본 에러 (데이터 없음):
            >>> error = JSONRPCError(-32600, "Invalid Request", request_id=1)
            >>> error.to_dict()
            {'jsonrpc': '2.0', 'error': {'code': -32600, 'message': 'Invalid Request'}, 'request_id': 1}

            추가 데이터가 있는 에러:
            >>> error = JSONRPCError(-32602, "Invalid params", data={"param": "value"}, request_id="abc")
            >>> error.to_dict()
            {'jsonrpc': '2.0', 'error': {'code': -32602, 'message': 'Invalid params', 'data': {'param': 'value'}}, 'request_id': 'abc'}

            요청 ID 없는 에러 (파싱 에러용):
            >>> error = JSONRPCError(-32700, "Parse error", data="Unexpected EOF")
            >>> error.to_dict()
            {'jsonrpc': '2.0', 'error': {'code': -32700, 'message': 'Parse error', 'data': 'Unexpected EOF'}, 'request_id': None}

            복잡한 데이터가 있는 에러:
            >>> error = JSONRPCError(-32603, "Internal error", data={"details": ["error1", "error2"], "timestamp": 123456}, request_id=42)
            >>> sorted(error.to_dict()['error']['data']['details'])
            ['error1', 'error2']
        """
        # 기본 에러 객체 생성
        error = {"code": self.code, "message": self.message}
        # 추가 데이터가 있으면 포함
        if self.data is not None:
            error["data"] = self.data

        # JSON-RPC 2.0 표준 포맷의 응답 생성
        return {"jsonrpc": "2.0", "error": error, "request_id": self.request_id}


# 표준 JSON-RPC 에러 코드 정의
PARSE_ERROR = -32700  # 유효하지 않은 JSON
INVALID_REQUEST = -32600  # 유효하지 않은 요청 객체
METHOD_NOT_FOUND = -32601  # 메소드를 찾을 수 없음
INVALID_PARAMS = -32602  # 유효하지 않은 메소드 파라미터
INTERNAL_ERROR = -32603  # 내부 JSON-RPC 에러
SERVER_ERROR_START = -32000  # 서버 에러 코드 시작
SERVER_ERROR_END = -32099  # 서버 에러 코드 끝


def validate_request(request: Dict[str, Any]) -> None:
    """JSON-RPC 요청을 검증합니다.

    JSON-RPC 2.0 사양에 따라 요청 객체의 유효성을 검사합니다.

    Args:
        request: 검증할 요청 딕셔너리

    Raises:
        JSONRPCError: 요청이 유효하지 않은 경우

    Examples:
        유효한 요청:
        >>> validate_request({"jsonrpc": "2.0", "method": "ping", "id": 1})

        유효한 알림 (id 없음):
        >>> validate_request({"jsonrpc": "2.0", "method": "notify"})

        파라미터가 있는 유효한 요청:
        >>> validate_request({"jsonrpc": "2.0", "method": "add", "params": [1, 2], "id": 1})
        >>> validate_request({"jsonrpc": "2.0", "method": "add", "params": {"a": 1, "b": 2}, "id": 1})

        유효하지 않은 버전:
        >>> validate_request({"jsonrpc": "1.0", "method": "ping", "id": 1})  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        mcpgateway.validation.jsonrpc.JSONRPCError: Invalid JSON-RPC version

        메소드 누락:
        >>> validate_request({"jsonrpc": "2.0", "id": 1})  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        mcpgateway.validation.jsonrpc.JSONRPCError: Invalid or missing method

        빈 메소드:
        >>> validate_request({"jsonrpc": "2.0", "method": "", "id": 1})  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        mcpgateway.validation.jsonrpc.JSONRPCError: Invalid or missing method

        유효하지 않은 파라미터 타입:
        >>> validate_request({"jsonrpc": "2.0", "method": "test", "params": "invalid", "id": 1})  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        mcpgateway.validation.jsonrpc.JSONRPCError: Invalid params type

        유효하지 않은 ID 타입:
        >>> validate_request({"jsonrpc": "2.0", "method": "test", "id": True})  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        mcpgateway.validation.jsonrpc.JSONRPCError: Invalid request ID type
    """  # doctest: +ELLIPSIS
    # JSON-RPC 버전 확인 (2.0이어야 함)
    if request.get("jsonrpc") != "2.0":
        raise JSONRPCError(INVALID_REQUEST, "Invalid JSON-RPC version", request_id=request.get("id"))

    # 메소드 필드 검증 (필수, 문자열, 비어있지 않아야 함)
    method = request.get("method")
    if not isinstance(method, str) or not method:
        raise JSONRPCError(INVALID_REQUEST, "Invalid or missing method", request_id=request.get("id"))

    # 요청 ID 검증 (알림이 아닌 경우에만 해당)
    # ID는 문자열 또는 정수여야 하며, 불리언은 허용되지 않음
    if "id" in request:
        request_id = request["id"]
        if not isinstance(request_id, (str, int)) or isinstance(request_id, bool):
            raise JSONRPCError(INVALID_REQUEST, "Invalid request ID type", request_id=None)

    # 파라미터 검증 (존재하는 경우에만)
    # 파라미터는 객체(dict) 또는 배열(list)여야 함
    params = request.get("params")
    if params is not None:
        if not isinstance(params, (dict, list)):
            raise JSONRPCError(INVALID_REQUEST, "Invalid params type", request_id=request.get("id"))


def validate_response(response: Dict[str, Any]) -> None:
    """JSON-RPC 응답을 검증합니다.

    JSON-RPC 2.0 사양에 따라 응답 객체의 유효성을 검사합니다.

    Args:
        response: 검증할 응답 딕셔너리

    Raises:
        JSONRPCError: 응답이 유효하지 않은 경우

    Examples:
        유효한 성공 응답:
        >>> validate_response({"jsonrpc": "2.0", "result": 42, "id": 1})

        유효한 에러 응답:
        >>> validate_response({"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": 1})

        null 결과가 있는 유효한 응답:
        >>> validate_response({"jsonrpc": "2.0", "result": None, "id": 1})

        null id가 있는 유효한 응답 (ID 파싱 중 에러):
        >>> validate_response({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None})

        유효하지 않은 버전:
        >>> validate_response({"jsonrpc": "1.0", "result": 42, "id": 1})  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        mcpgateway.validation.jsonrpc.JSONRPCError: Invalid JSON-RPC version

        ID 누락:
        >>> validate_response({"jsonrpc": "2.0", "result": 42})  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        mcpgateway.validation.jsonrpc.JSONRPCError: Missing response ID

        유효하지 않은 ID 타입 (불리언):
        >>> validate_response({"jsonrpc": "2.0", "result": 42, "id": True})  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        mcpgateway.validation.jsonrpc.JSONRPCError: Invalid response ID type

        유효하지 않은 ID 타입 (리스트):
        >>> validate_response({"jsonrpc": "2.0", "result": 42, "id": [1, 2]})  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        mcpgateway.validation.jsonrpc.JSONRPCError: Invalid response ID type

        결과와 에러 모두 누락:
        >>> validate_response({"jsonrpc": "2.0", "id": 1})  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        mcpgateway.validation.jsonrpc.JSONRPCError: Response must contain either result or error

        결과와 에러 모두 존재:
        >>> validate_response({"jsonrpc": "2.0", "result": 42, "error": {"code": -1, "message": "Error"}, "id": 1})  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        mcpgateway.validation.jsonrpc.JSONRPCError: Response cannot contain both result and error

        유효하지 않은 에러 객체 타입:
        >>> validate_response({"jsonrpc": "2.0", "error": "Invalid error", "id": 1})  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        mcpgateway.validation.jsonrpc.JSONRPCError: Invalid error object type

        에러 코드 누락:
        >>> validate_response({"jsonrpc": "2.0", "error": {"message": "Error"}, "id": 1})  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        mcpgateway.validation.jsonrpc.JSONRPCError: Error must contain code and message

        에러 메시지 누락:
        >>> validate_response({"jsonrpc": "2.0", "error": {"code": -32601}, "id": 1})  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        mcpgateway.validation.jsonrpc.JSONRPCError: Error must contain code and message

        유효하지 않은 에러 코드 타입:
        >>> validate_response({"jsonrpc": "2.0", "error": {"code": "invalid", "message": "Error"}, "id": 1})  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        mcpgateway.validation.jsonrpc.JSONRPCError: Error code must be integer

        유효하지 않은 에러 메시지 타입:
        >>> validate_response({"jsonrpc": "2.0", "error": {"code": -32601, "message": 123}, "id": 1})  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        mcpgateway.validation.jsonrpc.JSONRPCError: Error message must be string

        추가 데이터가 있는 유효한 에러:
        >>> validate_response({"jsonrpc": "2.0", "error": {"code": -32602, "message": "Invalid params", "data": {"param": "name"}}, "id": 1})
    """
    # JSON-RPC 버전 확인 (2.0이어야 함)
    if response.get("jsonrpc") != "2.0":
        raise JSONRPCError(INVALID_REQUEST, "Invalid JSON-RPC version", request_id=response.get("id"))

    # 응답 ID 검증 (필수 필드)
    # ID는 문자열, 정수 또는 null이어야 하며, 불리언은 허용되지 않음
    if "id" not in response:
        raise JSONRPCError(INVALID_REQUEST, "Missing response ID", request_id=None)

    response_id = response["id"]
    if not isinstance(response_id, (str, int, type(None))) or isinstance(response_id, bool):
        raise JSONRPCError(INVALID_REQUEST, "Invalid response ID type", request_id=None)

    # 결과와 에러 중 하나만 존재해야 함 (XOR 검증)
    has_result = "result" in response
    has_error = "error" in response

    if not has_result and not has_error:
        raise JSONRPCError(INVALID_REQUEST, "Response must contain either result or error", request_id=id)
    if has_result and has_error:
        raise JSONRPCError(INVALID_REQUEST, "Response cannot contain both result and error", request_id=id)

    # 에러 객체 상세 검증
    if has_error:
        error = response["error"]
        # 에러는 반드시 딕셔너리여야 함
        if not isinstance(error, dict):
            raise JSONRPCError(INVALID_REQUEST, "Invalid error object type", request_id=id)

        # 에러 객체는 code와 message 필드를 반드시 가져야 함
        if "code" not in error or "message" not in error:
            raise JSONRPCError(INVALID_REQUEST, "Error must contain code and message", request_id=id)

        # 에러 코드 타입 검증 (정수여야 함)
        if not isinstance(error["code"], int):
            raise JSONRPCError(INVALID_REQUEST, "Error code must be integer", request_id=id)

        # 에러 메시지 타입 검증 (문자열이어야 함)
        if not isinstance(error["message"], str):
            raise JSONRPCError(INVALID_REQUEST, "Error message must be string", request_id=id)
