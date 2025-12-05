<img width="631" height="517" alt="image" src="https://github.com/user-attachments/assets/7b817aee-8bbf-4d9f-8959-f7e0194f4b7f" />


🥗 AI Nutritionist Agent System

사용자의 식단 기록을 자동으로 분석하고, 영양소 계산·식단 추천·일일/주간 리포트를 생성하는 LLM 기반 영양 관리 에이전트 시스템입니다.

각 기능은 독립적인 Tool 모듈로 구성되며, 메인 에이전트는 REAct 구조로 이를 호출해 완전한 코칭 경험을 제공합니다.

🚀 주요 기능
1️⃣ Basal Metabolic Rate & 목표 섭취량 계산

파일: tool/bmrcal.py

사용자 정보(나이, 성별, 체중, 키, 활동량)를 기반으로 BMR 계산

감량/유지/증량 목표에 맞춘 목표 칼로리와 탄·단·지 비율 자동 산출

결과는 log/target_macros.json에 저장되어 모든 기능이 공유함

2️⃣ 자연어 기반 식단 영양소 분석

파일: tool/calnnutri.py

“오늘 점심에 제육덮밥 먹었어”처럼 자연어 식단 입력 → 영양 성분 자동 계산

FATSECRET API를 사용해 칼로리·탄수화물·단백질·지방·나트륨 등 상세 영양소 조회

결과는 log/nutrition.txt에 시간순으로 누적 저장

AI가 이해 가능한 기록 형태로 관리됨

3️⃣ 기록 기반 개인 맞춤 식단 추천

파일: tool/diet_agent.py

부족한 영양소·과다 섭취 항목 분석

TAVILY API를 이용해 현실적인 음식 후보를 검색하고 조합

“단백질이 부족하니 이런 메뉴를 추천합니다” 같은 자연스러운 텍스트로 제공

목표(감량/근육 증가/균형 유지)에 최적화된 추천

4️⃣ 일일/주간 식단 리포트 자동 생성

파일: tool/reporter.py

nutrition.txt, private.json, target_macros.json을 기반으로
LLM이 정성적 코칭 리포트(JSON) 생성

📌 일일 리포트 (log/daily.json)
{
  "평가": "...",
  "문제": "...",
  "차후전략": "..."
}

📌 주간 리포트 (log/weekly.json)
{
  "평가": "...",
  "긍정": "...",
  "문제": "...",
  "차후전략": "..."
}


LLM이 코치처럼 피드백을 작성하며
앞으로 개선할 수 있는 전략을 bullet 스타일로 제시

JSON 포맷으로 저장되어 다른 시스템에서도 쉽게 활용 가능

5️⃣ REAct 기반 메인 에이전트 통합

파일: main.py (예상 위치)

사용자의 자연어 입력을 분석해 필요한 Tool을 자동 선택

예:

“내일 식단 추천해줘” → diet_agent 호출

“오늘 먹은 것 분석해줘” → calnnutri 호출

“이번주 평가 만들어줘” → reporter.weekly 호출

Tool Output(JSON)을 조합해 대화형 응답 생성

기능 확장이 쉬운 모듈형 아키텍처

📁 프로젝트 구조
project_root/
  tool/
    bmrcal.py          # BMR 및 목표 칼로리 계산
    calnnutri.py       # 자연어 식단 → 영양 분석(FatSecret)
    diet_agent.py      # Tavily 기반 식단 추천
    reporter.py        # 일일/주간 리포트(JSON) 생성
  log/
    nutrition.txt       # 누적 식단 기록
    private.json        # 사용자 프로필
    target_macros.json  # 목표 섭취량
    daily.json          # LLM 일일 리포트 결과
    weekly.json         # LLM 주간 리포트 결과
  main.py               # REAct 기반 에이전트 실행부
  README.md             # 프로젝트 설명

🧪 사용 흐름 (Workflow)

사용자 프로필 입력 (private.json)

bmrcal.py
→ 목표 칼로리 및 탄단지 설정

매 식사 입력:
→ calnnutri.py가 자연어 분석 → nutrition.txt에 기록

필요할 때:

diet_agent.py → 부족 영양소 기반 식단 추천

reporter.py → 일일/주간 리포트 생성

모든 기능은 main.py에서 자동 orchestration됨

💡 프로젝트의 핵심 가치

자연어 기반의 완전한 자동 영양 관리

AI 분석 + 외부 API(FatSecret/Tavily) 결합 구조

JSON 기반 내보내기로 확장성 높음

정량(영양소) + 정성(리포트) 분석이 모두 가능

코치 경험을 LLM이 자동 제공

🛠 설치 및 실행
pip install -r requirements.txt
python app.py


리포트만 테스트하고 싶다면:


python tool/reporter.py daily
python tool/reporter.py weekly

<img width="1004" height="617" alt="image" src="https://github.com/user-attachments/assets/9cd87669-bdee-477e-98fc-f42bbc1fbad4" />


<img width="2005" height="1244" alt="스크린샷 2025-12-05 225432" src="https://github.com/user-attachments/assets/5a596383-60be-46d5-808e-ae71dd5e5a67" />

<img width="2133" height="1121" alt="스크린샷 2025-12-05 225422" src="https://github.com/user-attachments/assets/2f78f170-cb50-4ad1-8d12-cd391e11b9c3" />


<img width="2131" height="1077" alt="스크린샷 2025-12-05 225413" src="https://github.com/user-attachments/assets/3b57a22d-495e-4ba1-bd3c-3dda8af8de51" />


<img width="2142" height="984" alt="스크린샷 2025-12-05 225355" src="https://github.com/user-attachments/assets/8e350324-099f-420c-9bb7-74c361a2919e" />


<img width="1988" height="923" alt="스크린샷 2025-12-05 225343" src="https://github.com/user-attachments/assets/3873c1ff-638d-40f0-864c-3f612422701a" />

