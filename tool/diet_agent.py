import os
import re
import json
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from dotenv import load_dotenv
from tavily import TavilyClient
from openai import OpenAI


# ----------------------------
# 경로 헬퍼
# ----------------------------

def get_project_root() -> Path:
    """프로젝트 루트 디렉토리 반환 (tool 폴더의 상위 디렉토리)"""
    return Path(__file__).parent.parent


def get_log_path(filename: str) -> str:
    """log 폴더 내 파일의 절대 경로 반환"""
    return str(get_project_root() / "log" / filename)


# ----------------------------
# 데이터 클래스
# ----------------------------

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
class DailyIntake:
    kcal: float
    carb_g: float
    protein_g: float
    fat_g: float


@dataclass
class MacroDiff:
    remaining_kcal: float
    remaining_carb_g: float
    remaining_protein_g: float
    remaining_fat_g: float


# ----------------------------
# 파일 로딩
# ----------------------------

def load_user_profile(path: str = None) -> UserProfile:
    if path is None:
        path = get_log_path("private.json")
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)

    return UserProfile(
        age=data["age"],
        sex=data["sex"],
        height_cm=data["height_cm"],
        weight_kg=data["weight_kg"],
        activity_level=data["activity_level"],
        goal=data["goal"],
        exercise_level=data["exercise_level"],
        body_fat=data.get("body_fat"),
        diet_preference=data.get("diet_preference"),
        health_condition=data.get("health_condition"),
    )


def load_macro_targets(path: str = None) -> MacroTargets:
    if path is None:
        path = get_log_path("target_macros.json")
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)

    return MacroTargets(
        target_kcal=data["target_kcal"],
        protein_g=data["protein_g"],
        fat_g=data["fat_g"],
        carb_g=data["carb_g"],
        protein_ratio=data["protein_ratio"],
        fat_ratio=data["fat_ratio"],
        carb_ratio=data["carb_ratio"],
    )


# ----------------------------
# nutrition.txt 파싱
# ----------------------------

CAL_PATTERN = re.compile(r"칼로리\s*:\s*([\d\.]+)")
CARB_PATTERN = re.compile(r"탄수화물\s*:\s*([\d\.]+)")
PROTEIN_PATTERN = re.compile(r"단백질\s*:\s*([\d\.]+)")
FAT_PATTERN = re.compile(r"지방\s*:\s*([\d\.]+)")
DATE_PATTERN = re.compile(r"\[(\d{4}-\d{2}-\d{2})\s+[\d:]+\]")


def parse_nutrition_log(path: str = None,
                        date: Optional[str] = None) -> DailyIntake:
    if path is None:
        path = get_log_path("nutrition.txt")
    """
    nutrition.txt에서 특정 날짜(YYYY-MM-DD)의 총 섭취량을 합산.
    date=None이면 전체 합산.
    """
    p = Path(path)
    if not p.exists():
        # 기록이 없으면 0으로 반환
        return DailyIntake(kcal=0.0, carb_g=0.0, protein_g=0.0, fat_g=0.0)

    with p.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    total_kcal = 0.0
    total_carb = 0.0
    total_protein = 0.0
    total_fat = 0.0

    current_date: Optional[str] = None
    include_block = True  # date 필터가 없으면 기본 True

    for line in lines:
        line = line.strip()

        # 날짜 줄인지 검사
        m_date = DATE_PATTERN.search(line)
        if m_date:
            current_date = m_date.group(1)
            if date is None:
                include_block = True
            else:
                include_block = (current_date == date)
            continue

        if not include_block:
            continue

        # 각 영양소 파싱
        m_cal = CAL_PATTERN.search(line)
        if m_cal:
            total_kcal += float(m_cal.group(1))
            continue

        m_carb = CARB_PATTERN.search(line)
        if m_carb:
            total_carb += float(m_carb.group(1))
            continue

        m_pro = PROTEIN_PATTERN.search(line)
        if m_pro:
            total_protein += float(m_pro.group(1))
            continue

        m_fat = FAT_PATTERN.search(line)
        if m_fat:
            total_fat += float(m_fat.group(1))
            continue

    return DailyIntake(
        kcal=total_kcal,
        carb_g=total_carb,
        protein_g=total_protein,
        fat_g=total_fat,
    )


# ----------------------------
# 남은 섭취량 계산
# ----------------------------

def calc_macro_diff(target: MacroTargets, intake: DailyIntake) -> MacroDiff:
    return MacroDiff(
        remaining_kcal=target.target_kcal - intake.kcal,
        remaining_carb_g=target.carb_g - intake.carb_g,
        remaining_protein_g=target.protein_g - intake.protein_g,
        remaining_fat_g=target.fat_g - intake.fat_g,
    )


# ----------------------------
# Tavily + OpenAI로 추천 식단 생성
# ----------------------------

def build_search_query(profile: UserProfile, diff: MacroDiff) -> str:
    """
    Tavily에 날릴 검색 쿼리 생성.
    """
    # 단백질/칼로리 위주로 맞추는 방향으로 검색어 구성 (한식 위주)
    direction = []
    if diff.remaining_protein_g > 20:
        direction.append("고단백")
    if diff.remaining_fat_g < 0:
        direction.append("저지방")
    if diff.remaining_kcal < 0:
        direction.append("저칼로리")
    elif diff.remaining_kcal > 300:
        direction.append("고칼로리 보충")

    dir_str = " ".join(direction) if direction else "균형 잡힌"
    cuisine = "한식" if (profile.diet_preference or "").lower().startswith("korean") else "일반"

    return f"{cuisine} {dir_str} 식단 예시, 탄수화물·단백질·지방 함량 정보 포함"


