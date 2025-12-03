import os
import json
from datetime import datetime, timedelta
from typing import List, Dict

from dotenv import load_dotenv
from openai import OpenAI

# ---------- 환경 설정 ----------
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY가 .env에 설정되어 있어야 합니다.")

client = OpenAI(api_key=OPENAI_API_KEY)

LOG_DIR = "./log"
LOG_PATH = os.path.join(LOG_DIR, "log.txt")
META_PATH = os.path.join(LOG_DIR, "metadata.json")  # 최초 실행 시간 저장용

# 하루 권장치 (예시값 – 나중에 유저별 커스터마이즈 가능)
DAILY_TARGET = {
    "calories": 2000,    # kcal
    "carbohydrate": 260, # g
    "protein": 75,       # g
    "fat": 55,           # g
}

MEAL_KR_MAP = {
    "breakfast": "아침",
    "lunch": "점심",
    "dinner": "저녁",
}


# ============================================================
# 1. 로그 유틸
# ============================================================
def _ensure_log_dir():
    os.makedirs(LOG_DIR, exist_ok=True)


def append_meal_log(meal_type: str, total_nutrients: Dict[str, float]):
    """
    Parser/Nutrition Agent에서 한 끼 계산이 끝날 때마다 호출.
    log.txt 맨 뒤에 JSON 한 줄 추가.
    total_nutrients 예시:
    {
        "calories": 500,
        "carbohydrate": 60,
        "protein": 20,
        "fat": 15,
        "sugar": 5,
        "sodium": 800
    }
    """
    _ensure_log_dir()
    now = datetime.now()
    log_item = {
        "timestamp": now.isoformat(timespec="seconds"),
        "date": now.date().isoformat(),
        "meal_type": meal_type,  # "breakfast", "lunch", "dinner" 등
        "total": total_nutrients
    }

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_item, ensure_ascii=False) + "\n")

    _ensure_first_run_metadata(now)


