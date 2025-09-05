# AGENTS: 배포 자산 모음

실제 환경 배포를 위한 K8s 매니페스트, Ansible 롤북, Terraform 예제가 포함되어 있습니다. 인프라 수준/운영 문화에 따라 적합한 방식을 선택하세요.

## 디렉터리 구성

- `k8s/`: 수동/반자동 배포용 K8s 매니페스트
- `ansible/`: 서버 프로비저닝 및 애플리케이션 롤아웃 자동화
- `terraform/`: 클라우드 리소스(IaaS/PaaS) 프로비저닝 샘플

## K8s 매니페스트

```bash
kubectl apply -f deployment/k8s/postgres-*.yaml
kubectl apply -f deployment/k8s/redis-*.yaml
kubectl apply -f deployment/k8s/mcp-context-forge-deployment.yaml
kubectl apply -f deployment/k8s/mcp-context-forge-service.yaml
kubectl apply -f deployment/k8s/mcp-context-forge-ingress.yaml
```

- 프로덕션에서는 `charts/mcp-stack` 사용을 권장합니다(템플릿화/값 분리).

## Ansible(IBM Cloud 예시 포함)

```bash
cd deployment/ansible/ibm-cloud
ansible-playbook -i inventory.ini site.yml
```

- 사전 준비: SSH, 변수 파일, 클라우드 자격증명

## Terraform(IBM Cloud 예시 포함)

```bash
cd deployment/terraform/ibm-cloud
terraform init
terraform plan -out tfplan
terraform apply tfplan
```

- 원복 전략(`terraform destroy`)과 상태 파일 보안을 고려하세요.

## 보안/설정 체크리스트

- `.env` → 시크릿/ConfigMap으로 분리, `make check-env`로 키 검증
- `JWT_SECRET_KEY` 설정 필수, 네트워크/Ingress 보안 강화
- 관측성: OpenTelemetry, 로그 수집, 메트릭/알람 연동

## 탐색

- **⬆️ 프로젝트 루트**: [../AGENTS.md](../AGENTS.md)
