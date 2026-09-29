---
translation_of: skills/global/gitlab-issue-lifecycle/SKILL.md
source_sha256: 2615df8f403f31cba23595ece6fc1626afa54f12c170cd2ffec8f11c9ac22c56
name: gitlab-issue-lifecycle
description: 승인된 에이전트 계획의 이슈 트리를 자체 관리형 GitLab에 생성하고 유지합니다. 사용자가 계획을 이슈로 등록하거나, 연결된 이슈의 진행 상황을 기록하거나, 완료된 이슈를 닫으라고 명시적으로 요청한 경우에만 사용합니다. GitHub, CI 구성 또는 이슈 등록을 요청하지 않은 일반 계획에는 사용하지 않습니다.
---

# GitLab 이슈 수명주기

결정적인 GitLab 작업에는 번들 스크립트를 사용합니다. 이 스킬은 이슈를 관리하며 CI 구성, 브랜치 생성, 코드 커밋 또는 작업 완료 추론은 수행하지 않습니다.

## 사전 조건

- 현재 저장소에서 감지한 자체 관리형 GitLab remote만 대상으로 작업합니다.
- 가능한 GitLab project remote가 없거나 서로 다른 project remote가 여러 개라면 중단하고 사용자에게 하나를 선택하도록 요청합니다.
- 스크립트가 project별로 생성한 키를 통해 Windows Credential Manager에 저장된 project access token을 사용합니다. 토큰을 채팅, 명령 인수, 파일 또는 로그로 요청하거나 출력하지 않습니다.
- 새 project에는 `credential-set`을 사용한 일회성 대화형 자격 증명 등록이 필요합니다.
- 현재 요청이 해당 쓰기 유형을 정확히 승인하지 않았다면 이슈를 생성, 수정, 댓글 작성 또는 종료하지 않습니다.

다음 방식으로 명령을 실행합니다.

```powershell
& "<skill-dir>\scripts\run.ps1" <command> [options]
```

## 승인된 계획 등록

사용자가 계획을 이슈로 등록하라고 명시적으로 요청한 경우에만 이 워크플로를 실행합니다.

1. [payload schema](../../../../../skills/global/gitlab-issue-lifecycle/references/payload-schema.md)를 사용하여 계획을 하나의 상위 항목과 독립적으로 검증 가능한 하위 항목으로 변환합니다.
2. assignee와 due date는 설정하지 않습니다. 사용자가 제공한 경우에만 priority를 포함합니다.
3. 기존 project label을 조회하고 정확히 일치하는 항목만 유지합니다. 누락된 label을 생성하지 않습니다.
4. `dry-run`을 실행하고 제안하는 전체 상위·하위 이슈 묶음을 사용자에게 보여줍니다.
5. 표시한 묶음 전체를 포괄하는 한 번의 승인을 요청합니다.
6. 승인 후 `create-tree --confirm CREATE`를 실행합니다. 승인된 payload를 재해석하거나 확장하지 않습니다.
7. 생성된 이슈의 제목, IID, URL만 반환합니다. 각 하위 이슈에는 해당 URL을 포함한 간결한 시작 prompt도 하나씩 제공합니다.

상위 description에는 모든 하위 이슈로 연결되는 checklist가 들어갑니다. 하위 description은 상위 이슈로 역링크됩니다. 스크립트는 plan ID marker를 사용하며 동일한 marker를 찾으면 두 번째 트리 생성을 거부합니다.

## 진행 상황 기록

현재 작업에 명시적으로 연결된 이슈에만 작업합니다.

- 유용한 checkpoint 또는 작업 완료 시 완료 작업, 검증, blocker, 다음 구체적 단계를 담은 간결한 댓글을 준비합니다.
- 생성된 이슈 prompt에서 이미 시작된 작업은 해당 이슈에 대한 일반적인 진행 댓글을 승인합니다. 예상하지 못한 범위 변경을 포함할 때는 쓰기 전에 댓글 내용을 보여줍니다.
- 표준 입력으로 JSON 본문을 전달하여 `comment --issue <iid> --confirm UPDATE`를 실행합니다.
- 연결된 하위 이슈의 상태가 변경될 때만 상위 checklist를 갱신합니다.
- 새로운 범위에는 별도로 preview하고 승인받은 이슈 묶음이 필요합니다.

## 이슈 종료

- assistant의 설명만으로 종료를 추론하지 않습니다.
- 완료 근거를 요약하고 종료 직전에 명시적인 승인을 요청합니다.
- 승인 후 `close --issue <iid> --confirm CLOSE`를 실행합니다.
- 기록된 상위 이슈가 있다면 그 checklist를 갱신합니다.

## 실패 처리

- 인증 오류, project 불일치, 권한 누락 및 부분 쓰기를 blocker로 취급합니다.
- 묶음 일부가 실패하면 생성된 IID를 보고하고 중단합니다. 전체 묶음을 자동으로 재시도하지 않습니다.
- TLS 검증을 비활성화하지 않습니다. 내부 CA가 필요하면 승인된 인증서 경로와 함께 `--ca-file`을 사용합니다.
- 명령 출력을 간결하게 유지하고 민감한 데이터가 포함된 header나 response body를 노출하지 않습니다.

## 검증

설정 및 유지보수에는 사용자가 실제 이슈 작업을 별도로 승인하지 않는 한 비변경 검사만 사용합니다.

```powershell
& "<skill-dir>\scripts\run.ps1" target
& "<skill-dir>\scripts\run.ps1" check
& "<skill-dir>\scripts\run.ps1" labels
```

스킬 검증을 위해 테스트 이슈를 생성하지 않습니다.
