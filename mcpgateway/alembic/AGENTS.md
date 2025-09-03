# MCP Gateway Alembic - 데이터베이스 마이그레이션 관리 가이드

## 개요

`alembic/` 폴더는 MCP Gateway의 데이터베이스 스키마 관리를 담당하는 Alembic 마이그레이션 시스템을 포함합니다. 데이터베이스 스키마의 버전 관리, 변경 추적, 롤백 기능을 제공합니다.

## Alembic 구조 개요

```bash
alembic/
├── alembic.ini                    # Alembic 설정 파일
├── env.py                         # 마이그레이션 실행 환경 설정
├── script.py.mako                 # 마이그레이션 스크립트 템플릿
├── README.md                      # 상세 사용 가이드
└── versions/                      # 마이그레이션 스크립트들
    ├── 1fc1795f6983_merge_a2a_and_custom_name_changes.py
    ├── 34492f99a0c4_add_comprehensive_metadata_to_all_.py
    ├── 3b17fdc40a8d_add_passthrough_headers_to_gateways_and_.py
    ├── 733159a4fa74_add_display_name_to_tools.py
    ├── add_a2a_agents_and_metrics.py
    ├── add_oauth_tokens_table.py
    ├── b77ca9d2de7e_uuid_pk_and_slug_refactor.py
    ├── c9dd86c0aac9_remove_original_name_slug_and_added_.py
    ├── cc7b95fec5d9_add_tags_support_to_all_entities.py
    ├── e4fc04d1a442_add_annotations_to_tables.py
    ├── e75490e949b1_add_improved_status_to_tables.py
    ├── eb17fd368f9d_merge_passthrough_headers_and_tags_.py
    └── f8c9d3e2a1b4_add_oauth_config_to_gateways.py
```

## 핵심 컴포넌트 설명

### `alembic.ini` - 설정 파일
**역할**: Alembic의 전역 설정을 정의
**주요 설정**:
- 데이터베이스 연결 정보
- 마이그레이션 파일 위치
- 스크립트 템플릿 설정
- 로깅 설정

```ini
[alembic]
script_location = mcpgateway/alembic
sqlalchemy.url = driver://user:pass@localhost/dbname

[loggers]
keys = root,sqlalchemy,alembic
```

### `env.py` - 실행 환경
**역할**: 마이그레이션 실행 시 필요한 환경을 설정
**주요 기능**:
- 데이터베이스 연결 설정
- SQLAlchemy 메타데이터 연결
- 마이그레이션 컨텍스트 구성

```python
# SQLAlchemy 모델과 Alembic 연결
from mcpgateway.db import Base
target_metadata = Base.metadata
```

### `script.py.mako` - 스크립트 템플릿
**역할**: 새로운 마이그레이션 파일 생성 시 사용되는 Jinja2 템플릿
**포함 내용**:
- 업그레이드 함수 템플릿
- 다운그레이드 함수 템플릿
- 리비전 식별자 및 의존성 설정

## 마이그레이션 파일 구조

### 표준 마이그레이션 파일 형식

```python
"""add_comprehensive_metadata_to_all_tables

Revision ID: 34492f99a0c4
Revises: 3b17fdc40a8d
Create Date: 2024-01-15 10:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '34492f99a0c4'
down_revision: Union[str, None] = '3b17fdc40a8d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """업그레이드 로직"""
    # 데이터베이스 변경 작업들
    op.add_column('tools', sa.Column('created_by', sa.String(), nullable=True))
    op.add_column('tools', sa.Column('modified_by', sa.String(), nullable=True))

def downgrade() -> None:
    """다운그레이드 로직"""
    # 변경사항 되돌리기
    op.drop_column('tools', 'created_by')
    op.drop_column('tools', 'modified_by')
```

## 주요 마이그레이션 이력

### 코어 기능 마이그레이션들

#### 1. 기본 스키마 생성
- **f8c9d3e2a1b4**: OAuth 구성 추가
- **3b17fdc40a8d**: 게이트웨이 패스스루 헤더 추가
- **eb17fd368f9d**: 패스스루 헤더와 태그 병합

#### 2. 메타데이터 향상
- **34492f99a0c4**: 모든 테이블에 포괄적 메타데이터 추가
- **e4fc04d1a442**: 테이블에 어노테이션 추가
- **e75490e949b1**: 향상된 상태 필드 추가

#### 3. 태그 시스템
- **cc7b95fec5d9**: 모든 엔티티에 태그 지원 추가

#### 4. A2A 기능
- **add_a2a_agents_and_metrics**: A2A 에이전트 및 메트릭 추가
- **1fc1795f6983**: A2A와 커스텀 이름 변경사항 병합

#### 5. 네이밍 및 구조 개선
- **733159a4fa74**: 도구에 표시 이름 추가
- **b77ca9d2de7e**: UUID PK 및 슬러그 리팩토링
- **c9dd86c0aac9**: 원본 이름 슬러그 제거 및 표시 이름 추가

## 마이그레이션 작업 유형

### 1. 테이블 작업
```python
# 테이블 생성
op.create_table('new_table',
    sa.Column('id', sa.Integer(), primary_key=True),
    sa.Column('name', sa.String(), nullable=False)
)

# 테이블 삭제
op.drop_table('old_table')
```

### 2. 컬럼 작업
```python
# 컬럼 추가
op.add_column('table_name', sa.Column('new_column', sa.String()))

# 컬럼 수정
op.alter_column('table_name', 'column_name',
    existing_type=sa.String(),
    type_=sa.Text()
)

# 컬럼 삭제
op.drop_column('table_name', 'column_name')
```

