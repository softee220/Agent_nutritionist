2025.12.04 Hateslop Hackerthon 1위 출품작 (3팀) 


<img width="631" height="517" alt="image" src="https://github.com/user-attachments/assets/7b817aee-8bbf-4d9f-8959-f7e0194f4b7f" />




<img width="1004" height="617" alt="image" src="https://github.com/user-attachments/assets/9cd87669-bdee-477e-98fc-f42bbc1fbad4" />


<img width="2005" height="1244" alt="스크린샷 2025-12-05 225432" src="https://github.com/user-attachments/assets/5a596383-60be-46d5-808e-ae71dd5e5a67" />

<img width="2133" height="1121" alt="스크린샷 2025-12-05 225422" src="https://github.com/user-attachments/assets/2f78f170-cb50-4ad1-8d12-cd391e11b9c3" />


<img width="2131" height="1077" alt="스크린샷 2025-12-05 225413" src="https://github.com/user-attachments/assets/3b57a22d-495e-4ba1-bd3c-3dda8af8de51" />


<img width="2142" height="984" alt="스크린샷 2025-12-05 225355" src="https://github.com/user-attachments/assets/8e350324-099f-420c-9bb7-74c361a2919e" />


<img width="1988" height="923" alt="스크린샷 2025-12-05 225343" src="https://github.com/user-attachments/assets/3873c1ff-638d-40f0-864c-3f612422701a" />



# 🥗 AI Nutritionist Agent System  
**LLM 기반 자동 영양 분석·식단 추천·리포트 생성 에이전트**

사용자의 식단 기록을 자동으로 분석하고, 영양소 계산·개인 맞춤 식단 추천·일일/주간 코칭 리포트를 생성하는 **모듈형 AI 영양 관리 시스템**입니다.  
각 기능은 독립된 Tool 모듈로 구성되며, 메인 에이전트는 **REAct 구조**로 필요한 기능을 자동 호출합니다.

---

## 🚀 주요 기능

### 1️⃣ BMR & 목표 섭취량 계산  
**파일:** `tool/bmrcal.py`

- 사용자 정보(나이, 성별, 체중, 키, 활동량)를 기반으로 BMR 계산  
- 감량/유지/증량 목표에 맞는 **목표 칼로리 + 탄·단·지 비율 자동 산출**  
- 결과는 `log/target_macros.json`에 저장되어 모든 기능과 공유됨  

---

### 2️⃣ 자연어 기반 식단 영양소 분석  
**파일:** `tool/calnnutri.py`

- “점심에 제육덮밥 먹었어” → 자동 영양 분석  
- FatSecret API로 칼로리·탄수화물·단백질·지방·나트륨 등 상세 영양소 조회  
- 결과는 `log/nutrition.txt`에 시간순으로 누적 저장  
- LLM이 이해 가능한 기록 구조로 자동 관리됨  

---

### 3️⃣ 기록 기반 개인 맞춤 식단 추천  
**파일:** `tool/diet_agent.py`

- nutrition 기록을 기반으로 **부족/과다 영양소 자동 분석**  
- Tavily API를 이용해 현실적인 음식 후보를 검색  
- “단백질 보충을 위해 이런 메뉴를 추천합니다”와 같은 자연스러운 문장으로 결과 제공  
- 감량/균형/근육증가 목표에 최적화된 추천 시스템  

---

### 4️⃣ 일일/주간 리포트 자동 생성  
**파일:** `tool/reporter.py`

LLM이 nutrition 기록과 목표 섭취량을 기반으로 **정성적 코칭 리포트(JSON)**를 생성합니다.

#### 📌 일일 리포트 (`log/daily.json`)
```json
{
  "평가": "...",
  "문제": "...",
  "차후전략": "..."
}

####📌 주간 리포트 (log/weekly.json)
```json
{
  "평가": "...",
  "긍정": "...",
  "문제": "...",
  "차후전략": "..."
}


코치처럼 피드백을 제공하고

개선 전략을 bullet 형태로 제시

JSON 포맷이므로 다른 시스템과 연동하기 쉬움

###5️⃣ REAct 기반 메인 에이전트 통합

**파일:** main_react.py

사용자의 자연어 입력을 해석해 적절한 Tool을 자동 호출하는 에이전트 구조

예시 동작:

“오늘 먹은 것 분석해줘” → calnnutri

“단백질 부족한데 뭐 먹을까?” → diet_agent

“이번 주 리포트 만들어줘” → reporter.weekly

모듈형 아키텍처로 기능 확장성이 매우 높음.
```

---

## 📁 프로젝트 구조
project_root/
  tool/
    bmrcal.py          # BMR 및 목표 칼로리 계산
    calnnutri.py       # 자연어 식단 → 영양 분석(FatSecret)
    diet_agent.py      # Tavily 기반 식단 추천
    reporter.py        # 일일/주간 리포트(JSON) 생성

  log/
    nutrition.txt       # 누적 식단 기록
    private.json        # 사용자 정보
    target_macros.json  # 목표 섭취량
    daily.json          # 일일 리포트
    weekly.json         # 주간 리포트

  main.py               # REAct 기반 통합 에이전트
  README.md             # 프로젝트 설명 문서




---

## 🧪 사용 흐름 (Workflow)

1. **사용자 프로필 입력**  
   → `log/private.json`

2. **목표 섭취량 계산**  
   → `bmrcal.py` 실행 → `target_macros.json` 생성

3. **식사 입력 시**  
   → `calnnutri.py`가 자연어를 분석해 `nutrition.txt`에 누적

4. 필요할 때:
   - 식단 추천 → `diet_agent.py`
   - 일일/주간 리포트 → `reporter.py`

5. `main.py`가 전체 작업을 자동 조정하여 대화형 시스템 구성

---

## 💡 핵심 가치

- 자연어 기반 **완전 자동 영양 관리**
- 외부 API(FatSecret/Tavily)와 LLM 결합
- 모든 결과를 JSON으로 저장 → 데이터 활용성 극대화
- 정량(영양소) + 정성(코칭 리포트) 통합 분석
- 모듈형 구조로 기능 확장 용이

---

## 🛠 설치 및 실행

### 1. 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. 메인 에이전트
```bash
python main_react.py
```

### 3. 프로그램 실행(웹 UI)
```bash
python app.py
```


.env : openai API, Fatsecret API
환경변수 : Tavily API
---

## 🧪 리포트만 개별 테스트하고 싶다면:

### 📌 일일 리포트 생성
```bash
python tool/reporter.py daily
```

### 📌 주간 리포트 생성
```bash
python tool/reporter.py weekly
```

---
