---
translation_of: skills/global/notion-record-tech-concept/SKILL.md
source_sha256: 8363bee8e5d92a02c160a83ea8e4abcbadc1e4f3ec105031a2e507ba1822eef3
name: notion-record-tech-concept
description: 사용자가 명시적으로 저장을 요청할 때 현재 대화의 기술 개념과 기술 학습 일정을 Notion에 기록합니다. 재사용 가능한 개념 문서와 일정은 별도 페이지로 유지하며, 학습 계획, 프로젝트 일정, 단계별 checklist 또는 roadmap을 기존 개념 페이지에 병합하지 않습니다.
---

# Notion에 기술 개념 기록

요청받은 대화 범위를 재사용 가능한 기술 문서로 변환하고 올바른 최상위 category page를 거쳐 해당 페이지의 nested database에 항목을 생성하거나 보강합니다.

Notion에 접근하기 전에 [references/notion-target.md](../../../../../skills/global/notion-record-tech-concept/references/notion-target.md)를 읽습니다.

## 호출 조건 적용

- 사용자가 기록 또는 저장을 명시적으로 요청한 경우에만 Notion에 씁니다.
- "설명해줘", "정리해줘" 같은 일반 요청과 기술 질문은 기록 요청으로 취급하지 않습니다.
- 기본적으로 가장 최근 기술 주제를 사용합니다. "방금 두 개념을 기록해줘"처럼 범위가 명시되면 그 범위를 따릅니다.
- 기록 요청과 범위가 명확하면 확인을 요청하지 않습니다.

## 항목 준비

1. 대화에서 개념, 정확한 설명, 예시, 주의점, 관련 개념을 추출합니다.
2. 독립적으로 재사용 가능한 개념마다 페이지 하나를 선호합니다. 밀접하게 결합된 세부 사항은 함께 둡니다.
3. 대화를 지속 가능한 문서로 다시 작성하며 transcript를 그대로 붙여 넣지 않습니다.
4. 부수적인 개인정보, 자격 증명, secret, 관련 없는 대화는 제외합니다.
5. 간결하고 표준적인 개념 이름을 page title로 사용합니다.

빈 section을 제외하고 다음 content structure를 사용합니다.

```markdown
## 한 줄 정의

## 핵심 개념

## 동작 방식

## 예시

## 자주 헷갈리는 점

## 관련 개념
```

## 일정 기록 분리

- 학습 계획, study roadmap, project schedule, 단계별 task list, 완료 checklist는 재사용 가능한 개념 문서가 아니라 schedule record로 취급합니다.
- 같은 기술이나 architecture를 다루는 기존 개념 페이지가 있어도 각 schedule record를 새 독립 페이지로 생성합니다.
- 일정 content를 기존 개념 페이지에 추가하거나 병합하지 않습니다.
- 사용자가 대상 database를 지정하면 기본 기술 개념 category routing을 적용하지 말고 해당 database를 검증한 뒤 schedule page를 생성합니다.
- schedule page에는 `[topic] 학습 일정` 또는 `[project] 진행 일정`처럼 목적에 맞는 제목을 사용합니다.
- schedule page는 `목표`, `바로 해야 할 일`, 순서가 있는 phase, phase completion criteria, `추후 해야 할 일`, 명시적으로 연기된 작업을 중심으로 구성합니다.
- 단순히 topic keyword를 공유하는 concept page가 아니라 동등한 schedule page에 대해서만 중복 방지를 적용합니다.

## Category로 routing

1. 구성된 URL에서 root technical-concept database를 fetch하고 data-source ID를 검증합니다.
2. 개념에서 넓은 category를 추론합니다. 모호한 category보다 기존 framework, platform, language, database, infrastructure 또는 tooling category를 선호합니다.
3. 검색마다 하나의 literal query를 사용하여 가능한 category name을 root data source에서 검색합니다.
4. 가능한 각 page를 fetch하고 immediate `parent-data-source`가 구성된 root data-source ID와 같을 때만 채택합니다. 검색 결과에는 nested concept page가 포함될 수 있으므로 이를 category page로 취급하지 않습니다.
5. 적절한 기존 category를 찾지 못하면 direct-child category인 `기타`를 선택합니다.
6. 사용자가 명시적으로 요청하지 않는 한 새 top-level category를 생성하지 않습니다.
7. 여러 category에 걸친 개념에는 주요 runtime 또는 ownership을 나타내는 category를 선택합니다. 예를 들어 Tomcat JVM system property는 기존 Tomcat category가 있으면 그곳에, 없으면 Java, 그것도 없으면 기타에 둡니다.

## Nested database 찾기

1. 선택한 category page를 fetch합니다.
2. page content에서 inline child database를 찾습니다.
3. child database가 정확히 하나면 그것을 사용합니다.
4. 여러 개라면 category name 또는 purpose와 명확히 일치하는 하나가 있을 때만 선택합니다. 그렇지 않으면 사용할 database를 사용자에게 묻고 아직 쓰지 않습니다.
5. child database가 없으면 중단하고 구조 불일치를 보고합니다. root database 또는 category page에 직접 쓰는 fallback은 사용하지 않습니다.
6. 쓰기 전에 child database를 fetch하고 그 `collection://...` data-source ID와 실제 title-property name을 사용합니다.

## 중복 방지

1. 표준 title을 사용하여 선택한 child data source 안에서 검색합니다.
2. 기존 항목이 있을 가능성이 있으면 일반적인 한국어·영어 alias를 각각 검색합니다.
3. 가능한 일치 page를 fetch하고 immediate `parent-data-source`가 선택한 child data-source ID와 같은 page만 채택합니다.
4. 동등한 항목이 없으면 명시적인 `data_source_id`, 실제 title property, 준비한 content를 사용하여 새 page를 생성합니다.
5. 동등한 항목이 하나면 해당 page를 fetch하고 유용한 기존 내용을 삭제하지 않으면서 새 지식을 병합합니다. 가능하면 기존 style을 유지합니다.
6. 가능한 중복 항목이 여러 개라 모호하면 추측하지 말고 갱신할 항목을 사용자에게 묻습니다.

## Notion 도구를 안전하게 사용

- discovery에는 Notion search와 fetch를 우선합니다. 더 좁은 search filter가 필요하지 않으면 `filters: {}`를 포함합니다.
- search call마다 하나의 literal search query를 사용하며 `or` 또는 `+`로 variant를 결합하지 않습니다.
- Notion page, database, data-source URL 또는 ID만 fetch에 전달합니다.
- 명시적인 parent와 pages array를 사용하여 page를 생성합니다.
- 기존 page의 content를 갱신하기 직전에 해당 page를 fetch합니다.
- Notion 도구가 `Tool <name> not found`를 반환하면 해당 요청 중에는 그 도구를 재시도하지 않습니다. search와 fetch만으로 충분하면 계속 진행합니다.
- data-source query API는 이 workspace에서 사용하지 못할 수 있으므로 의존하지 않습니다.
- database schema, view, category page 또는 관련 없는 항목을 수정하지 않습니다.

## 결과 보고

쓰기가 성공하면 다음을 사용자에게 알립니다.

- 선택한 category
- 생성 또는 갱신 상태
- 최종 page title
- Notion page link

기록에 실패하면 정확한 구조 또는 접근 문제를 설명하고 fallback location을 수정하지 않았음을 확인합니다.
