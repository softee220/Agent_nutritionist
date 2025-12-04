import os
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

from dotenv import load_dotenv
from openai import OpenAI


# ============================================================
# 0. 경로 헬퍼 & 환경 설정
# ============================================================

def get_project_root() -> Path:
    """프로젝트 루트 디렉토리 반환 (이 파일의 상위 디렉토리)"""
    return Path(__file__).parent.parent


def get_log_path(filename: str) -> str:
    """log 폴더 내 파일의 절대 경로 반환"""
    return str(get_project_root() / "log" / filename)


def save_json_to_log(data: Any, filename: str) -> str:
    """
    data(dict 등)를 프로젝트 루트/log/filename 으로 저장하고,
    저장 경로를 문자열로 리턴.
    """
    path = get_project_root() / "log" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


load_dotenv()
# OPENAI_API_KEY는 .env에 있다고 가정 (os.environ에서 자동으로 읽음)
client = OpenAI()  # 환경변수 기반


# ============================================================
# 1. 데이터 클래스 및 로딩
# ============================================================

@dataclass
class UserProfile:
    age: int
    sex: str
    height_cm: float
    weight_kg: float
    activity_level: str
    goal: str
    exercise_level: str
    body_fat: Optional[float] = None
    diet_preference: Optional[str] = None
    health_condition: Optional[str] = None


@dataclass
class MacroTargets:
    target_kcal: int
    protein_g: int
    fat_g: int
    carb_g: int
    protein_ratio: float
    fat_ratio: float
    carb_ratio: float


@dataclass
class DailyTotals:
    date: str
    calories: float
    carbohydrate: float
    protein: float
    fat: float
    sugar: float
    sodium: float


def load_user_profile(path: str) -> UserProfile:
    """
    ./log/private.json 형식:
    {
      "age": 27,
      "sex": "male",
      "height_cm": 178,
      "weight_kg": 70,
      "activity_level": "moderate",
      "goal": "weight_loss",
      "exercise_level": "mid",
      "body_fat": 18,
      "diet_preference": "korean",
      "health_condition": null
    }
    """
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))

    return UserProfile(
        age=data["age"],
        sex=data["sex"],
        height_cm=data["height_cm"],
        weight_kg=data["weight_kg"],
        activity_level=data["activity_level"],
        goal=data["goal"],
        exercise_level=data["exercise_level"],
        body_fat=data.get("body_fat") or data.get("...at"),  # 업로드된 예시 호환
        diet_preference=data.get("diet_preference"),
        health_condition=data.get("health_condition"),
    )


def load_macro_targets(path: str) -> MacroTargets:
    """
    ./log/target_macros.json 형식:
    {
        "target_kcal": 2108,
        "protein_g": 112,
        "fat_g": 56,
        "carb_g": 289,
        "protein_ratio": 21.3,
        "fat_ratio": 23.9,
        "carb_ratio": 54.8
    }
    """
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))

    return MacroTargets(
        target_kcal=data["target_kcal"],
        protein_g=data["protein_g"],
        fat_g=data["fat_g"],
        carb_g=data["carb_g"],
        protein_ratio=data["protein_ratio"],
        fat_ratio=data["fat_ratio"],
        carb_ratio=data["carb_ratio"],
    )


# ============================================================
# 2. nutrition.txt 파싱 및 일/주 합계 계산
# ============================================================

# 예시 형식:
# [2025-12-03 04:08:28]
#    ● 칼로리 : 604.1 kcal
#    ● 탄수화물: 59.2 g
#    ● 단백질  : 39.4 g
#    ● 지방    : 21.3 g
#    ● 당류    : 0.2 g
#    ● 나트륨  : 1,388 mg

