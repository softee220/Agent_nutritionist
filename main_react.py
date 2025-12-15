#!/usr/bin/env python3
"""
Agent Nutritionist - 통합 영양 관리 에이전트 (ReAct 스타일 AgentExecutor)

기능:
1. 프로필/목표 설정 (tool.bmrcal)
2. 식단 기록/추가 (tool.calnnutri)
3. 식단 추천 (tool.diet_agent)
4. 리포트 요청 (tool.reporter)

동작 방식:
- LangChain AgentExecutor / ReAct 패턴과 유사하게
  Thought → Action → Action Input → Observation → Thought … 를 반복하다가
  마지막에 Final Answer 를 출력하고 종료.
"""

import os
import json
import re
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

def get_today_str():
    # 예: "2025-12-04 11:32:10 KST"
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S %Z")

# =============================================================================
# 환경 설정 / OpenAI 클라이언트
# =============================================================================

load_dotenv()  # .env 에서 OPENAI_API_KEY 로드
client = OpenAI()  # OPENAI_API_KEY 환경변수 사용


# =============================================================================
# 개별 툴 핸들러 정의
# =============================================================================

def handle_profile_setup(params: dict):
    """
    프로필/목표 설정 핸들러
    - 내부적으로 tool.bmrcal.main() 실행
    - ReAct 에이전트에게는 간단한 텍스트를 Observation 으로 반환
    """
    print("\n🎯 프로필 및 목표 설정")
    print("=" * 70)

    from tool.bmrcal import main as bmr_main

    try:
        bmr_main()
        msg = "프로필 및 목표 설정이 완료되었습니다."
        print(f"\n✅ {msg}")
        return msg
    except Exception as e:
        err = f"프로필 설정 중 오류 발생: {e}"
        print(f"❌ {err}")
        return err


def handle_meal_record(params: dict):
    from tool.calnnutri import record_nutrition

    meal_desc = params.get("meal_description", "")
    meal_desc = meal_desc.strip() if isinstance(meal_desc, str) else ""

    if not meal_desc:
        # 여기서 직접 물어보지 말고, LLM에게 "파라미터 부족"이라는 Observation을 돌려줌
        msg = "meal_record 도구를 사용하려면 meal_description 파라미터가 필요합니다."
        print("❗ " + msg)
        return msg

    try:
        result = record_nutrition(meal_desc)
        msg = "식단 기록이 완료되었습니다."
        print("\n✅ " + msg)
        return msg
    except Exception as e:
        err = f"식단 기록 중 오류 발생: {e}"
        print("❌ " + err)
        return err


def handle_diet_recommend(params: dict):
    """
    식단 추천 핸들러
    - tool.diet_agent.run_nutrition_agent 사용
    """
    print("\n🍽️ 식단 추천")
    print("=" * 70)

    from tool.diet_agent import run_nutrition_agent

    try:
        recommendation = run_nutrition_agent()
        text = str(recommendation)
        print("\n" + "=" * 70)
        print("💡 추천 식단")
        print("=" * 70)
        print(text)
        print("=" * 70)
        print("\n✅ 식단 추천이 완료되었습니다.")
        return text
    except Exception as e:
        err = f"식단 추천 중 오류 발생: {e}"
        print(f"❌ {err}")
        return err


def handle_report(params: dict):
    """
    리포트 생성 핸들러
    - tool.reporter.run_daily_coach / run_weekly_coach 사용
    - params["report_type"] 가 "weekly" 면 주간, 아니면 일일 리포트
    """
    print("\n📊 리포트 생성")
    print("=" * 70)

    from tool.reporter import run_daily_coach, run_weekly_coach

    report_type = params.get("report_type", "daily")

    try:
        if report_type == "weekly":
            print("주간 리포트 생성 중...\n")
            report = run_weekly_coach()
        else:
            print("일일 리포트 생성 중...\n")
            report = run_daily_coach()

        text = str(report)
        print("=" * 70)
        print(text)
        print("=" * 70)
        print("\n✅ 리포트 생성이 완료되었습니다.")
        return text
    except Exception as e:
        err = f"리포트 생성 중 오류 발생: {e}"
        print(f"❌ {err}")
        return err


