---
translation_of: skills/global/agent-playbook-manager/SKILL.md
source_sha256: 4e160540f13f182744cfb875a531a113f337d410eeaed71aa3aa970167fd2dd0
name: agent-playbook-manager
description: D:\agent-playbook 저장소의 카테고리, 한국어 번역, 해시 및 README 색인 규칙에 따라 재사용 가능한 Codex Agent, Skill, Rule과 Prompt를 생성하거나 수정합니다. 플레이북 산출물에만 사용하며 일반 프로젝트 파일이나 문서를 이 저장소로 이동하지 않습니다.
---

# 에이전트 플레이북 관리자

`D:\agent-playbook`에서 재사용 가능한 플레이북 산출물을 관리한다. 이 저장소를 기준 원본으로 유지한다. 사용자가 별도로 설치를 요청하지 않는 한 생성한 산출물을 Codex에 설치하지 않는다. 기본적으로 전역 설치되는 산출물은 이 관리 Skill뿐이다.

## 적용 범위

다음과 같은 재사용 가능한 산출물을 생성하거나 수정할 때 적용한다.

- Custom Agent
- Codex Skill
- Rule 또는 지속적으로 적용할 지침
- 재사용 가능한 Prompt

일반 프로젝트 코드, 저장소 문서, 보고서 또는 일회성 Markdown 파일에는 적용하지 않는다.

## 분류

다음 경로 중 하나만 사용한다.

```text
agents/global/<name>/
skills/global/<name>/
rules/global/<name>/
prompts/global/<name>/
```

영어 진입점은 다음 경로 아래에 동일한 구조로 반영한다.

```text
translations/ko/<동일한-상대-경로>
```

진입점 규칙:

- Agent: 산출물 디렉터리 바로 아래에 TOML 파일 하나
- Skill: `SKILL.md`
- Rule: 산출물 디렉터리 바로 아래에 Markdown 파일 하나
- Prompt: 산출물 디렉터리 바로 아래에 Markdown 파일 하나

산출물 디렉터리 이름에는 소문자, 숫자와 하이픈을 사용한다. `misc` 카테고리나 산출물별 README를 만들지 않는다. README는 저장소 루트의 `README.md` 하나만 사용한다.

분류가 모호하면 예상 카테고리와 전체 경로를 제시하고 확인을 기다린다. 분류가 명확하면 쓰기 전에 정확한 대상 경로를 사용자에게 알린다.

## 원본과 번역

영어 파일을 기준 원본으로 사용한다. 같은 작업에서 한국어 대응 파일을 항상 함께 생성하거나 수정한다.

- Markdown 번역은 YAML frontmatter에 `translation_of`와 `source_sha256`을 선언한다.
- TOML 번역은 TOML 스키마를 깨뜨리지 않도록 같은 필드를 파일 선두 주석으로 선언한다.
- 동작과 설명은 번역하되 식별자, 명령, 경로, 코드와 스키마 키는 번역으로 인해 깨질 수 있으므로 원형을 유지한다.
- 영어와 한국어 내용이 최종 확정된 후 다음 명령으로 번역 메타데이터를 갱신한다.

```powershell
python D:\agent-playbook\.github\scripts\sync_translation_hash.py <영어-저장소-상대-경로>
```

해시만 갱신하지 않는다. 최종 영어 원본을 기준으로 한국어 내용을 먼저 검토하고 수정한다.

## 저장소 작업 흐름

1. `D:\agent-playbook`, Git 상태와 적용되는 저장소 지침을 확인한다.
2. 관련 없는 사용자 변경을 보존한다. 겹치는 변경을 안전하게 처리할 수 없으면 중단한다.
3. 산출물을 분류하고 영어 및 한국어 대상 경로를 알린다.
4. 영어 진입점을 실행 가능한 원본 형식으로 생성하거나 수정한다.
5. 한국어 대응 파일을 같은 원본 형식으로 생성하거나 수정한다.
6. 번역 메타데이터를 갱신한다.
7. 루트 색인을 다시 생성한다.

```powershell
python D:\agent-playbook\.github\scripts\generate_readme_index.py
```

8. 작업을 완료하기 전에 검증한다.

```powershell
python D:\agent-playbook\.github\scripts\generate_readme_index.py --check
```

Skill에는 `quick_validate.py`, Agent에는 TOML 파싱, 변경된 Python 스크립트에는 Python 컴파일, 저장소에는 `git diff --check` 등 형식에 적합한 검증도 수행한다.

카테고리 구조가 바뀌면 같은 작업에서 README 생성기와 `.github/workflows/update-readme-index.yml`을 모두 확인하고 수정한다.

## 권한 경계

- `D:\agent-playbook` 쓰기에는 명시적 파일시스템 승인이 필요할 수 있으므로 필요한 경우 승인을 요청한다.
- 별도 요청 없이 커밋, 푸시, 병합, 브랜치 보호 변경 또는 생성 산출물 설치를 수행하지 않는다.
- 누락된 자격 증명, 사용할 수 없는 서비스, 샌드박스 제한 또는 실패한 검증을 우회하지 않는다.
- 번역과 검증을 완료한 뒤 성공을 보고한다.
