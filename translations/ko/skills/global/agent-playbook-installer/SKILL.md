---
translation_of: skills/global/agent-playbook-installer/SKILL.md
source_sha256: a16fe3a75861a0fbec3b8f38ea5712e0b1d2edc720a12c2e3b38fd310f8d8580
name: agent-playbook-installer
description: 로컬 D:\agent-playbook 저장소의 Codex skill과 rule을 조회, 설치, 업데이트, 상태 확인 또는 제거합니다. 사용자가 playbook 산출물을 Codex에 적용하려 할 때 사용하며, 산출물 작성이나 다른 저장소의 설치에는 사용하지 않습니다.
---

# Agent Playbook Installer

`D:\agent-playbook`을 원본으로 사용하고 현재 로컬 체크아웃만 대상으로 작업한다. 설치 과정에서 pull, commit 또는 push하지 않는다.

## 작업 흐름

1. 저장소 상태를 확인하고 요청한 산출물을 `skills/global/` 또는 `rules/global/` 아래의 정확한 이름으로 식별한다.
2. 목록이나 상태 확인에는 `-List` 또는 `-Status`를 사용한다. 이 작업들은 읽기 전용이다.
3. 사용자가 변경 작업을 명시적으로 요청한 경우에만 산출물을 설치, 업데이트 또는 제거한다. "X 설치해줘" 또는 "X 제거해줘" 같은 요청은 해당 산출물에 대한 충분한 권한이다.
4. 요청 대상, 덮어쓰기 동작 또는 영향을 받는 전역 파일이 불명확하면 `-WhatIf`을 사용한다. 사용자가 로컬에서 수정된 관리 대상 설치본의 교체를 승인하지 않았다면 `-Force`를 사용하지 않는다.
5. 원본 산출물, 설치 위치, 결과 상태와 새로 설치한 skill을 Codex가 발견하기 위해 새 채팅이나 재시작이 필요할 수 있는지를 보고한다.

런타임 파일을 직접 복사하거나 편집하지 말고 결정적 래퍼를 실행한다.

```powershell
D:\agent-playbook\scripts\install-playbook.ps1 -List
D:\agent-playbook\scripts\install-playbook.ps1 -Status
D:\agent-playbook\scripts\install-playbook.ps1 -Name <artifact-name>
D:\agent-playbook\scripts\install-playbook.ps1 -Name <artifact-name> -Uninstall
```

## 설치 동작

- Skill은 `%USERPROFILE%\.codex\skills\<name>`으로 복사한다. 저장소가 원본이며 자동 동기화하지 않는다.
- Rule은 `%USERPROFILE%\.codex\AGENTS.md`의 설치기 관리 구역에 렌더링한다. 해당 구역 밖의 내용은 사용자 소유이므로 변경하지 않는다.
- 설치 스탬프에 원본과 설치 대상 해시를 기록한다. 설치본이나 관리 중인 rule 구역이 설치기 외부에서 변경됐다면 덮어쓰지 않고 중단한다.
- 설치기는 영어 런타임 산출물을 배포한다. `translations/ko/` 아래의 한국어 파일은 문서 대응본이며 런타임 입력이 아니다.
- `%USERPROFILE%\.codex\rules\`를 playbook 지침의 설치 위치로 사용하지 않는다. 해당 디렉터리는 명령 실행 정책용이다.

사용자가 저장소 산출물을 생성하거나 수정하려는 경우에는 `$agent-playbook-manager`를 사용한다.
