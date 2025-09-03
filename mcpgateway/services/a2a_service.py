# -*- coding: utf-8 -*-
"""위치: ./mcpgateway/services/a2a_service.py
저작권 2025
SPDX-License-Identifier: Apache-2.0
저자: Mihai Criveti

A2A 에이전트 서비스

이 모듈은 MCP 게이트웨이를 위한 A2A (Agent-to-Agent) 에이전트 관리를 구현합니다.
에이전트 등록, 목록 조회, 검색, 업데이트, 활성화 토글, 삭제,
그리고 A2A 호환 에이전트와의 상호작용을 처리합니다.
"""

# 표준 라이브러리
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

# 서드파티 라이브러리
import httpx
from sqlalchemy import case, delete, desc, func, select
from sqlalchemy.orm import Session

# 자체 라이브러리
from mcpgateway.db import A2AAgent as DbA2AAgent
from mcpgateway.db import A2AAgentMetric
from mcpgateway.schemas import A2AAgentCreate, A2AAgentMetrics, A2AAgentRead, A2AAgentUpdate
from mcpgateway.services.logging_service import LoggingService

# 로깅 서비스 초기화
logging_service = LoggingService()
logger = logging_service.get_logger(__name__)


# A2A 에이전트 관련 예외 클래스들
class A2AAgentError(Exception):
    """A2A 에이전트 관련 오류들의 기본 클래스입니다."""


class A2AAgentNotFoundError(A2AAgentError):
    """요청된 A2A 에이전트를 찾을 수 없을 때 발생하는 예외입니다."""


class A2AAgentNameConflictError(A2AAgentError):
    """A2A 에이전트 이름이 기존 에이전트와 충돌할 때 발생하는 예외입니다."""

    def __init__(self, name: str, is_active: bool = True, agent_id: Optional[str] = None):
        """A2AAgentNameConflictError 예외를 초기화합니다.

        충돌하는 에이전트 이름과 함께, 충돌하는 에이전트가 활성화 상태인지
        그리고 알려진 경우 ID에 대한 추가 컨텍스트를 포함한 예외를 생성합니다.

        Args:
            name: 충돌을 일으킨 에이전트 이름입니다.
            is_active: 충돌하는 에이전트가 현재 활성화 상태인지 여부입니다.
            agent_id: 알려진 경우 충돌하는 에이전트의 ID입니다.
        """
        self.name = name
        self.is_active = is_active
        self.agent_id = agent_id

        # 사용자 친화적인 오류 메시지 구성
        message = f"A2A 에이전트가 이미 존재합니다: {name}"
        if not is_active:
            message += f" (현재 비활성화 상태, ID: {agent_id})"

        super().__init__(message)


