#!/usr/bin/env python3
"""
Agent Nutritionist - 통합 영양 관리 에이전트

4가지 주요 기능:
1. 프로필/목표 설정 (BMRcal)
2. 식단 기록/추가 (calnnutri)
3. 식단 추천 (diet_agent)
4. 리포트 요청 (reporter)
"""

import os
import json
from enum import Enum
from dotenv import load_dotenv
from openai import OpenAI

# 환경변수 로드
load_dotenv()

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ============================================================================
# Intent 분류 시스템
# ============================================================================

class IntentCategory(Enum):
    """사용자 의도 카테고리"""
    PROFILE_SETUP = "profile_setup"      # 프로필/목표 설정
    MEAL_RECORD = "meal_record"          # 식단 기록/추가
    DIET_RECOMMEND = "diet_recommend"    # 식단 추천
    REPORT = "report"                    # 리포트 요청
    UNKNOWN = "unknown"                  # 알 수 없음


def classify_intent(user_input: str) -> dict:
    """
    사용자 입력을 분석하여 의도를 분류합니다.

    Args:
        user_input: 사용자 입력 텍스트

    Returns:
        dict: {"category": IntentCategory, "confidence": float, "params": dict}
    """
    system_prompt = """
당신은 사용자의 의도를 분류하는 AI입니다.
사용자 입력을 분석하여 다음 4가지 카테고리 중 하나로 분류하세요:

1. profile_setup: 프로필 설정, 목표 설정, BMR/TDEE 계산, 목표 칼로리 설정
   예시: "내 목표 칼로리 설정해줘", "BMR 계산해줘", "프로필 업데이트"

2. meal_record: 식단 기록, 음식 섭취 기록
   예시: "현미밥 200g 먹었어", "닭가슴살 100g 기록해줘", "오늘 점심 먹은거 기록"

3. diet_recommend: 식단 추천, 메뉴 추천
   예시: "뭐 먹으면 좋을까?", "오늘 저녁 메뉴 추천해줘", "식단 추천해줘"

4. report: 리포트 요청, 분석 요청
   예시: "오늘 리포트 보여줘", "이번 주 분석해줘", "식단 분석"

다음 JSON 형식으로 답변하세요:
{
    "category": "카테고리 이름 (위 4가지 중 하나)",
    "confidence": 0.0-1.0 (확신도),
    "reasoning": "분류 이유 (한국어)",
    "params": {
        "report_type": "daily 또는 weekly (report 카테고리일 때만)",
        "meal_description": "음식 설명 (meal_record 카테고리일 때만)"
    }
}
"""

    user_prompt = f"사용자 입력: {user_input}"

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3
        )

        content = completion.choices[0].message.content.strip()
        # JSON 코드 블록 제거
        content = content.replace("```json", "").replace("```", "").strip()
        result = json.loads(content)

        # Enum으로 변환
        category_str = result.get("category", "unknown")
        try:
            category = IntentCategory(category_str)
        except ValueError:
            category = IntentCategory.UNKNOWN

        return {
            "category": category,
            "confidence": result.get("confidence", 0.0),
            "reasoning": result.get("reasoning", ""),
            "params": result.get("params", {})
        }

    except Exception as e:
        print(f"⚠️ 의도 분류 중 오류 발생: {e}")
        return {
            "category": IntentCategory.UNKNOWN,
            "confidence": 0.0,
            "reasoning": "오류 발생",
            "params": {}
        }


# ============================================================================
# 각 카테고리별 핸들러 함수
# ============================================================================

def handle_profile_setup(params: dict):
    """프로필/목표 설정 핸들러"""
    print("\n🎯 프로필 및 목표 설정")
    print("=" * 70)

    # 동적 import (필요할 때만 로드)
    from tool.bmrcal import main as bmr_main

    try:
        bmr_main()
        print("\n✅ 프로필 및 목표 설정이 완료되었습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")