DATE_LINE_RE = re.compile(r"\[(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}:\d{2}\]")
CAL_RE = re.compile(r"칼로리\s*:\s*([\d\.]+)")
CARB_RE = re.compile(r"탄수화물\s*:\s*([\d\.]+)")
PROT_RE = re.compile(r"단백질\s*:\s*([\d\.]+)")
FAT_RE = re.compile(r"지방\s*:\s*([\d\.]+)")
SUGAR_RE = re.compile(r"당류\s*:\s*([\d\.]+)")
SODIUM_RE = re.compile(r"나트륨\s*:\s*([\d,\.]+)")


def _parse_float_safe(text: str) -> float:
    text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return 0.0


def parse_nutrition_file(path: str) -> Dict[str, DailyTotals]:
    """
    nutrition.txt 전체를 읽어서
    날짜별로 합산된 DailyTotals 딕셔너리를 반환.
    key: "YYYY-MM-DD"
    """
    p = Path(path)
    if not p.exists():
        return {}

    lines = p.read_text(encoding="utf-8").splitlines()

    # 날짜별 누적
    daily_acc: Dict[str, Dict[str, float]] = {}

    current_date: Optional[str] = None
    temp_block: Dict[str, float] = {}

    def flush_block(date_key: Optional[str]):
        if date_key is None or not temp_block:
            return
        acc = daily_acc.setdefault(
            date_key,
            dict(calories=0.0, carbohydrate=0.0, protein=0.0,
                 fat=0.0, sugar=0.0, sodium=0.0),
        )
        for k, v in temp_block.items():
            acc[k] += v
        temp_block.clear()

    for raw in lines:
        line = raw.strip()
        if not line:
            # 블록 경계로 처리
            flush_block(current_date)
            continue

        # 날짜 라인
        m_date = DATE_LINE_RE.search(line)
        if m_date:
            # 이전 블록 flush
            flush_block(current_date)
            current_date = m_date.group(1)
            continue

        # 영양 성분 라인들
        m = CAL_RE.search(line)
        if m:
            temp_block["calories"] = _parse_float_safe(m.group(1))
            continue
        m = CARB_RE.search(line)
        if m:
            temp_block["carbohydrate"] = _parse_float_safe(m.group(1))
            continue
        m = PROT_RE.search(line)
        if m:
            temp_block["protein"] = _parse_float_safe(m.group(1))
            continue
        m = FAT_RE.search(line)
        if m:
            temp_block["fat"] = _parse_float_safe(m.group(1))
            continue
        m = SUGAR_RE.search(line)
        if m:
            temp_block["sugar"] = _parse_float_safe(m.group(1))
            continue
        m = SODIUM_RE.search(line)
        if m:
            temp_block["sodium"] = _parse_float_safe(m.group(1))
            continue

    # 파일 끝에서도 flush
    flush_block(current_date)

    # DailyTotals로 변환
    result: Dict[str, DailyTotals] = {}
    for date_str, acc in daily_acc.items():
        result[date_str] = DailyTotals(
            date=date_str,
            calories=acc["calories"],
            carbohydrate=acc["carbohydrate"],
            protein=acc["protein"],
            fat=acc["fat"],
            sugar=acc["sugar"],
            sodium=acc["sodium"],
        )
    return result


# ============================================================
# 3. 요약/리포트용 데이터 생성
# ============================================================

