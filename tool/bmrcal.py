import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal, Dict, Any


# -----------------------------
# 0. 경로 헬퍼
# -----------------------------

def get_project_root() -> Path:
    """프로젝트 루트 디렉토리 반환 (tool 폴더의 상위 디렉토리)"""
    return Path(__file__).parent.parent


def get_log_path(filename: str) -> str:
    """log 폴더 내 파일의 절대 경로 반환"""
    return str(get_project_root() / "log" / filename)


# -----------------------------
# 1. 데이터 구조 정의
# -----------------------------

Sex = Literal["male", "female"]
ActivityLevel = Literal["sedentary", "light", "moderate", "active", "very_active"]
Goal = Literal["weight_loss", "maintenance", "weight_gain"]
ExerciseLevel = Literal["low", "mid", "high"]


@dataclass
class UserProfile:
    age: int
    sex: Sex
    height_cm: float
    weight_kg: float
    activity_level: ActivityLevel
    goal: Goal
    exercise_level: ExerciseLevel
    body_fat: float | None = None
    diet_preference: str | None = None
    health_condition: str | None = None


@dataclass
class MacroTargets:
    target_kcal: int
    protein_g: int
    fat_g: int
    carb_g: int
    protein_ratio: float
    fat_ratio: float
    carb_ratio: float


# -----------------------------
# 2. 설정 값 (계수/규칙 테이블)
# -----------------------------

ACTIVITY_FACTORS: Dict[ActivityLevel, float] = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}

PROTEIN_PER_KG: Dict[ExerciseLevel, float] = {
    "low": 1.2,
    "mid": 1.6,
    "high": 2.0,
}

FAT_PER_KG_DEFAULT: float = 0.8


# -----------------------------
# 3. 파일 로드/저장 함수
# -----------------------------

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


def save_macro_targets(path: str, macros: MacroTargets):
    """
    MacroTargets 객체를 JSON으로 저장.
    ./log/target_macros.json 에 저장됨.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)  # ./log 폴더 없으면 생성
    with p.open("w", encoding="utf-8") as f:
        json.dump(asdict(macros), f, indent=4, ensure_ascii=False)
    print(f"[saved] 목표 탄단지 데이터 → {path}")


# -----------------------------
# 4. 계산 함수
# -----------------------------

def calculate_bmr(profile: UserProfile) -> float:
    if profile.sex == "male":
        return 10 * profile.weight_kg + 6.25 * profile.height_cm - 5 * profile.age + 5
    else:
        return 10 * profile.weight_kg + 6.25 * profile.height_cm - 5 * profile.age - 161


def calculate_tdee(profile: UserProfile, bmr: float) -> float:
    return bmr * ACTIVITY_FACTORS[profile.activity_level]


def adjust_for_goal(profile: UserProfile, tdee: float) -> float:
    if profile.goal == "weight_loss":
        target = tdee - 500
    elif profile.goal == "weight_gain":
        target = tdee + 300
    else:
        target = tdee

    # 최소 안정 섭취 칼로리 제한
    min_kcal = 1200 if profile.sex == "male" else 1000
    if target < min_kcal:
        target = float(min_kcal)

    return target


def calculate_macros(profile: UserProfile, target_kcal: float) -> MacroTargets:
    protein_per_kg = PROTEIN_PER_KG[profile.exercise_level]
    protein_g = profile.weight_kg * protein_per_kg
    protein_kcal = protein_g * 4

    fat_g = profile.weight_kg * FAT_PER_KG_DEFAULT
    fat_kcal = fat_g * 9

    remaining_kcal = target_kcal - (protein_kcal + fat_kcal)
    if remaining_kcal < 0:
        # 지방을 먼저 깎아서 조정
        deficit = -remaining_kcal
        fat_kcal = max(fat_kcal - deficit, 0)
        fat_g = fat_kcal / 9
        remaining_kcal = target_kcal - (protein_kcal + fat_kcal)

    carb_kcal = remaining_kcal
    carb_g = carb_kcal / 4

    # 비율 계산
    p_ratio = protein_kcal / target_kcal * 100
    f_ratio = fat_kcal / target_kcal * 100
    c_ratio = carb_kcal / target_kcal * 100

    return MacroTargets(
        target_kcal=int(round(target_kcal)),
        protein_g=int(round(protein_g)),
        fat_g=int(round(fat_g)),
        carb_g=int(round(carb_g)),
        protein_ratio=round(p_ratio, 1),
        fat_ratio=round(f_ratio, 1),
        carb_ratio=round(c_ratio, 1),
    )


# -----------------------------
# 5. 메인 실행부
# -----------------------------

def main():
    profile = load_user_profile()

    bmr = calculate_bmr(profile)
    tdee = calculate_tdee(profile, bmr)
    target_kcal = adjust_for_goal(profile, tdee)

    macros = calculate_macros(profile, target_kcal)

    # 결과 출력
    print("=== 목표 섭취 칼로리 / 탄단지 계산 결과 ===")
    print(macros)

    # 🔥 저장 기능 추가된 부분
    save_macro_targets(get_log_path("target_macros.json"), macros)


if __name__ == "__main__":
    main()
