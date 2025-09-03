# -*- coding: utf-8 -*-
"""위치: ./mcpgateway/services/export_service.py
저작권 2025
SPDX-License-Identifier: Apache-2.0
저자: Mihai Criveti

구성 내보내기 서비스 구현 모듈

내보내기 사양에 따라 포괄적인 구성 내보내기 기능을 구현합니다.
다음 항목들을 처리합니다:
- 모든 엔티티 타입에서 엔티티 수집 (도구, 게이트웨이, 서버, 프롬프트, 리소스, 루트)
- AES-256-GCM을 사용한 안전한 인증 데이터 암호화
- 의존성 해결 및 포함
- 엔티티 타입, 태그, 활성화/비활성화 상태별 필터링
- 내보내기 형식 검증 및 스키마 준수
- 로컬로 구성된 엔티티만 내보내기 (연합 콘텐츠 제외)
"""

# 표준 라이브러리 임포트
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

# 서드파티 라이브러리 임포트
from sqlalchemy import select
from sqlalchemy.orm import Session

# 자체 라이브러리 임포트
from mcpgateway.config import settings
from mcpgateway.db import Gateway as DbGateway
from mcpgateway.db import Tool as DbTool
from mcpgateway.services.gateway_service import GatewayService
from mcpgateway.services.prompt_service import PromptService
from mcpgateway.services.resource_service import ResourceService
from mcpgateway.services.root_service import RootService
from mcpgateway.services.server_service import ServerService
from mcpgateway.services.tool_service import ToolService

logger = logging.getLogger(__name__)


class ExportError(Exception):
    """내보내기 관련 오류들의 기본 클래스입니다."""


class ExportValidationError(ExportError):
    """내보내기 데이터 검증 실패 시 발생하는 예외입니다."""