def build_daily_summary(
    date: str,
    daily_totals: DailyTotals,
    targets: MacroTargets
) -> Dict[str, Any]:
    """
    LLM 프롬프트에 넣기 좋은 형태로 요약 dict 생성
    """
    delta = {
        "calories": daily_totals.calories - targets.target_kcal,
        "carbohydrate": daily_totals.carbohydrate - targets.carb_g,
        "protein": daily_totals.protein - targets.protein_g,
        "fat": daily_totals.fat - targets.fat_g,
    }

    ratio = {
        "calories": daily_totals.calories / targets.target_kcal * 100 if targets.target_kcal else 0.0,
        "carbohydrate": daily_totals.carbohydrate / targets.carb_g * 100 if targets.carb_g else 0.0,
        "protein": daily_totals.protein / targets.protein_g * 100 if targets.protein_g else 0.0,
        "fat": daily_totals.fat / targets.fat_g * 100 if targets.fat_g else 0.0,
    }

    return {
        "date": date,
        "total": {
            "calories": round(daily_totals.calories, 1),
            "carbohydrate": round(daily_totals.carbohydrate, 1),
            "protein": round(daily_totals.protein, 1),
            "fat": round(daily_totals.fat, 1),
            "sugar": round(daily_totals.sugar, 1),
            "sodium": round(daily_totals.sodium, 1),
        },
        "target": {
            "calories": targets.target_kcal,
            "carbohydrate": targets.carb_g,
            "protein": targets.protein_g,
            "fat": targets.fat_g,
        },
        "delta": {k: round(v, 1) for k, v in delta.items()},
        "ratio": {k: round(v, 1) for k, v in ratio.items()},
    }


