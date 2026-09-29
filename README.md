# agent-playbook
AI 에이전트를 일관되게 활용하기 위한 재사용 가능한 스킬, 규칙, 지침 및 작업 흐름 모음.

## 목록

### agents

| 이름 | 설명 | 문서 | 경로 |
| --- | --- | --- | --- |
| **code_reviewer** | 정확성, 보안, 회귀, 테스트 범위, 아키텍처, 가독성, 성능과 의존성 위험을 중점적으로 검토하는 읽기 전용 시니어 코드 리뷰어입니다. 코드 변경, diff, 커밋, PR 리뷰 시 적극적으로 사용하세요. | [en](agents/global/code-reviewer/code_reviewer.toml)/[kr](translations/ko/agents/global/code-reviewer/code_reviewer.toml) | `agents/global/code-reviewer/code_reviewer.toml` |

### rules

| 이름 | 설명 | 문서 | 경로 |
| --- | --- | --- | --- |
| **response-readability-and-structure** | 사용자가 선택한 접근 방식을 유지하면서 명확성, 간결성, 실용성과 절제된 이모지 사용을 기준으로 응답을 구성합니다. | [en](rules/global/response-readability-and-structure/response-readability-and-structure.md)/[kr](translations/ko/rules/global/response-readability-and-structure/response-readability-and-structure.md) | `rules/global/response-readability-and-structure/response-readability-and-structure.md` |

### skills

| 이름 | 설명 | 문서 | 경로 |
| --- | --- | --- | --- |
| **agent-playbook-installer** | 로컬 D:\\agent-playbook 저장소의 Codex skill과 rule을 조회, 설치, 업데이트, 상태 확인 또는 제거합니다. 사용자가 playbook 산출물을 Codex에 적용하려 할 때 사용하며, 산출물 작성이나 다른 저장소의 설치에는 사용하지 않습니다. | [en](skills/global/agent-playbook-installer/SKILL.md)/[kr](translations/ko/skills/global/agent-playbook-installer/SKILL.md) | `skills/global/agent-playbook-installer/SKILL.md` |
| **agent-playbook-manager** | D:\\agent-playbook 저장소의 카테고리, 영어-한국어 양방향 동기화, 해시 및 README 색인 규칙에 따라 재사용 가능한 Agent, Skill, Rule과 Prompt를 생성하거나 수정합니다. 플레이북 산출물에만 사용하며 일반 프로젝트 파일이나 문서를 이 저장소로 이동하지 않습니다. 사용자가 설치를 요청하지 않으면 ~/.codex로 복사하지 않습니다. | [en](skills/global/agent-playbook-manager/SKILL.md)/[kr](translations/ko/skills/global/agent-playbook-manager/SKILL.md) | `skills/global/agent-playbook-manager/SKILL.md` |
| **deep-interview** | 모호한 요청을 소크라테스식 질문으로 구체화해 실행 가능한 요구사항으로 정리합니다. | [en](skills/global/deep-interview/SKILL.md)/[kr](translations/ko/skills/global/deep-interview/SKILL.md) | `skills/global/deep-interview/SKILL.md` |
| **github-issue-lifecycle** | 승인된 에이전트 계획의 이슈 트리를 GitHub에 생성하고 유지합니다. 사용자가 계획을 이슈로 등록하거나, 연결된 이슈의 진행 상황을 기록하거나, 완료된 이슈를 닫으라고 명시적으로 요청한 경우에만 사용합니다. GitLab, CI 구성 또는 이슈 등록을 요청하지 않은 일반 계획에는 사용하지 않습니다. | [en](skills/global/github-issue-lifecycle/SKILL.md)/[kr](translations/ko/skills/global/github-issue-lifecycle/SKILL.md) | `skills/global/github-issue-lifecycle/SKILL.md` |
| **gitlab-issue-lifecycle** | 승인된 에이전트 계획의 이슈 트리를 자체 관리형 GitLab에 생성하고 유지합니다. 사용자가 계획을 이슈로 등록하거나, 연결된 이슈의 진행 상황을 기록하거나, 완료된 이슈를 닫으라고 명시적으로 요청한 경우에만 사용합니다. GitHub, CI 구성 또는 이슈 등록을 요청하지 않은 일반 계획에는 사용하지 않습니다. | [en](skills/global/gitlab-issue-lifecycle/SKILL.md)/[kr](translations/ko/skills/global/gitlab-issue-lifecycle/SKILL.md) | `skills/global/gitlab-issue-lifecycle/SKILL.md` |
| **notion-record-tech-concept** | 사용자가 명시적으로 저장을 요청할 때 현재 대화의 기술 개념과 기술 학습 일정을 Notion에 기록합니다. 재사용 가능한 개념 문서와 일정은 별도 페이지로 유지하며, 학습 계획, 프로젝트 일정, 단계별 checklist 또는 roadmap을 기존 개념 페이지에 병합하지 않습니다. | [en](skills/global/notion-record-tech-concept/SKILL.md)/[kr](translations/ko/skills/global/notion-record-tech-concept/SKILL.md) | `skills/global/notion-record-tech-concept/SKILL.md` |
| **write-work-log** | 사용자가 $write-work-log를 호출하거나 "개발일지 작성해줘", "작업 일지로 정리해줘"처럼 완료한 개발 또는 작업을 일지로 명시적으로 요청했을 때, 현재 대화와 확인 가능한 작업 증거를 바탕으로 한국어 Markdown 작업 일지를 채팅에 작성한다. 일반적인 작업 요약, 자동 회고, 파일 문서 생성에는 사용하지 않는다. | [en](skills/global/write-work-log/SKILL.md)/[kr](translations/ko/skills/global/write-work-log/SKILL.md) | `skills/global/write-work-log/SKILL.md` |