### 3. 인덱스 및 제약조건
```python
# 인덱스 생성
op.create_index('idx_table_column', 'table_name', ['column_name'])

# 외래 키 제약조건 추가
op.create_foreign_key(
    'fk_table_ref',
    'table_name', 'ref_table',
    ['ref_id'], ['id']
)

# 유니크 제약조건
op.create_unique_constraint('uq_table_column', 'table_name', ['column_name'])
```

## 마이그레이션 워크플로우

### 1. 모델 변경
```python
# mcpgateway/db.py에서 모델 수정
class Tool(Base):
    # 새로운 필드 추가
    display_name = Column(String, nullable=True)
```

### 2. 마이그레이션 생성
```bash
# 변경사항 감지하여 마이그레이션 파일 생성
alembic revision --autogenerate -m "add display_name to tools"

# 또는 Make 명령어 사용
make db-new MSG="add display_name to tools"
```

### 3. 마이그레이션 검토 및 수정
```python
# 생성된 마이그레이션 파일 검토
# alembic/versions/xxxxx_add_display_name_to_tools.py

def upgrade():
    op.add_column('tools', sa.Column('display_name', sa.String(), nullable=True))

def downgrade():
    op.drop_column('tools', 'display_name')
```

### 4. 마이그레이션 적용
```bash
# 데이터베이스에 적용
alembic upgrade head

# 또는 Make 명령어 사용
make db-up
```

### 5. 마이그레이션 롤백 (필요시)
```bash
# 마지막 마이그레이션 롤백
alembic downgrade -1

# 특정 리비전으로 롤백
alembic downgrade <revision_id>

# 또는 Make 명령어 사용
make db-down
make db-down REV=<revision_id>
```

## 마이그레이션 모범 사례

### 1. 의미 있는 커밋 메시지
```bash
# 좋은 예
alembic revision --autogenerate -m "add user authentication fields to tools table"

# 나쁜 예
alembic revision --autogenerate -m "changes"
```

### 2. 작은 단위의 마이그레이션
```python
# 하나의 마이그레이션에 하나의 논리적 변경만 포함
def upgrade():
    # 사용자 관련 필드들만
    op.add_column('tools', sa.Column('created_by', sa.String()))
    op.add_column('tools', sa.Column('updated_by', sa.String()))

# 별도의 마이그레이션으로 분리
# def upgrade():  # 다른 파일에서
#     op.add_column('tools', sa.Column('description', sa.Text()))
```

### 3. 안전한 다운그레이드
```python
def upgrade():
    # 업그레이드 시 NOT NULL 제약조건 추가
    op.add_column('tools', sa.Column('name', sa.String(), nullable=False))
    # 기존 데이터에 기본값 설정
    op.execute("UPDATE tools SET name = 'unnamed' WHERE name IS NULL")

def downgrade():
    # 다운그레이드 시 안전하게 제거
    op.drop_column('tools', 'name')
```

## 데이터베이스별 고려사항

### SQLite
```python
# SQLite는 제약조건 삭제가 제한적
def upgrade():
    # 복잡한 변경 시 테이블 재생성 패턴 사용
    op.rename_table('old_table', 'old_table_backup')
    op.create_table('new_table', ...)
    op.execute('INSERT INTO new_table SELECT * FROM old_table_backup')
    op.drop_table('old_table_backup')
```

### PostgreSQL
```python
# PostgreSQL은 고급 기능 활용 가능
def upgrade():
    # JSONB 타입 활용
    op.add_column('tools', sa.Column('metadata', postgresql.JSONB()))
    # GIN 인덱스 생성
    op.create_index('idx_tools_metadata', 'tools', ['metadata'], postgresql_using='gin')
```

## 모니터링 및 디버깅

### 마이그레이션 상태 확인
```bash
# 현재 적용된 리비전 확인
alembic current

# 마이그레이션 이력 조회
alembic history --verbose

# Make 명령어 사용
make db-current
make db-history
```

### 마이그레이션 충돌 해결
```python
# 병합 충돌 발생 시
def upgrade():
    # 여러 브랜치의 변경사항 통합
    # 충돌하는 마이그레이션들을 수동으로 통합

def downgrade():
    # 복잡한 롤백 로직 구현
    # 중간 상태로의 안전한 롤백 보장
```

## CI/CD 통합

### 자동 마이그레이션 적용
```yaml
# .github/workflows/deploy.yml
- name: Run database migrations
  run: |
    alembic upgrade head
  env:
    DATABASE_URL: ${{ secrets.DATABASE_URL }}
```

### 마이그레이션 검증
```yaml
# 마이그레이션 파일이 유효한지 검증
- name: Validate migrations
  run: |
    python -c "import alembic.config; alembic.config.main(['--config', 'mcpgateway/alembic.ini', 'check'])"
```

## 결론

alembic/ 폴더는 MCP Gateway의 데이터베이스 스키마를 안정적이고 추적 가능하게 관리하는 핵심 컴포넌트입니다:

- **버전 관리**: 모든 스키마 변경사항을 체계적으로 추적
- **안전성**: 롤백 기능으로 변경사항을 안전하게 되돌릴 수 있음
- **협업**: 팀원 간 스키마 변경사항을 동기화
- **자동화**: CI/CD 파이프라인에 쉽게 통합 가능
- **다중 DB 지원**: SQLite, PostgreSQL 등 다양한 데이터베이스 지원

이러한 마이그레이션 시스템을 통해 데이터베이스 스키마를 안정적으로 발전시키고, 프로덕션 환경에서의 변경사항을 안전하게 관리할 수 있습니다.