def build_weekly_summary(
    daily_map: Dict[str, DailyTotals],
    targets: MacroTargets,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    end_date 기준 최근 7일(없으면 nutrition에 있는 마지막 날짜 기준)
    의 통계를 모아서 LLM용 요약 데이터 생성.
    """
    if not daily_map:
        return {"days": [], "average": {}, "total": {}, "start_date": None, "end_date": None}

    # 날짜 정렬
    dates_sorted = sorted(daily_map.keys())
    if end_date is None:
        end_date = dates_sorted[-1]

    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    start_dt = end_dt - timedelta(days=6)

    selected: List[DailyTotals] = []
    for d in dates_sorted:
        dt = datetime.strptime(d, "%Y-%m-%d")
        if start_dt <= dt <= end_dt:
            selected.append(daily_map[d])

    if not selected:
        return {"days": [], "average": {}, "total": {}, "start_date": None, "end_date": end_date}

    # 총합/평균 계산
    total = {
        "calories": sum(d.calories for d in selected),
        "carbohydrate": sum(d.carbohydrate for d in selected),
        "protein": sum(d.protein for d in selected),
        "fat": sum(d.fat for d in selected),
        "sugar": sum(d.sugar for d in selected),
        "sodium": sum(d.sodium for d in selected),
    }
    n = len(selected)
    avg = {k: v / n for k, v in total.items()}

    # 목표 대비 (하루 기준)
    avg_delta = {
        "calories": avg["calories"] - targets.target_kcal,
        "carbohydrate": avg["carbohydrate"] - targets.carb_g,
        "protein": avg["protein"] - targets.protein_g,
        "fat": avg["fat"] - targets.fat_g,
    }

    start_date_str = start_dt.strftime("%Y-%m-%d")

    return {
        "start_date": start_date_str,
        "end_date": end_date,
        "num_days": n,
        "days": [
            {
                "date": d.date,
                "calories": round(d.calories, 1),
                "carbohydrate": round(d.carbohydrate, 1),
                "protein": round(d.protein, 1),
                "fat": round(d.fat, 1),
                "sugar": round(d.sugar, 1),
                "sodium": round(d.sodium, 1),
            }
            for d in selected
        ],
        "total": {k: round(v, 1) for k, v in total.items()},
        "average": {k: round(v, 1) for k, v in avg.items()},
        "average_delta_vs_target": {k: round(v, 1) for k, v in avg_delta.items()},
    }


# ============================================================
# 4. LLM 프롬프트 구성 (JSON 포맷 일일 / 주간 리포트)
# ============================================================

def build_daily_coach_json(
    profile: UserProfile,
    summary: Dict[str, Any],
) -> Dict[str, Any]:
    """
    하루 요약 리포트를 LLM에게 JSON 형식으로 요청.
    최종 출력 포맷:
    {
      "평가": "...",
      "문제": "...",
      "차후전략": "..."
    }
    """
    date = summary["date"]
    t = summary["total"]
    target = summary["target"]
    delta = summary["delta"]
    ratio = summary["ratio"]

    prompt = f"""
당신은 사용자의 일일 식단을 리뷰하는 한국어 영양 코치입니다.

[사용자 정보]
- 나이: {profile.age}세
- 성별: {profile.sex}
- 키/체중: {profile.height_cm} cm / {profile.weight_kg} kg
- 목표: {profile.goal} (예: 체중감량, 유지, 증량 등)
- 활동 수준: {profile.activity_level}
- 운동 수준: {profile.exercise_level}
- 식단 선호: {profile.diet_preference}

[오늘 날짜] {date}

[하루 목표]
- 칼로리: {target['calories']} kcal
- 탄수화물: {target['carbohydrate']} g
- 단백질: {target['protein']} g
- 지방: {target['fat']} g

[오늘 실제 섭취량]
- 칼로리: {t['calories']} kcal ({ratio['calories']}% / Δ {delta['calories']} kcal)
- 탄수화물: {t['carbohydrate']} g ({ratio['carbohydrate']}% / Δ {delta['carbohydrate']} g)
- 단백질: {t['protein']} g ({ratio['protein']}% / Δ {delta['protein']} g)
- 지방: {t['fat']} g ({ratio['fat']}% / Δ {delta['fat']} g)
- 당류: {t['sugar']} g
- 나트륨: {t['sodium']} mg

[요청사항]
1. 오늘 하루 식단을 목표와 비교해서 장점과 아쉬운 점을 정리해 주세요.
2. 특히 단백질/탄수화물/지방 중 무엇이 좋았고, 무엇을 조정하면 좋을지 구체적으로 적어 주세요.
3. "내일부터 당장 실천 가능한" 간단한 행동 팁을 차후 전략에 포함해 주세요.
4. 체중감량이나 건강을 단정적으로 보장하지 말고, '경향'과 '조언' 수준에서만 이야기해 주세요.

[출력 형식]
반드시 아래와 같은 JSON 형식만 출력하세요. 한국어로 작성하되, 키 이름은 그대로 사용하세요.

{{
  "평가": "오늘 하루 식단 전반에 대한 평가를 3~5줄 정도로 작성",
  "문제": "섭취 패턴에서 아쉬운 점, 과다/부족한 영양소 등을 3~5줄 정도로 작성",
  "차후전략": "내일부터 실천 가능한 구체적인 행동 전략을 bullet 느낌으로 문장 여러 개로 작성"
}}

추가 설명 문장이나 JSON 바깥 텍스트를 절대 쓰지 마세요.
유효한 JSON만 출력하세요.
    """.strip()

    completion = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": "너는 사용자의 식습관을 다정하게 코칭해주는 한국어 영양 코치야. "
                           "반드시 사용자가 요구한 JSON 형식으로만 답변해."
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
    )
    content = completion.choices[0].message.content.strip()

    # JSON 파싱 시도
    try:
        data = json.loads(content)
        # 키 강제 보정
        result = {
            "평가": data.get("평가", "").strip(),
            "문제": data.get("문제", "").strip(),
            "차후전략": data.get("차후전략", "").strip(),
        }
    except Exception:
        # 파싱 실패 시, 전체를 "평가"에 넣고 나머지는 빈 문자열
        result = {
            "평가": content,
            "문제": "",
            "차후전략": "",
        }

    # 메타 정보도 같이 붙이고 싶다면 여기서 추가 가능 (선택):
    result_meta = {
        "date": date,
        "summary": summary,
        "report": result,
    }
    return result_meta


def build_weekly_coach_json(
    profile: UserProfile,
    weekly_summary: Dict[str, Any],
) -> Dict[str, Any]:
    """
    1주일 식습관 리포트를 LLM에게 JSON 형식으로 요청.
    최종 출력 포맷:
    {
      "평가": "...",
      "긍정": "...",
      "문제": "...",
      "차후전략": "..."
    }
    """
    if not weekly_summary["days"]:
        return {
            "start_date": weekly_summary.get("start_date"),
            "end_date": weekly_summary.get("end_date"),
            "summary": weekly_summary,
            "report": {
                "평가": "최근 1주일 간 기록된 식단 데이터가 충분하지 않아, 주간 리포트를 생성할 수 없습니다.",
                "긍정": "",
                "문제": "",
                "차후전략": "",
            },
        }

    start_date = weekly_summary["start_date"]
    end_date = weekly_summary["end_date"]
    avg = weekly_summary["average"]
    avg_delta = weekly_summary["average_delta_vs_target"]
    total = weekly_summary["total"]

    # 날짜별 간단 목록 문자열
    day_lines = []
    for d in weekly_summary["days"]:
        day_lines.append(
            f"- {d['date']}: {d['calories']} kcal, 탄수 {d['carbohydrate']} g, "
            f"단백질 {d['protein']} g, 지방 {d['fat']} g, 당류 {d['sugar']} g, 나트륨 {d['sodium']} mg"
        )
    days_text = "\n".join(day_lines)

    prompt = f"""
당신은 사용자의 1주일 식습관을 리뷰하는 한국어 영양 코치입니다.

[사용자 정보]
- 나이: {profile.age}세
- 성별: {profile.sex}
- 키/체중: {profile.height_cm} cm / {profile.weight_kg} kg
- 목표: {profile.goal}
- 활동 수준: {profile.activity_level}
- 운동 수준: {profile.exercise_level}
- 식단 선호: {profile.diet_preference}

[분석 기간]
- 시작일: {start_date}
- 종료일: {end_date}
- 기록 일수: {weekly_summary['num_days']}일

[1일 평균 섭취량]
- 칼로리: {avg['calories']} kcal (목표 대비 Δ {avg_delta['calories']} kcal)
- 탄수화물: {avg['carbohydrate']} g (목표 대비 Δ {avg_delta['carbohydrate']} g)
- 단백질: {avg['protein']} g (목표 대비 Δ {avg_delta['protein']} g)
- 지방: {avg['fat']} g (목표 대비 Δ {avg_delta['fat']} g)
- 당류: {avg['sugar']} g
- 나트륨: {avg['sodium']} mg

[1주일 총 섭취량]
- 칼로리: {total['calories']} kcal
- 탄수화물: {total['carbohydrate']} g
- 단백질: {total['protein']} g
- 지방: {total['fat']} g
- 당류: {total['sugar']} g
- 나트륨: {total['sodium']} mg

[날짜별 요약]
{days_text}

[요청사항]
1. 이번 주 전반적인 식습관의 경향(칼로리, 탄단지, 당류, 나트륨)을 정리해 주세요.
2. 좋았던 패턴(긍정적인 부분)을 정리해 주세요.
3. 개선하면 좋을 점(문제점)을 정리해 주세요.
4. 다음 주에 실천해볼 만한 구체적인 행동 전략을 제안해 주세요.
5. 체중이나 질병 상태를 단정적으로 진단하지 말고, 어디까지나 '생활 습관' 관점에서 코칭해 주세요.

[출력 형식]
반드시 아래와 같은 JSON 형식만 출력하세요. 한국어로 작성하되, 키 이름은 그대로 사용하세요.

{{
  "평가": "이번 주 전반적인 식습관 경향 요약 (3~6줄)",
  "긍정": "좋았던 패턴 3가지 정도를 문단 또는 bullet 느낌으로 정리",
  "문제": "개선이 필요한 점 3가지 정도를 정리",
  "차후전략": "다음 주에 실천할 구체적인 행동 전략을 여러 문장으로 제시"
}}

추가 설명 문장이나 JSON 바깥 텍스트를 절대 쓰지 마세요.
유효한 JSON만 출력하세요.
    """.strip()

    completion = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": "너는 사용자의 1주일 식습관을 다정하게 리뷰해주는 한국어 영양 코치야. "
                           "반드시 사용자가 요구한 JSON 형식으로만 답변해."
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
    )
    content = completion.choices[0].message.content.strip()

    # JSON 파싱 시도
    try:
        data = json.loads(content)
        report = {
            "평가": data.get("평가", "").strip(),
            "긍정": data.get("긍정", "").strip(),
            "문제": data.get("문제", "").strip(),
            "차후전략": data.get("차후전략", "").strip(),
        }
    except Exception:
        report = {
            "평가": content,
            "긍정": "",
            "문제": "",
            "차후전략": "",
        }

    result_meta = {
        "start_date": start_date,
        "end_date": end_date,
        "summary": weekly_summary,
        "report": report,
    }
    return result_meta


# ============================================================
# 5. 외부에서 쓰기 좋은 진입 함수
# ============================================================

def run_daily_coach(
    nutrition_path: str = None,
    private_path: str = None,
    target_path: str = None,
    date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    nutrition, private, target_macros를 입력받아서
    특정 날짜(기본: 가장 최근 날짜)의 일일 리포트(JSON)를 생성하고,
    프로젝트 루트의 log/daily.json에 저장한 뒤 JSON(dict)을 반환.
    """
    if nutrition_path is None:
        nutrition_path = get_log_path("nutrition.txt")
    if private_path is None:
        private_path = get_log_path("private.json")
    if target_path is None:
        target_path = get_log_path("target_macros.json")

    profile = load_user_profile(private_path)
    targets = load_macro_targets(target_path)
    daily_map = parse_nutrition_file(nutrition_path)

    if not daily_map:
        result = {
            "error": "nutrition.txt에서 유효한 식단 기록을 찾지 못했습니다.",
        }
        save_json_to_log(result, "daily.json")
        return result

    # 기본 날짜: nutrition에 있는 마지막 날짜
    dates_sorted = sorted(daily_map.keys())
    if date is None:
        date = dates_sorted[-1]
    if date not in daily_map:
        result = {
            "error": f"{date} 날짜의 기록이 nutrition.txt에 없습니다.",
        }
        save_json_to_log(result, "daily.json")
        return result

    summary = build_daily_summary(date, daily_map[date], targets)
    daily_json = build_daily_coach_json(profile, summary)
    save_json_to_log(daily_json, "daily.json")
    return daily_json


def run_weekly_coach(
    nutrition_path: str = None,
    private_path: str = None,
    target_path: str = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    nutrition, private, target_macros를 입력받아서
    end_date 기준 최근 7일 주간 리포트(JSON)를 생성하고,
    프로젝트 루트의 log/weekly.json에 저장한 뒤 JSON(dict)을 반환.
    end_date가 None이면 nutrition에 기록된 마지막 날짜 기준.
    """
    if nutrition_path is None:
        nutrition_path = get_log_path("nutrition.txt")
    if private_path is None:
        private_path = get_log_path("private.json")
    if target_path is None:
        target_path = get_log_path("target_macros.json")

    profile = load_user_profile(private_path)
    targets = load_macro_targets(target_path)
    daily_map = parse_nutrition_file(nutrition_path)

    if not daily_map:
        result = {
            "error": "nutrition.txt에서 유효한 식단 기록을 찾지 못했습니다.",
        }
        save_json_to_log(result, "weekly.json")
        return result

    dates_sorted = sorted(daily_map.keys())
    if end_date is None:
        end_date = dates_sorted[-1]

    weekly_summary = build_weekly_summary(daily_map, targets, end_date=end_date)
    weekly_json = build_weekly_coach_json(profile, weekly_summary)
    save_json_to_log(weekly_json, "weekly.json")
    return weekly_json


# ============================================================
# 6. CLI 테스트용 진입점
# ============================================================

if __name__ == "__main__":
    # 사용 예:
    #   python reporter.py daily
    #   python reporter.py weekly
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "daily"
    if mode == "daily":
        result = run_daily_coach()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif mode == "weekly":
        result = run_weekly_coach()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("사용법: python reporter.py [daily|weekly]")