# =============================================================================
# 툴 레지스트리 (에이전트가 사용할 수 있는 도구 목록)
# =============================================================================

TOOL_HANDLERS = {
    "profile_setup": handle_profile_setup,
    "meal_record": handle_meal_record,
    "diet_recommend": handle_diet_recommend,
    "report": handle_report,
}


# =============================================================================
# LLM 호출 헬퍼 (에이전트용)
# =============================================================================

def agent_llm(messages):
    """
    OpenAI ChatCompletion 래퍼.
    messages: [{"role": "...", "content": "..."}, ...]
    """
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.0,
    )
    return completion.choices[0].message.content


# =============================================================================
# ReAct 스타일 AgentExecutor 메인 루프
# =============================================================================

def run_react_agent_once(user_input: str):
    """
    한 번의 사용자 입력에 대해:
    Thought → Action → Observation → ... → Final Answer
    루프를 수행하는 에이전트.
    """
    today_str = get_today_str()
    system_prompt = """
너는 여러 도구를 사용해 사용자의 영양 관리 목표를 달성하는 AI 에이전트이다.

중요: 지금 이 코드가 실행되는 시점의 실제 날짜와 시간은
"{today_str}" 이다. (대한민국 표준시, KST 기준)

사용자의 질문에서 '오늘', '지금', '어제', '이번 주' 등
상대적인 날짜 표현이 나오면 반드시 위 날짜를 기준으로 해석해야 한다.

사용할 수 있는 도구 목록:

1. profile_setup
   - 설명: 사용자의 프로필 및 목표 칼로리, BMR/TDEE 등을 설정하거나 수정하는 도구
   - 내부 구현: tool.bmrcal.main()

2. meal_record
   - 설명: 사용자가 **이미 먹은 구체적인 음식**(텍스트 설명)을 받아 영양 정보를 기록하는 도구
   - 내부 구현: tool.calnnutri.record_nutrition(meal_description)
   - Action Input 예시: {"meal_description": "현미밥 200g이랑 닭가슴살 100g 먹었어"}

3. diet_recommend
   - 설명: 현재 프로필과 식단 기록을 기반으로 앞으로의 식단을 추천하는 도구
   - 내부 구현: tool.diet_agent.run_nutrition_agent()

4. report
   - 설명: 일간/주간 리포트를 생성하는 도구
   - 내부 구현: tool.reporter.run_daily_coach(), tool.reporter.run_weekly_coach()
   - Action Input 예시: {"report_type": "daily"} 또는 {"report_type": "weekly"}

반드시 아래 형식을 지켜서 출력해야 한다:

Thought: (지금 무엇을 해야 할지에 대한 너의 생각을 한국어로 작성)
Action: (사용할 도구 이름: profile_setup / meal_record / diet_recommend / report 중 하나)
Action Input: (JSON 형식의 파라미터, 예: {"meal_description": "..."} 또는 {} )

도구 실행 결과(Observation)를 받은 후에는,
다시 위와 같은 형식의 Thought / Action / Action Input 을 출력하거나,
모든 작업이 끝났다면 아래 형식으로 최종 답변을 출력해라:

Final Answer: (사용자에게 보여줄 최종 답변을 한국어로 작성)

규칙:
- 최소 0개 이상, 여러 개의 도구를 순서대로 사용할 수 있다.
- 도구가 더 이상 필요 없으면 Final Answer 를 출력하고 종료한다.
- Action 없이 Final Answer만 출력하지 말고, 필요한 경우 반드시 도구를 사용하라.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input},
    ]

    print("\n===== 🔥 Agent Execution Start =====")

    # 무한 루프 방지용 최대 스텝 수
    max_steps = 10
    step_count = 0

    while True:
        step_count += 1
        if step_count > max_steps:
            print("\n⚠️ 최대 스텝 수를 초과하여 에이전트를 종료합니다.")
            return "에이전트 최대 스텝 수를 초과하여 강제 종료되었습니다."

        # 1) LLM에게 Thought / Action / Action Input 또는 Final Answer 요청
        llm_output = agent_llm(messages)
        print("\n🤖 LLM OUTPUT:\n")
        print(llm_output)

        # 2) Final Answer 가 포함되어 있으면 종료
        if "Final Answer:" in llm_output:
            final = llm_output.split("Final Answer:", 1)[1].strip()
            print("\n===== 🎉 Final Answer =====\n")
            print(final)
            return final

        # 3) Action / Action Input 파싱
        action_match = re.search(r"Action:\s*([a-zA-Z_]+)", llm_output)
        input_match = re.search(r"Action Input:\s*(\{.*\})", llm_output, re.DOTALL)

        if not action_match:
            # Action 을 못 찾았으면 에러 처리
            error_msg = "LLM이 Action을 생성하지 않았습니다. 출력:\n" + llm_output
            print("\n❌ " + error_msg)
            return error_msg

        tool_name = action_match.group(1).strip()
        params = {}

        if input_match:
            params_json = input_match.group(1)
            try:
                params = json.loads(params_json)
            except Exception:
                # JSON 파싱 실패 시 문자열 그대로 넘김
                params = {"raw_input": params_json}

        print(f"\n▶ Executing Tool: {tool_name}")
        print(f"   params = {params}")

        # 4) 실제 툴 실행
        handler = TOOL_HANDLERS.get(tool_name)
        if handler is None:
            observation = f"Unknown tool: {tool_name}"
        else:
            try:
                result = handler(params)
                # handler 가 None 을 반환해도 문자열로 캐스팅
                observation = str(result)
            except Exception as e:
                observation = f"Tool Error: {e}"

        # 5) Observation을 LLM에게 다시 전달
        obs_message = f"Observation: {observation}"
        messages.append({"role": "assistant", "content": llm_output})
        messages.append({"role": "assistant", "content": obs_message})

        print("\n🔍 Observation:\n")
        print(observation)
        print("\n==================================")


# =============================================================================
# CLI 루프
# =============================================================================

def run_agent():
    """통합 에이전트 CLI 루프 (여러 번 질의 가능)"""
    print("\n" + "=" * 70)
    print("🥗 AI 영양사 에이전트 (ReAct AgentExecutor 스타일)")
    print("=" * 70)
    print("\n 식사하셨으면 뭘 먹었는지 말씀해 주세요!")
    print("\n📌 가능한 예시:")
    print("  - '목표 칼로리 설정해줘', 'BMR 계산해줘'")
    print("  - '현미밥 200g 먹었어', '점심 기록해줘'")
    print("  - '저녁 뭐 먹으면 좋을까?', '식단 추천해줘'")
    print("  - '오늘 리포트 보여줘', '이번 주 분석해줘'")
    print("  - 종료: 'exit', 'quit', '종료'\n")

    while True:
        try:
            user_input = input("\n💬 무엇을 도와드릴까요? > ").strip()

            if user_input.lower() in {"exit", "quit", "종료"}:
                print("\n\n👋 이용해 주셔서 감사합니다!")
                break

            if not user_input:
                print("아무 것도 입력되지 않았습니다. 다시 입력해 주세요.")
                continue

            # LangChain AgentExecutor 와 유사한 ReAct 에이전트 실행
            run_react_agent_once(user_input)

        except KeyboardInterrupt:
            print("\n\n👋 (Ctrl+C)로 종료합니다. 이용해 주셔서 감사합니다!")
            break
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            print("   다시 시도해 주세요.")


def main():
    """프로그램 진입점"""
    run_agent()


if __name__ == "__main__":
    main()