class A2AAgentService:
    """게이트웨이에서 A2A 에이전트를 관리하는 서비스 클래스입니다.

    에이전트 레코드 생성, 목록 조회, 검색, 업데이트, 상태 토글, 삭제를 위한
    메서드들을 제공합니다. 또한 A2A 호환 에이전트와의 상호작용도 지원합니다.
    """

    def __init__(self) -> None:
        """새로운 A2AAgentService 인스턴스를 초기화합니다."""
        self._initialized = False
        # 비동기 이벤트 스트림들을 저장할 리스트 (미래 확장을 위한 준비)
        self._event_streams: List[AsyncGenerator[str, None]] = []

    async def initialize(self) -> None:
        """A2A 에이전트 서비스를 초기화합니다."""
        if not self._initialized:
            logger.info("A2A 에이전트 서비스 초기화 중")
            self._initialized = True

    async def shutdown(self) -> None:
        """A2A 에이전트 서비스를 종료하고 리소스를 정리합니다."""
        if self._initialized:
            logger.info("A2A 에이전트 서비스 종료 중")
            self._initialized = False

    async def register_agent(
        self,
        db: Session,
        agent_data: A2AAgentCreate,
        created_by: Optional[str] = None,
        created_from_ip: Optional[str] = None,
        created_via: Optional[str] = None,
        created_user_agent: Optional[str] = None,
        import_batch_id: Optional[str] = None,
        federation_source: Optional[str] = None,
    ) -> A2AAgentRead:
        """새로운 A2A 에이전트를 등록합니다.

        Args:
            db: 데이터베이스 세션입니다.
            agent_data: 에이전트 생성 데이터입니다.
            created_by: 이 에이전트를 생성한 사용자 이름입니다.
            created_from_ip: 생성자의 IP 주소입니다.
            created_via: 생성 방법입니다.
            created_user_agent: 생성 요청의 사용자 에이전트입니다.
            import_batch_id: 일괄 가져오기 배치의 UUID입니다.
            federation_source: 연합 엔티티를 위한 소스 게이트웨이입니다.

        Returns:
            생성된 에이전트 데이터입니다.

        Raises:
            A2AAgentNameConflictError: 동일한 이름의 에이전트가 이미 존재하는 경우 발생합니다.
        """
        # 동일한 이름의 기존 에이전트 확인
        existing_query = select(DbA2AAgent).where(DbA2AAgent.name == agent_data.name)
        existing_agent = db.execute(existing_query).scalar_one_or_none()

        if existing_agent:
            raise A2AAgentNameConflictError(
                name=agent_data.name,
                is_active=existing_agent.enabled,
                agent_id=existing_agent.id
            )

        # 새로운 에이전트 생성
        new_agent = DbA2AAgent(
            name=agent_data.name,
            description=agent_data.description,
            endpoint_url=agent_data.endpoint_url,
            agent_type=agent_data.agent_type,
            protocol_version=agent_data.protocol_version,
            capabilities=agent_data.capabilities,
            config=agent_data.config,
            auth_type=agent_data.auth_type,
            auth_value=agent_data.auth_value,  # 실제로는 암호화되어야 함
            tags=agent_data.tags,
            created_by=created_by,
            created_from_ip=created_from_ip,
            created_via=created_via,
            created_user_agent=created_user_agent,
            import_batch_id=import_batch_id,
            federation_source=federation_source,
        )

        # 데이터베이스에 추가 및 커밋
        db.add(new_agent)
        db.commit()
        db.refresh(new_agent)

        # 성공 로그 기록 및 결과 반환
        logger.info(f"새로운 A2A 에이전트 등록됨: {new_agent.name} (ID: {new_agent.id})")
        return self._db_to_schema(new_agent)

    async def list_agents(
        self,
        db: Session,
        cursor: Optional[str] = None,
        include_inactive: bool = False,
        tags: Optional[List[str]] = None
    ) -> List[A2AAgentRead]:  # pylint: disable=unused-argument
        """선택적 필터링을 적용하여 A2A 에이전트 목록을 조회합니다.

        Args:
            db: 데이터베이스 세션입니다.
            cursor: 페이지네이션 커서입니다 (아직 구현되지 않음).
            include_inactive: 비활성화된 에이전트도 포함할지 여부입니다.
            tags: 필터링할 태그 목록입니다.

        Returns:
            에이전트 데이터 목록입니다.
        """
        # 기본 쿼리 생성
        query = select(DbA2AAgent)

        # 활성화된 에이전트만 필터링 (기본값)
        if not include_inactive:
            query = query.where(DbA2AAgent.enabled.is_(True))

        # 태그 기반 필터링
        if tags:
            # 태그로 필터링 - 에이전트는 지정된 태그 중 하나 이상을 가지고 있어야 함
            # 타입 명시를 위해 Union 타입으로 변경
            tag_conditions: List[Union[bool, Any]] = []
            for tag in tags:
                # JSON 필드에서 태그가 포함되어 있는지 확인
                tag_condition = func.json_extract(DbA2AAgent.tags, "$").contains(tag)
                tag_conditions.append(tag_condition)

            # 하나 이상의 태그 조건이 만족되는 경우에만 결과 포함
            if tag_conditions:
                query = query.where(func.or_(*tag_conditions))

        # 생성일 기준 내림차순 정렬
        query = query.order_by(desc(DbA2AAgent.created_at))

        # 쿼리 실행 및 결과 변환
        agents = db.execute(query).scalars().all()
        return [self._db_to_schema(agent) for agent in agents]

    async def get_agent(self, db: Session, agent_id: str) -> A2AAgentRead:
        """ID로 A2A 에이전트를 검색합니다.

        Args:
            db: 데이터베이스 세션입니다.
            agent_id: 에이전트 ID입니다.

        Returns:
            에이전트 데이터입니다.

        Raises:
            A2AAgentNotFoundError: 에이전트를 찾을 수 없는 경우 발생합니다.
        """
        # ID로 에이전트 조회 쿼리
        query = select(DbA2AAgent).where(DbA2AAgent.id == agent_id)
        agent = db.execute(query).scalar_one_or_none()

        if not agent:
            raise A2AAgentNotFoundError(f"A2A 에이전트를 찾을 수 없습니다. ID: {agent_id}")

        return self._db_to_schema(agent)

    async def get_agent_by_name(self, db: Session, agent_name: str) -> A2AAgentRead:
        """이름으로 A2A 에이전트를 검색합니다.

        Args:
            db: 데이터베이스 세션입니다.
            agent_name: 에이전트 이름입니다.

        Returns:
            에이전트 데이터입니다.

        Raises:
            A2AAgentNotFoundError: 에이전트를 찾을 수 없는 경우 발생합니다.
        """
        # 이름으로 에이전트 조회 쿼리
        query = select(DbA2AAgent).where(DbA2AAgent.name == agent_name)
        agent = db.execute(query).scalar_one_or_none()

        if not agent:
            raise A2AAgentNotFoundError(f"A2A 에이전트를 찾을 수 없습니다. 이름: {agent_name}")

        return self._db_to_schema(agent)

    async def update_agent(
        self,
        db: Session,
        agent_id: str,
        agent_data: A2AAgentUpdate,
        modified_by: Optional[str] = None,
        modified_from_ip: Optional[str] = None,
        modified_via: Optional[str] = None,
        modified_user_agent: Optional[str] = None,
    ) -> A2AAgentRead:
        """기존 A2A 에이전트를 업데이트합니다.

        Args:
            db: 데이터베이스 세션입니다.
            agent_id: 에이전트 ID입니다.
            agent_data: 에이전트 업데이트 데이터입니다.
            modified_by: 이 에이전트를 수정한 사용자 이름입니다.
            modified_from_ip: 수정자의 IP 주소입니다.
            modified_via: 수정 방법입니다.
            modified_user_agent: 수정 요청의 사용자 에이전트입니다.

        Returns:
            업데이트된 에이전트 데이터입니다.

        Raises:
            A2AAgentNotFoundError: 에이전트를 찾을 수 없는 경우 발생합니다.
            A2AAgentNameConflictError: 이름이 다른 에이전트와 충돌하는 경우 발생합니다.
        """
        # 업데이트할 에이전트 조회
        query = select(DbA2AAgent).where(DbA2AAgent.id == agent_id)
        agent = db.execute(query).scalar_one_or_none()

        if not agent:
            raise A2AAgentNotFoundError(f"A2A 에이전트를 찾을 수 없습니다. ID: {agent_id}")

        # 이름 변경 시 충돌 확인
        if agent_data.name and agent_data.name != agent.name:
            existing_query = select(DbA2AAgent).where(
                DbA2AAgent.name == agent_data.name,
                DbA2AAgent.id != agent_id
            )
            existing_agent = db.execute(existing_query).scalar_one_or_none()

            if existing_agent:
                raise A2AAgentNameConflictError(
                    name=agent_data.name,
                    is_active=existing_agent.enabled,
                    agent_id=existing_agent.id
                )

        # 필드 업데이트 (설정되지 않은 필드는 제외)
        update_data = agent_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(agent, field):
                setattr(agent, field, value)

        # 메타데이터 업데이트
        if modified_by:
            agent.modified_by = modified_by
        if modified_from_ip:
            agent.modified_from_ip = modified_from_ip
        if modified_via:
            agent.modified_via = modified_via
        if modified_user_agent:
            agent.modified_user_agent = modified_user_agent

        # 버전 증가
        agent.version += 1

        # 변경사항 커밋 및 새로고침
        db.commit()
        db.refresh(agent)

        # 성공 로그 기록 및 결과 반환
        logger.info(f"A2A 에이전트 업데이트됨: {agent.name} (ID: {agent.id})")
        return self._db_to_schema(agent)

    async def toggle_agent_status(
        self,
        db: Session,
        agent_id: str,
        activate: bool,
        reachable: Optional[bool] = None
    ) -> A2AAgentRead:
        """A2A 에이전트의 활성화 상태를 토글합니다.

        Args:
            db: 데이터베이스 세션입니다.
            agent_id: 에이전트 ID입니다.
            activate: True이면 활성화, False이면 비활성화합니다.
            reachable: 선택적 도달 가능성 상태입니다.

        Returns:
            업데이트된 에이전트 데이터입니다.

        Raises:
            A2AAgentNotFoundError: 에이전트를 찾을 수 없는 경우 발생합니다.
        """
        # 토글할 에이전트 조회
        query = select(DbA2AAgent).where(DbA2AAgent.id == agent_id)
        agent = db.execute(query).scalar_one_or_none()

        if not agent:
            raise A2AAgentNotFoundError(f"A2A 에이전트를 찾을 수 없습니다. ID: {agent_id}")

        # 상태 업데이트
        agent.enabled = activate
        if reachable is not None:
            agent.reachable = reachable

        # 변경사항 커밋 및 새로고침
        db.commit()
        db.refresh(agent)

        # 상태 변경 로그 기록
        status = "활성화됨" if activate else "비활성화됨"
        logger.info(f"A2A 에이전트 {status}: {agent.name} (ID: {agent.id})")
        return self._db_to_schema(agent)

    async def delete_agent(self, db: Session, agent_id: str) -> None:
        """A2A 에이전트를 삭제합니다.

        Args:
            db: 데이터베이스 세션입니다.
            agent_id: 에이전트 ID입니다.

        Raises:
            A2AAgentNotFoundError: 에이전트를 찾을 수 없는 경우 발생합니다.
        """
        # 삭제할 에이전트 조회
        query = select(DbA2AAgent).where(DbA2AAgent.id == agent_id)
        agent = db.execute(query).scalar_one_or_none()

        if not agent:
            raise A2AAgentNotFoundError(f"A2A 에이전트를 찾을 수 없습니다. ID: {agent_id}")

        # 에이전트 정보 저장 후 삭제
        agent_name = agent.name
        db.delete(agent)
        db.commit()

        # 삭제 성공 로그 기록
        logger.info(f"A2A 에이전트 삭제됨: {agent_name} (ID: {agent_id})")

    async def invoke_agent(
        self,
        db: Session,
        agent_name: str,
        parameters: Dict[str, Any],
        interaction_type: str = "query"
    ) -> Dict[str, Any]:
        """A2A 에이전트를 호출합니다.

        Args:
            db: 데이터베이스 세션입니다.
            agent_name: 호출할 에이전트의 이름입니다.
            parameters: 상호작용을 위한 파라미터입니다.
            interaction_type: 상호작용 타입입니다.

        Returns:
            에이전트 응답입니다.

        Raises:
            A2AAgentNotFoundError: 에이전트를 찾을 수 없는 경우 발생합니다.
            A2AAgentError: 에이전트가 비활성화되었거나 호출에 실패한 경우 발생합니다.
        """
        # 이름으로 에이전트 조회
        agent = await self.get_agent_by_name(db, agent_name)

        if not agent.enabled:
            raise A2AAgentError(f"A2A 에이전트 '{agent_name}'이(가) 비활성화되었습니다")

        # 호출 시작 시간 및 초기 상태 설정
        start_time = datetime.now(timezone.utc)
        success = False
        error_message = None
        response = None

        try:
            # A2A 에이전트에 대한 요청 준비
            # 에이전트 타입과 엔드포인트에 따라 요청 형식 결정
            if agent.agent_type in ["generic", "jsonrpc"] or agent.endpoint_url.endswith("/"):
                # JSONRPC 형식을 기대하는 에이전트의 경우
                request_data = {
                    "jsonrpc": "2.0",
                    "method": parameters.get("method", "message/send"),
                    "params": parameters.get("params", parameters),
                    "id": 1
                }
            else:
                # 사용자 정의 A2A 형식
                request_data = {
                    "interaction_type": interaction_type,
                    "parameters": parameters,
                    "protocol_version": agent.protocol_version
                }

            # HTTP 클라이언트로 에이전트 엔드포인트에 요청
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {"Content-Type": "application/json"}

                # 설정된 경우 인증 헤더 추가 (DB에서 직접 가져옴)
                db_query = select(DbA2AAgent).where(DbA2AAgent.id == agent.id)
                db_agent = db.execute(db_query).scalar_one()

                if db_agent.auth_type == "api_key" and db_agent.auth_value:
                    headers["Authorization"] = f"Bearer {db_agent.auth_value}"
                elif db_agent.auth_type == "bearer" and db_agent.auth_value:
                    headers["Authorization"] = f"Bearer {db_agent.auth_value}"

                # HTTP POST 요청 실행
                http_response = await client.post(
                    db_agent.endpoint_url,
                    json=request_data,
                    headers=headers
                )

                if http_response.status_code == 200:
                    response = http_response.json()
                    success = True
                else:
                    error_message = f"HTTP {http_response.status_code}: {http_response.text}"
                    raise A2AAgentError(error_message)

        except Exception as e:
            error_message = str(e)
            logger.error(f"A2A 에이전트 '{agent_name}' 호출 실패: {error_message}")
            raise A2AAgentError(f"A2A 에이전트 호출 실패: {error_message}")

        finally:
            # 메트릭 기록 (성공/실패 여부와 관계없이 실행)
            end_time = datetime.now(timezone.utc)
            response_time = (end_time - start_time).total_seconds()

            # 메트릭 데이터 생성 및 저장
            metric = A2AAgentMetric(
                a2a_agent_id=agent.id,
                response_time=response_time,
                is_success=success,
                error_message=error_message,
                interaction_type=interaction_type
            )
            db.add(metric)

            # 마지막 상호작용 타임스탬프 업데이트 (항상 DB에서 새로 조회)
            update_query = select(DbA2AAgent).where(DbA2AAgent.id == agent.id)
            db_agent_to_update = db.execute(update_query).scalar_one()
            db_agent_to_update.last_interaction = end_time
            db.commit()

        # 응답 반환 (없는 경우 오류 메시지 포함)
        return response or {"error": error_message}

    async def aggregate_metrics(self, db: Session) -> Dict[str, Any]:
        """모든 A2A 에이전트에 대한 메트릭을 집계합니다.

        Args:
            db: 데이터베이스 세션입니다.

        Returns:
            집계된 메트릭 데이터입니다.
        """
        # 총 에이전트 수 조회
        total_agents_query = select(func.count(DbA2AAgent.id))  # pylint: disable=not-callable
        total_agents = db.execute(total_agents_query).scalar() or 0

        # 활성화된 에이전트 수 조회
        active_agents_query = select(func.count(DbA2AAgent.id)).where(DbA2AAgent.enabled.is_(True))  # pylint: disable=not-callable
        active_agents = db.execute(active_agents_query).scalar() or 0

        # 전체 메트릭 조회
        metrics_query = select(
            func.count(A2AAgentMetric.id).label("total_interactions"),  # pylint: disable=not-callable
            func.sum(case((A2AAgentMetric.is_success.is_(True), 1), else_=0)).label("successful_interactions"),
            func.avg(A2AAgentMetric.response_time).label("avg_response_time"),
            func.min(A2AAgentMetric.response_time).label("min_response_time"),
            func.max(A2AAgentMetric.response_time).label("max_response_time"),
        )

        metrics_result = db.execute(metrics_query).first()

        # 메트릭 결과가 None일 수 있으므로 안전하게 처리
        if metrics_result:
            total_interactions = metrics_result.total_interactions or 0
            successful_interactions = metrics_result.successful_interactions or 0
            avg_response_time = float(metrics_result.avg_response_time or 0.0)
            min_response_time = float(metrics_result.min_response_time or 0.0)
            max_response_time = float(metrics_result.max_response_time or 0.0)
        else:
            # 메트릭 데이터가 없는 경우 기본값 설정
            total_interactions = 0
            successful_interactions = 0
            avg_response_time = 0.0
            min_response_time = 0.0
            max_response_time = 0.0

        failed_interactions = total_interactions - successful_interactions

        # 집계된 메트릭 반환
        return {
            "total_agents": total_agents,
            "active_agents": active_agents,
            "total_interactions": total_interactions,
            "successful_interactions": successful_interactions,
            "failed_interactions": failed_interactions,
            "success_rate": (successful_interactions / total_interactions * 100) if total_interactions > 0 else 0.0,
            "avg_response_time": avg_response_time,
            "min_response_time": min_response_time,
            "max_response_time": max_response_time,
        }

    async def reset_metrics(self, db: Session, agent_id: Optional[str] = None) -> None:
        """에이전트 메트릭을 리셋합니다.

        Args:
            db: 데이터베이스 세션입니다.
            agent_id: 특정 에이전트의 메트릭을 리셋할 때 사용하는 선택적 에이전트 ID입니다.
        """
        if agent_id:
            # 특정 에이전트의 메트릭 리셋
            delete_query = delete(A2AAgentMetric).where(A2AAgentMetric.a2a_agent_id == agent_id)
        else:
            # 모든 메트릭 리셋
            delete_query = delete(A2AAgentMetric)

        # 메트릭 삭제 실행 및 커밋
        db.execute(delete_query)
        db.commit()

        # 리셋 완료 로그 기록
        logger.info("A2A 에이전트 메트릭 리셋됨" + (f" (에이전트 {agent_id})" if agent_id else ""))

    def _db_to_schema(self, db_agent: DbA2AAgent) -> A2AAgentRead:
        """데이터베이스 모델을 스키마로 변환합니다.

        Args:
            db_agent: 데이터베이스 에이전트 모델입니다.

        Returns:
            에이전트 읽기 스키마입니다.
        """
        # 메트릭 계산
        total_executions = len(db_agent.metrics)
        successful_executions = sum(1 for m in db_agent.metrics if m.is_success)
        failed_executions = total_executions - successful_executions
        failure_rate = (failed_executions / total_executions) * 100 if total_executions > 0 else 0.0

        # 응답 시간 및 실행 시간 계산
        min_response_time = None
        max_response_time = None
        avg_response_time = None
        last_execution_time = None

        if db_agent.metrics:
            # 메트릭 데이터가 있는 경우 계산 수행
            response_times = [m.response_time for m in db_agent.metrics]
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            avg_response_time = sum(response_times) / len(response_times)
            last_execution_time = max(m.timestamp for m in db_agent.metrics)

        # 메트릭 객체 생성
        metrics = A2AAgentMetrics(
            total_executions=total_executions,
            successful_executions=successful_executions,
            failed_executions=failed_executions,
            failure_rate=failure_rate,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            avg_response_time=avg_response_time,
            last_execution_time=last_execution_time,
        )

        # A2AAgentRead 스키마 객체 생성 및 반환
        return A2AAgentRead(
            id=db_agent.id,
            name=db_agent.name,
            slug=db_agent.slug,
            description=db_agent.description,
            endpoint_url=db_agent.endpoint_url,
            agent_type=db_agent.agent_type,
            protocol_version=db_agent.protocol_version,
            capabilities=db_agent.capabilities,
            config=db_agent.config,
            auth_type=db_agent.auth_type,
            enabled=db_agent.enabled,
            reachable=db_agent.reachable,
            created_at=db_agent.created_at,
            updated_at=db_agent.updated_at,
            last_interaction=db_agent.last_interaction,
            tags=db_agent.tags,
            metrics=metrics,
            created_by=db_agent.created_by,
            created_from_ip=db_agent.created_from_ip,
            created_via=db_agent.created_via,
            created_user_agent=db_agent.created_user_agent,
            modified_by=db_agent.modified_by,
            modified_from_ip=db_agent.modified_from_ip,
            modified_via=db_agent.modified_via,
            modified_user_agent=db_agent.modified_user_agent,
            import_batch_id=db_agent.import_batch_id,
            federation_source=db_agent.federation_source,
            version=db_agent.version,
        )