def _ensure_first_run_metadata(now: datetime):
    """metadata.json에 최초 실행 시각이 비어 있으면 기록"""
    need_write = False
    meta = {"first_run": now.isoformat(timespec="seconds")}

    if not os.path.exists(META_PATH) or os.path.getsize(META_PATH) == 0:
        need_write = True
    else:
        try:
            with open(META_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not data.get("first_run"):
                need_write = True
        except Exception:
            need_write = True

    if need_write:
        with open(META_PATH, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)


def load_all_logs() -> List[Dict]:
    if not os.path.exists(LOG_PATH):
        return []

    logs = []
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                logs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return logs


# ============================================================
# 2. 날짜별 요약 (숫자 집계)
# ============================================================
def summarize_day(date_str: str, logs: List[Dict]) -> Dict:
    """
    해당 날짜(date_str)에 대한 총합 계산.
    logs 중에서 date가 date_str인 것만 사용.
    """
    day_logs = [l for l in logs if l["date"] == date_str]

    meal_types = {l["meal_type"] for l in day_logs}
    all_meals_done = all(m in meal_types for m in ["breakfast", "lunch", "dinner"])

    total = {
        "calories": 0.0,
        "carbohydrate": 0.0,
        "protein": 0.0,
        "fat": 0.0,
        "sugar": 0.0,
        "sodium": 0.0,
    }

    for l in day_logs:
        t = l["total"]
        for k in total.keys():
            total[k] += float(t.get(k, 0.0))

    return {
        "date": date_str,
        "all_meals_done": all_meals_done,
        "meal_types": sorted(list(meal_types)),
        "total": total,
    }


# ============================================================
# 3. LLM 기반 Daily Report 생성
# ============================================================
def build_daily_coach_message_llm(summary: Dict, skipped_meals: List[str] | None = None) -> str:
    """
    하루 요약(summary)을 LLM에게 넘겨서
    한국어 코칭 멘트를 생성.
    """
    skipped_meals = skipped_meals or []
    skipped_text = ", ".join(skipped_meals) if skipped_meals else "없음"

    date = summary["date"]
    t = summary["total"]
    meals = ", ".join(summary["meal_types"]) if summary["meal_types"] else "없음"

    user_data = {
        "date": date,
        "meal_types": summary["meal_types"],
        "total": t,
        "daily_target": DAILY_TARGET,
    }

    prompt = f"""
당신은 건강한 식습관을 도와주는 한국어 식단 코치입니다.
극단적인 다이어트, 단식, 약물·보충제 남용 등은 절대 추천하지 말고,
현실적이고 작게 실천할 수 있는 행동 중심의 조언만 해주세요.

<하루 섭취 데이터>
- 날짜: {date}
- 기록된 식사 종류: {meals}
- 총 열량: {t['calories']:.1f} kcal
- 탄수화물: {t['carbohydrate']:.1f} g
- 단백질: {t['protein']:.1f} g
- 지방: {t['fat']:.1f} g
- 당류: {t['sugar']:.1f} g
- 나트륨: {t['sodium']:.0f} mg

<하루 권장 기준(참고용)>
- 권장 열량: {DAILY_TARGET['calories']} kcal
- 권장 탄수화물: {DAILY_TARGET['carbohydrate']} g
- 권장 단백질: {DAILY_TARGET['protein']} g
- 권장 지방: {DAILY_TARGET['fat']} g

<건너뛴 끼니>
- {skipped_text}

위 숫자 정보를 참고해, 아래 형식의 짧은 한국어 리포트를 작성하세요.

형식:
[일일 리포트] YYYY-MM-DD
1) 오늘 식사 패턴 한 줄 요약 (과식/부족/균형 등)
2) 열량과 탄단지, 당류, 나트륨에 대한 피드백 (너무 공격적이지 않게, 위로 + 현실적인 관찰)
3) 내일 실천해볼 수 있는 구체적인 행동 2~3가지 (예: "점심에 국물은 절반만 먹기", "간식은 과자 대신 요거트로 바꾸기")

조건:
- 존댓말을 사용하세요.
- 최대 8줄 이내로 간결하게 작성하세요.
- 건강 상태나 질병을 단정 짓지 마세요.
- 건너뛴 끼니가 있다면 왜 규칙적인 식사가 중요한지 1~2줄로 언급하고, 다음 끼니에 바로 적용할 수 있는 행동 팁을 포함하세요.
"""

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system",
             "content": "너는 사용자의 식습관을 부드럽게 코칭해주는 한국어 영양 코치야."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )
    return completion.choices[0].message.content.strip()


def generate_skipped_meal_advice(skipped_meals: List[str]) -> str:
    """
    건너뛴 끼니에 대한 조언 생성 (LLM 기반)
    skipped_meals: 건너뛴 끼니 한국어 이름 리스트 (예: ["아침", "점심"])
    """
    skipped_str = ", ".join(skipped_meals)

    prompt = f"""
당신은 건강한 식습관을 도와주는 한국어 식단 코치입니다.
사용자가 오늘 {skipped_str} 식사를 건너뛰었습니다.

건너뛴 끼니에 대해 부드럽고 현실적인 조언을 해주세요.

조건:
- 존댓말을 사용하세요.
- 극단적인 다이어트나 단식을 권장하지 마세요.
- 건너뛴 끼니가 건강에 미치는 영향에 대해 간단히 설명하되, 공격적이지 않게 작성하세요.
- 다음 끼니나 내일을 위한 실용적인 조언 2~3가지를 포함하세요.
- 죄책감을 주기보다는 이해하고 격려하는 톤으로 작성하세요.
- 최대 6줄 이내로 간결하게 작성하세요.

예시 형식:
"건너뛴 끼니에 대한 간단한 설명과 영향"
"다음 끼니나 내일을 위한 실용적인 조언 2~3가지"
"""

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system",
             "content": "너는 사용자의 식습관을 부드럽게 코칭해주는 한국어 영양 코치야."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )
    return completion.choices[0].message.content.strip()