def handle_meal_record(params: dict):
    """식단 기록 핸들러"""
    print("\n📝 식단 기록")
    print("=" * 70)

    # 동적 import
    from tool.calnnutri import record_nutrition

    # params에서 meal_description 가져오기
    meal_desc = params.get("meal_description", "")

    if not meal_desc:
        # LLM이 추출하지 못한 경우, 사용자에게 직접 입력 받기
        print("무엇을 드셨나요?")
        meal_desc = input("입력 (예: 현미밥 200g이랑 닭가슴살 100g 먹었어): ")

    try:
        record_nutrition(meal_desc)
        print("\n✅ 식단이 기록되었습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")


def handle_diet_recommend(params: dict):
    """식단 추천 핸들러"""
    print("\n🍽️  식단 추천")
    print("=" * 70)

    # 동적 import
    from tool.diet_agent import run_nutrition_agent

    try:
        recommendation = run_nutrition_agent()
        print("\n" + "=" * 70)
        print("💡 추천 식단")
        print("=" * 70)
        print(recommendation)
        print("=" * 70)
        print("\n✅ 식단 추천이 완료되었습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")


def handle_report(params: dict):
    """리포트 요청 핸들러"""
    print("\n📊 리포트")
    print("=" * 70)

    # 동적 import
    from tool.reporter import run_daily_coach, run_weekly_coach

    # report_type 확인
    report_type = params.get("report_type", "daily")

    try:
        if report_type == "weekly":
            print("주간 리포트 생성 중...\n")
            report = run_weekly_coach()
        else:
            print("일일 리포트 생성 중...\n")
            report = run_daily_coach()

        print("=" * 70)
        print(report)
        print("=" * 70)
        print("\n✅ 리포트 생성이 완료되었습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")


# ============================================================================
# 메인 에이전트 실행
# ============================================================================

def run_agent():
    """통합 에이전트 메인 루프"""
    print("\n" + "=" * 70)
    print("🥗 AI 영양사 에이전트에 오신 것을 환영합니다!")
    print("=" * 70)
    print("\n📌 가능한 기능:")
    print("  1. 프로필/목표 설정: '목표 칼로리 설정해줘', 'BMR 계산'")
    print("  2. 식단 기록: '현미밥 200g 먹었어', '점심 기록'")
    print("  3. 식단 추천: '뭐 먹으면 좋을까?', '저녁 메뉴 추천'")
    print("  4. 리포트: '오늘 리포트', '이번 주 분석'")
    print("  5. 종료: 'exit', 'quit', '종료'\n")

    while True:
        try:
            user_input = input("\n💬 무엇을 도와드릴까요? > ").strip()

            if not user_input:
                continue

            # 종료 명령어 확인
            if user_input.lower() in ["exit", "quit", "종료", "나가기"]:
                print("\n👋 이용해 주셔서 감사합니다!")
                break

            # 의도 분류
            print("\n🤔 요청을 분석 중...")
            intent = classify_intent(user_input)

            print(f"📍 분류: {intent['category'].value}")
            print(f"   확신도: {intent['confidence']:.1%}")
            print(f"   이유: {intent['reasoning']}")

            # 카테고리별 핸들러 실행
            if intent["category"] == IntentCategory.PROFILE_SETUP:
                handle_profile_setup(intent["params"])

            elif intent["category"] == IntentCategory.MEAL_RECORD:
                handle_meal_record(intent["params"])

            elif intent["category"] == IntentCategory.DIET_RECOMMEND:
                handle_diet_recommend(intent["params"])

            elif intent["category"] == IntentCategory.REPORT:
                handle_report(intent["params"])

            else:
                print("\n❓ 요청을 이해하지 못했습니다. 다시 시도해주세요.")
                print("   예시: '목표 설정', '식단 기록', '메뉴 추천', '리포트'")

        except KeyboardInterrupt:
            print("\n\n👋 이용해 주셔서 감사합니다!")
            break
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            print("   다시 시도해주세요.")


def main():
    """프로그램 진입점"""
    run_agent()


if __name__ == "__main__":
    main()