class ExportService:
    """MCP 게이트웨이 구성 및 데이터를 내보내는 서비스 클래스입니다.

    이 서비스는 다음과 같은 포괄적인 내보내기 기능을 제공합니다:
    - 모든 엔티티 타입 수집 (도구, 게이트웨이, 서버, 프롬프트, 리소스, 루트)
    - 암호화를 통한 인증 데이터의 안전한 처리
    - 엔티티 간 의존성 해결
    - 필터링 옵션 (타입, 태그, 상태별)
    - 내보내기 형식 검증

    이 서비스는 로컬로 구성된 엔티티만 내보내며, 연합 소스의 동적 콘텐츠를
    제외하여 내보내기에 구성 데이터만 포함되도록 보장합니다.
    """

    def __init__(self):
        """필요한 의존성과 함께 내보내기 서비스를 초기화합니다."""
        # 각 엔티티 타입을 처리하기 위한 서비스 인스턴스들 초기화
        self.gateway_service = GatewayService()
        self.tool_service = ToolService()
        self.resource_service = ResourceService()
        self.prompt_service = PromptService()
        self.server_service = ServerService()
        self.root_service = RootService()

    async def initialize(self) -> None:
        """내보내기 서비스를 초기화합니다."""
        logger.info("내보내기 서비스 초기화됨")

    async def shutdown(self) -> None:
        """내보내기 서비스를 종료합니다."""
        logger.info("내보내기 서비스 종료됨")

    async def export_configuration(
        self,
        db: Session,
        include_types: Optional[List[str]] = None,
        exclude_types: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        include_inactive: bool = False,
        include_dependencies: bool = True,
        exported_by: str = "system",
    ) -> Dict[str, Any]:
        """완전한 게이트웨이 구성을 표준화된 형식으로 내보냅니다.

        Args:
            db: 데이터베이스 세션
            include_types: 포함할 엔티티 타입 목록 (tools, gateways, servers, prompts, resources, roots)
            exclude_types: 제외할 엔티티 타입 목록
            tags: 태그별 엔티티 필터링 (이 태그들을 가진 엔티티만 내보내기)
            include_inactive: 비활성화된 엔티티도 포함할지 여부
            include_dependencies: 종속 엔티티를 자동으로 포함할지 여부
            exported_by: 내보내기를 수행한 사용자의 이름

        Returns:
            지정된 스키마 형식의 완전한 내보내기 데이터를 포함하는 딕셔너리

        Raises:
            ExportError: 내보내기 실패 시
            ExportValidationError: 검증 실패 시
        """
        try:
            logger.info(f"{exported_by}에 의한 구성 내보내기 시작")

            # 포함할 엔티티 타입 결정
            all_types = ["tools", "gateways", "servers", "prompts", "resources", "roots"]
            if include_types:
                # 지정된 타입들 중 유효한 것만 필터링
                entity_types = [t.lower() for t in include_types if t.lower() in all_types]
            else:
                # 모든 타입 포함
                entity_types = all_types

            if exclude_types:
                # 제외할 타입들을 필터링하여 제거
                entity_types = [t for t in entity_types if t.lower() not in [e.lower() for e in exclude_types]]

            # 내보내기 구조 초기화
            export_data = {
                "version": settings.protocol_version,
                "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "exported_by": exported_by,
                "source_gateway": f"http://{settings.host}:{settings.port}",
                "encryption_method": "AES-256-GCM",
                "entities": {},  # 엔티티 데이터를 담을 컨테이너
                "metadata": {
                    "entity_counts": {},  # 각 타입별 엔티티 수
                    "dependencies": {},   # 엔티티 간 의존성 정보
                    "export_options": {   # 내보내기 옵션 설정
                        "include_inactive": include_inactive,
                        "include_dependencies": include_dependencies,
                        "selected_types": entity_types,
                        "filter_tags": tags or []
                    },
                },
            }

            # 각 엔티티 타입별로 내보내기 수행
            if "tools" in entity_types:
                # 도구 엔티티 내보내기 (태그 필터링 및 활성화 상태 고려)
                export_data["entities"]["tools"] = await self._export_tools(db, tags, include_inactive)

            if "gateways" in entity_types:
                # 게이트웨이 엔티티 내보내기 (태그 필터링 및 활성화 상태 고려)
                export_data["entities"]["gateways"] = await self._export_gateways(db, tags, include_inactive)

            if "servers" in entity_types:
                # 서버 엔티티 내보내기 (태그 필터링 및 활성화 상태 고려)
                export_data["entities"]["servers"] = await self._export_servers(db, tags, include_inactive)

            if "prompts" in entity_types:
                # 프롬프트 엔티티 내보내기 (태그 필터링 및 활성화 상태 고려)
                export_data["entities"]["prompts"] = await self._export_prompts(db, tags, include_inactive)

            if "resources" in entity_types:
                # 리소스 엔티티 내보내기 (태그 필터링 및 활성화 상태 고려)
                export_data["entities"]["resources"] = await self._export_resources(db, tags, include_inactive)

            if "roots" in entity_types:
                # 루트 엔티티 내보내기 (태그나 활성화 상태 필터링 없음)
                export_data["entities"]["roots"] = await self._export_roots()

            # 의존성 정보 추가
            if include_dependencies:
                # 엔티티 간의 의존성 관계 추출 및 추가
                export_data["metadata"]["dependencies"] = await self._extract_dependencies(db, export_data["entities"])

            # 엔티티 수 계산
            for entity_type, entities in export_data["entities"].items():
                # 각 엔티티 타입별로 엔티티 개수 저장
                export_data["metadata"]["entity_counts"][entity_type] = len(entities)

            # 내보내기 데이터 검증
            self._validate_export_data(export_data)

            # 성공 로그 기록 및 결과 반환
            total_entities = sum(export_data['metadata']['entity_counts'].values())
            logger.info(f"총 {total_entities}개 엔티티와 함께 내보내기가 성공적으로 완료됨")
            return export_data

        except Exception as e:
            logger.error(f"내보내기 실패: {str(e)}")
            raise ExportError(f"구성 내보내기에 실패했습니다: {str(e)}")

    async def _export_tools(self, db: Session, tags: Optional[List[str]], include_inactive: bool) -> List[Dict[str, Any]]:
        """Export tools with encrypted authentication data.

        Args:
            db: Database session
            tags: Filter by tags
            include_inactive: Include inactive tools

        Returns:
            List of exported tool dictionaries
        """
        tools = await self.tool_service.list_tools(db, tags=tags, include_inactive=include_inactive)
        exported_tools = []

        for tool in tools:
            # Only export locally created REST tools, not MCP tools from gateways
            if tool.integration_type == "MCP" and tool.gateway_id:
                continue

            tool_data = {
                "name": tool.original_name,  # Use original name, not the slugified version
                "displayName": tool.displayName,  # Export displayName field from ToolRead
                "url": str(tool.url),
                "integration_type": tool.integration_type,
                "request_type": tool.request_type,
                "description": tool.description,
                "headers": tool.headers or {},
                "input_schema": tool.input_schema or {"type": "object", "properties": {}},
                "annotations": tool.annotations or {},
                "jsonpath_filter": tool.jsonpath_filter,
                "tags": tool.tags or [],
                "rate_limit": getattr(tool, "rate_limit", None),
                "timeout": getattr(tool, "timeout", None),
                "is_active": tool.enabled,
                "created_at": tool.created_at.isoformat() if hasattr(tool.created_at, "isoformat") and tool.created_at else None,
                "updated_at": tool.updated_at.isoformat() if hasattr(tool.updated_at, "isoformat") and tool.updated_at else None,
            }

            # Handle authentication data securely - get raw encrypted values
            if hasattr(tool, "auth") and tool.auth:
                auth_data = tool.auth
                if hasattr(auth_data, "auth_type") and hasattr(auth_data, "auth_value"):
                    # Check if auth_value is masked, if so get raw value from DB
                    if auth_data.auth_value == settings.masked_auth_value:
                        # Get the raw encrypted auth_value from database
                        db_tool = db.execute(select(DbTool).where(DbTool.id == tool.id)).scalar_one_or_none()
                        if db_tool and db_tool.auth_value:
                            tool_data["auth_type"] = auth_data.auth_type
                            tool_data["auth_value"] = db_tool.auth_value  # Raw encrypted value
                    else:
                        # Auth value is not masked, use as-is
                        tool_data["auth_type"] = auth_data.auth_type
                        tool_data["auth_value"] = auth_data.auth_value  # Already encrypted

            exported_tools.append(tool_data)

        return exported_tools

    async def _export_gateways(self, db: Session, tags: Optional[List[str]], include_inactive: bool) -> List[Dict[str, Any]]:
        """Export gateways with encrypted authentication data.

        Args:
            db: Database session
            tags: Filter by tags
            include_inactive: Include inactive gateways

        Returns:
            List of exported gateway dictionaries
        """
        gateways = await self.gateway_service.list_gateways(db, include_inactive=include_inactive)
        exported_gateways = []

        for gateway in gateways:
            # Filter by tags if specified
            if tags and not any(tag in (gateway.tags or []) for tag in tags):
                continue

            gateway_data = {
                "name": gateway.name,
                "url": str(gateway.url),
                "description": gateway.description,
                "transport": gateway.transport,
                "capabilities": gateway.capabilities or {},
                "health_check": {"url": f"{gateway.url}/health", "interval": 30, "timeout": 10, "retries": 3},
                "is_active": gateway.enabled,
                "federation_enabled": True,
                "tags": gateway.tags or [],
                "passthrough_headers": gateway.passthrough_headers or [],
            }

            # Handle authentication data securely - get raw encrypted values
            if gateway.auth_type and gateway.auth_value:
                # Check if auth_value is masked, if so get raw value from DB
                if gateway.auth_value == settings.masked_auth_value:
                    # Get the raw encrypted auth_value from database
                    db_gateway = db.execute(select(DbGateway).where(DbGateway.id == gateway.id)).scalar_one_or_none()
                    if db_gateway and db_gateway.auth_value:
                        gateway_data["auth_type"] = gateway.auth_type
                        gateway_data["auth_value"] = db_gateway.auth_value  # Raw encrypted value
                else:
                    # Auth value is not masked, use as-is
                    gateway_data["auth_type"] = gateway.auth_type
                    gateway_data["auth_value"] = gateway.auth_value  # Already encrypted

            exported_gateways.append(gateway_data)

        return exported_gateways

    async def _export_servers(self, db: Session, tags: Optional[List[str]], include_inactive: bool) -> List[Dict[str, Any]]:
        """Export virtual servers with their tool associations.

        Args:
            db: Database session
            tags: Filter by tags
            include_inactive: Include inactive servers

        Returns:
            List of exported server dictionaries
        """
        servers = await self.server_service.list_servers(db, tags=tags, include_inactive=include_inactive)
        exported_servers = []

        for server in servers:
            server_data = {
                "name": server.name,
                "description": server.description,
                "tool_ids": list(server.associated_tools),
                "sse_endpoint": f"/servers/{server.id}/sse",
                "websocket_endpoint": f"/servers/{server.id}/ws",
                "jsonrpc_endpoint": f"/servers/{server.id}/jsonrpc",
                "capabilities": {"tools": {"list_changed": True}, "prompts": {"list_changed": True}},
                "is_active": server.is_active,
                "tags": server.tags or [],
            }

            exported_servers.append(server_data)

        return exported_servers

    async def _export_prompts(self, db: Session, tags: Optional[List[str]], include_inactive: bool) -> List[Dict[str, Any]]:
        """Export prompts with their templates and schemas.

        Args:
            db: Database session
            tags: Filter by tags
            include_inactive: Include inactive prompts

        Returns:
            List of exported prompt dictionaries
        """
        prompts = await self.prompt_service.list_prompts(db, tags=tags, include_inactive=include_inactive)
        exported_prompts = []

        for prompt in prompts:
            prompt_data = {
                "name": prompt.name,
                "template": prompt.template,
                "description": prompt.description,
                "input_schema": {"type": "object", "properties": {}, "required": []},
                "tags": prompt.tags or [],
                "is_active": prompt.is_active,
            }

            # Convert arguments to input schema format
            if prompt.arguments:
                properties = {}
                required = []
                for arg in prompt.arguments:
                    properties[arg.name] = {"type": "string", "description": arg.description or ""}
                    if arg.required:
                        required.append(arg.name)

                prompt_data["input_schema"]["properties"] = properties
                prompt_data["input_schema"]["required"] = required

            exported_prompts.append(prompt_data)

        return exported_prompts

    async def _export_resources(self, db: Session, tags: Optional[List[str]], include_inactive: bool) -> List[Dict[str, Any]]:
        """Export resources with their content metadata.

        Args:
            db: Database session
            tags: Filter by tags
            include_inactive: Include inactive resources

        Returns:
            List of exported resource dictionaries
        """
        resources = await self.resource_service.list_resources(db, tags=tags, include_inactive=include_inactive)
        exported_resources = []

        for resource in resources:
            resource_data = {
                "name": resource.name,
                "uri": resource.uri,
                "description": resource.description,
                "mime_type": resource.mime_type,
                "tags": resource.tags or [],
                "is_active": resource.is_active,
                "last_modified": resource.updated_at.isoformat() if resource.updated_at else None,
            }

            exported_resources.append(resource_data)

        return exported_resources

    async def _export_roots(self) -> List[Dict[str, Any]]:
        """Export filesystem roots.

        Returns:
            List of exported root dictionaries
        """
        roots = await self.root_service.list_roots()
        exported_roots = []

        for root in roots:
            root_data = {"uri": str(root.uri), "name": root.name}
            exported_roots.append(root_data)

        return exported_roots

    async def _extract_dependencies(self, db: Session, entities: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:  # pylint: disable=unused-argument
        """Extract dependency relationships between entities.

        Args:
            db: Database session
            entities: Dictionary of exported entities

        Returns:
            Dictionary containing dependency mappings
        """
        dependencies = {"servers_to_tools": {}, "servers_to_resources": {}, "servers_to_prompts": {}}

        # Extract server-to-tool dependencies
        if "servers" in entities and "tools" in entities:
            for server in entities["servers"]:
                if server.get("tool_ids"):
                    dependencies["servers_to_tools"][server["name"]] = server["tool_ids"]

        return dependencies

    def _validate_export_data(self, export_data: Dict[str, Any]) -> None:
        """Validate export data against the schema.

        Args:
            export_data: The export data to validate

        Raises:
            ExportValidationError: If validation fails
        """
        required_fields = ["version", "exported_at", "exported_by", "entities", "metadata"]

        for field in required_fields:
            if field not in export_data:
                raise ExportValidationError(f"Missing required field: {field}")

        # Validate version format
        if not export_data["version"]:
            raise ExportValidationError("Version cannot be empty")

        # Validate entities structure
        if not isinstance(export_data["entities"], dict):
            raise ExportValidationError("Entities must be a dictionary")

        # Validate metadata structure
        metadata = export_data["metadata"]
        if not isinstance(metadata.get("entity_counts"), dict):
            raise ExportValidationError("Metadata entity_counts must be a dictionary")

        logger.debug("Export data validation passed")

    async def export_selective(self, db: Session, entity_selections: Dict[str, List[str]], include_dependencies: bool = True, exported_by: str = "system") -> Dict[str, Any]:
        """Export specific entities by their IDs/names.

        Args:
            db: Database session
            entity_selections: Dict mapping entity types to lists of IDs/names to export
            include_dependencies: Whether to include dependent entities
            exported_by: Username of the person performing the export

        Returns:
            Dict containing the selective export data

        Example:
            entity_selections = {
                "tools": ["tool1", "tool2"],
                "servers": ["server1"],
                "prompts": ["prompt1"]
            }
        """
        logger.info(f"Starting selective export by {exported_by}")

        export_data = {
            "version": settings.protocol_version,
            "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "exported_by": exported_by,
            "source_gateway": f"http://{settings.host}:{settings.port}",
            "encryption_method": "AES-256-GCM",
            "entities": {},
            "metadata": {"entity_counts": {}, "dependencies": {}, "export_options": {"selective": True, "include_dependencies": include_dependencies, "selections": entity_selections}},
        }

        # Export selected entities for each type
        for entity_type, selected_ids in entity_selections.items():
            if entity_type == "tools":
                export_data["entities"]["tools"] = await self._export_selected_tools(db, selected_ids)
            elif entity_type == "gateways":
                export_data["entities"]["gateways"] = await self._export_selected_gateways(db, selected_ids)
            elif entity_type == "servers":
                export_data["entities"]["servers"] = await self._export_selected_servers(db, selected_ids)
            elif entity_type == "prompts":
                export_data["entities"]["prompts"] = await self._export_selected_prompts(db, selected_ids)
            elif entity_type == "resources":
                export_data["entities"]["resources"] = await self._export_selected_resources(db, selected_ids)
            elif entity_type == "roots":
                export_data["entities"]["roots"] = await self._export_selected_roots(selected_ids)

        # Add dependencies if requested
        if include_dependencies:
            export_data["metadata"]["dependencies"] = await self._extract_dependencies(db, export_data["entities"])

        # Calculate entity counts
        for entity_type, entities in export_data["entities"].items():
            export_data["metadata"]["entity_counts"][entity_type] = len(entities)

        self._validate_export_data(export_data)

        logger.info(f"Selective export completed with {sum(export_data['metadata']['entity_counts'].values())} entities")
        return export_data

    async def _export_selected_tools(self, db: Session, tool_ids: List[str]) -> List[Dict[str, Any]]:
        """Export specific tools by their IDs.

        Args:
            db: Database session
            tool_ids: List of tool IDs to export

        Returns:
            List of exported tool dictionaries
        """
        tools = []
        for tool_id in tool_ids:
            try:
                tool = await self.tool_service.get_tool(db, tool_id)
                if tool.integration_type == "REST":  # Only export local REST tools
                    tool_data = await self._export_tools(db, None, True)
                    tools.extend([t for t in tool_data if t["name"] == tool.original_name])
            except Exception as e:
                logger.warning(f"Could not export tool {tool_id}: {str(e)}")
        return tools

    async def _export_selected_gateways(self, db: Session, gateway_ids: List[str]) -> List[Dict[str, Any]]:
        """Export specific gateways by their IDs.

        Args:
            db: Database session
            gateway_ids: List of gateway IDs to export

        Returns:
            List of exported gateway dictionaries
        """
        gateways = []
        for gateway_id in gateway_ids:
            try:
                gateway = await self.gateway_service.get_gateway(db, gateway_id)
                gateway_data = await self._export_gateways(db, None, True)
                gateways.extend([g for g in gateway_data if g["name"] == gateway.name])
            except Exception as e:
                logger.warning(f"Could not export gateway {gateway_id}: {str(e)}")
        return gateways

    async def _export_selected_servers(self, db: Session, server_ids: List[str]) -> List[Dict[str, Any]]:
        """Export specific servers by their IDs.

        Args:
            db: Database session
            server_ids: List of server IDs to export

        Returns:
            List of exported server dictionaries
        """
        servers = []
        for server_id in server_ids:
            try:
                server = await self.server_service.get_server(db, server_id)
                server_data = await self._export_servers(db, None, True)
                servers.extend([s for s in server_data if s["name"] == server.name])
            except Exception as e:
                logger.warning(f"Could not export server {server_id}: {str(e)}")
        return servers

    async def _export_selected_prompts(self, db: Session, prompt_names: List[str]) -> List[Dict[str, Any]]:
        """Export specific prompts by their names.

        Args:
            db: Database session
            prompt_names: List of prompt names to export

        Returns:
            List of exported prompt dictionaries
        """
        prompts = []
        for prompt_name in prompt_names:
            try:
                # Use get_prompt with empty args to get metadata
                await self.prompt_service.get_prompt(db, prompt_name, {})
                prompt_data = await self._export_prompts(db, None, True)
                prompts.extend([p for p in prompt_data if p["name"] == prompt_name])
            except Exception as e:
                logger.warning(f"Could not export prompt {prompt_name}: {str(e)}")
        return prompts

    async def _export_selected_resources(self, db: Session, resource_uris: List[str]) -> List[Dict[str, Any]]:
        """Export specific resources by their URIs.

        Args:
            db: Database session
            resource_uris: List of resource URIs to export

        Returns:
            List of exported resource dictionaries
        """
        resources = []
        for resource_uri in resource_uris:
            try:
                resource_data = await self._export_resources(db, None, True)
                resources.extend([r for r in resource_data if r["uri"] == resource_uri])
            except Exception as e:
                logger.warning(f"Could not export resource {resource_uri}: {str(e)}")
        return resources

    async def _export_selected_roots(self, root_uris: List[str]) -> List[Dict[str, Any]]:
        """Export specific roots by their URIs.

        Args:
            root_uris: List of root URIs to export

        Returns:
            List of exported root dictionaries
        """
        all_roots = await self._export_roots()
        return [r for r in all_roots if r["uri"] in root_uris]