def recommend_meal_with_tavily(
    profile: UserProfile,
    targets: MacroTargets,
    intake: DailyIntake,
    diff: MacroDiff,
    client: TavilyClient,
    llm: OpenAI,
) -> str:
    """
    Tavily 검색 결과 + OpenAI LLM으로 맞춤 식단 추천 텍스트 생성.
    """
    query = build_search_query(profile, diff)

    # Tavily 검색
    search_result = client.search(
        query=query,
        search_depth="basic",
        max_results=5,
        include_raw_content=True,
    )

    # 검색 결과 텍스트 정리
    web_context_parts = []
    for i, r in enumerate(search_result.get("results", []), start=1):
        title = r.get("title", "")
        url = r.get("url", "")
        content = r.get("content", "")
        web_context_parts.append(
            f"[{i}] {title}\nURL: {url}\n내용 요약: {content}\n"
        )
    web_context = "\n\n".join(web_context_parts)

    # LLM 프롬프트 구성 (한국어)
    user_status = (
        f"사용자 정보:\n"
        f"- 나이: {profile.age}세, 성별: {profile.sex}\n"
        f"- 키: {profile.height_cm} cm, 체중: {profile.weight_kg} kg\n"
        f"- 목표: {profile.goal} (목표 칼로리 {targets.target_kcal} kcal)\n"
        f"- 오늘까지 섭취량: 칼로리 {intake.kcal:.1f} kcal, "
        f"탄수화물 {intake.carb_g:.1f} g, 단백질 {intake.protein_g:.1f} g, 지방 {intake.fat_g:.1f} g\n"
        f"- 남은 목표: 칼로리 {diff.remaining_kcal:.1f} kcal, "
        f"탄수화물 {diff.remaining_carb_g:.1f} g, 단백질 {diff.remaining_protein_g:.1f} g, "
        f"지방 {diff.remaining_fat_g:.1f} g\n"
        f"- 식단 선호: {profile.diet_preference}\n"
    )

    instructions = (
        "다음은 웹 검색 결과입니다. 이 정보들을 참고해서, "
        "사용자가 남은 칼로리/탄단지 목표를 최대한 맞출 수 있는 맞춤 식단(1~3끼 정도)을 제안해 주세요.\n"
        "조건:\n"
        "1. 가능한 한 한식 위주로 추천하고, 각 음식의 대략적인 칼로리와 탄수화물/단백질/지방 방향성을 설명해 주세요.\n"
        "2. 아예 새로운 정보를 지어내지 말고, 웹 검색 결과에서 합리적으로 추론 가능한 범위에서만 설명하세요.\n"
        "3. 최종적으로 각 끼니별로 음식 조합과, 그 끼니가 남은 목표를 어떻게 채워주는지 간단히 설명해 주세요.\n"
        "4. 너무 디테일한 g 단위까지 정확할 필요는 없지만, 단백질 보충이 중요한지, 탄수 조절이 필요한지 등을 명확히 말해 주세요.\n"
    )

    messages = [
        {
            "role": "system",
            "content": (
                "당신은 한국어로 답하는 영양사 AI입니다. "
                "웹 검색 결과를 활용하여 과학적 근거가 있는 식단만 추천해야 합니다."
            ),
        },
        {
            "role": "user",
            "content": user_status + "\n\n" + instructions + "\n\n[웹 검색 결과]\n" + web_context,
        },
    ]

    completion = llm.chat.completions.create(
        model="gpt-4.1-mini",
        messages=messages,
        temperature=0.4,
    )

    return completion.choices[0].message.content


# ----------------------------
# 메인: 에이전트 실행
# ----------------------------

def run_nutrition_agent(
    date: Optional[str] = None,
    nutrition_path: str = None,
    profile_path: str = None,
    targets_path: str = None,
) -> str:
    if nutrition_path is None:
        nutrition_path = get_log_path("nutrition.txt")
    if profile_path is None:
        profile_path = get_log_path("private.json")
    if targets_path is None:
        targets_path = get_log_path("target_macros.json")
    """
    date: "YYYY-MM-DD" 형식. None이면 전체 기록 기준.
    return: 추천 식단 텍스트
    """
    # 1) 환경변수 로드 (.env -> OPENAI_API_KEY)
    load_dotenv()
    tavily_key = os.getenv("TAVILY_API_KEY")
    if not tavily_key:
        raise RuntimeError("TAVILY_API_KEY 환경변수가 설정되어 있지 않습니다.")

    # OpenAI 클라이언트 (OPENAI_API_KEY는 .env에서 로드)
    llm = OpenAI()

    tavily_client = TavilyClient(api_key=tavily_key)

    # 2) 파일 로드
    profile = load_user_profile(profile_path)
    targets = load_macro_targets(targets_path)

    # 3) 오늘(또는 지정 날짜) 섭취량 계산
    if date is None:
        today_str = datetime.now().strftime("%Y-%m-%d")
        date = today_str

    intake = parse_nutrition_log(nutrition_path, date=date)

    # 4) 남은 목표 계산
    diff = calc_macro_diff(targets, intake)

    # 5) Tavily + OpenAI로 추천 식단 생성
    recommendation = recommend_meal_with_tavily(
        profile=profile,
        targets=targets,
        intake=intake,
        diff=diff,
        client=tavily_client,
        llm=llm,
    )

    return recommendation


if __name__ == "__main__":
    # 기본은 오늘 날짜 기준으로 실행
    text = run_nutrition_agent()
    print(text)