def generate_daily_report_for(date_str: str, skipped_meals: List[str] | None = None) -> str | None:
    """
    특정 날짜에 대해 일일 리포트를 생성.
    건너뛴 끼니가 있으면 리포트 안에 조언을 포함.
    """
    logs = load_all_logs()
    summary = summarize_day(date_str, logs)
    skipped_meals = list(skipped_meals) if skipped_meals else []

    existing_meals = set(summary["meal_types"])
    missing_meals = [MEAL_KR_MAP[m] for m in MEAL_KR_MAP.keys() if m not in existing_meals]

    for meal in missing_meals:
        if meal not in skipped_meals:
            skipped_meals.append(meal)

    report = build_daily_coach_message_llm(summary, skipped_meals)

    if skipped_meals:
        advice = generate_skipped_meal_advice(skipped_meals)
        report = f"{report}\n\n[끼니 조언]\n{advice}"

    return report


# ============================================================
# 4. LLM 기반 Weekly Report
# ============================================================
def _load_first_run_time() -> datetime | None:
    if not os.path.exists(META_PATH):
        return None
    with open(META_PATH, "r", encoding="utf-8") as f:
        meta = json.load(f)
    try:
        return datetime.fromisoformat(meta["first_run"])
    except Exception:
        return None


def generate_weekly_report_if_due() -> str | None:
    """
    최초 실행 시각 기준 7일이 지났으면:
      -> 최초 실행 ~ 7일 구간의 로그로 주간 리포트 생성 (LLM)
    아니라면 None.
    """
    first_run = _load_first_run_time()
    if first_run is None:
        return None

    now = datetime.now()
    if now < first_run + timedelta(days=7):
        # 아직 1주일 안 지남
        return None

    start_date = first_run.date()
    end_date = (first_run + timedelta(days=7)).date()  # 포함 범위의 마지막 날짜
    logs = load_all_logs()

    current_date = start_date
    day_summaries = []
    while current_date <= end_date:
        ds = current_date.isoformat()
        summary = summarize_day(ds, logs)
        if summary["total"]["calories"] > 0:
            day_summaries.append(summary)
        current_date += timedelta(days=1)

    if not day_summaries:
        return None

    # LLM에 넘길 요약 숫자 만들기
    weekly_payload = []
    for s in day_summaries:
        weekly_payload.append({
            "date": s["date"],
            "total": s["total"],
            "meal_types": s["meal_types"],
        })

    payload_str = json.dumps(weekly_payload, ensure_ascii=False, indent=2)

    prompt = f"""
당신은 건강한 식습관을 도와주는 한국어 식단 코치입니다.
아래는 한 사용자의 1주일 동안 섭취 데이터 요약입니다.

<1주일 데이터(JSON)>
{payload_str}

각 day.total 안에는 해당 날짜의 총 섭취량이 들어 있습니다.
칼로리/탄수화물/단백질/지방/당류/나트륨 값을 보고
1주일 패턴 전체를 요약하고 싶습니다.

형식:
[주간 리포트] YYYY-MM-DD ~ YYYY-MM-DD
1) 이번 주 전체 식사 패턴 한 줄 요약 (예: "평균적으로 칼로리가 높고, 나트륨이 많은 한 주였어요.")
2) 칼로리, 탄단지, 당/나트륨 관점에서 나타나는 경향 3가지 이내로 bullet 형식 정리
3) 다음 주에 실천해보면 좋은 구체적인 행동 3가지 (작고 현실적인 변화 – 예: "라면은 주 1회로 줄이기", "하루 한 끼는 채소가 눈에 보이게 추가되도록 구성하기")

조건:
- 존댓말을 사용하세요.
- 질병이나 비만, 영양결핍 등을 단정적으로 진단하지 마세요.
- 사용자에게 죄책감을 주기보다는, '지금 패턴'을 이해하고 '다음 주에 쓸 수 있는 전략'에 집중하세요.
"""

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system",
             "content": "너는 사용자의 1주일 식습관을 다정하게 리뷰해주는 한국어 영양 코치야."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )
    return completion.choices[0].message.content.strip()
