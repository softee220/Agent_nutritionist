import os
from urllib.parse import urlencode

from dotenv import load_dotenv
import requests
from requests_oauthlib import OAuth1

# 1) .env 로드
load_dotenv()

CONSUMER_KEY = os.getenv("FATSECRET_CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("FATSECRET_CONSUMER_SECRET")

if not CONSUMER_KEY or not CONSUMER_SECRET:
    raise RuntimeError("FATSECRET_CONSUMER_KEY / FATSECRET_CONSUMER_SECRET 를 .env에 설정해야 합니다.")

BASE_URL = "https://platform.fatsecret.com/rest/server.api"


def call_fatsecret(params: dict):
    """
    FatSecret REST API 호출 유틸 함수 (OAuth1 서명 포함)
    """
    auth = OAuth1(CONSUMER_KEY, CONSUMER_SECRET)
    # GET 방식으로 호출 (FatSecret v1 스타일)
    resp = requests.get(BASE_URL, params=params, auth=auth)
    try:
        resp.raise_for_status()
    except Exception as e:
        print("HTTP 오류:", e)
        print("응답 텍스트:", resp.text)
        raise
    return resp.json()


def foods_search(search_expression: str, max_results: int = 3):
    """
    foods.search : 음식 이름으로 검색해서 food 리스트 받기
    """
    params = {
        "method": "foods.search",
        "search_expression": search_expression,
        "max_results": max_results,
        "format": "json",
    }
    data = call_fatsecret(params)
    return data


def food_get(food_id: str):
    """
    food.get : food_id로 상세 영양 정보 받기
    """
    params = {
        "method": "food.get",
        "food_id": food_id,
        "format": "json",
    }
    data = call_fatsecret(params)
    return data


def search_and_show(food_name: str):
    print(f"\n===== '{food_name}' 검색 =====")
    data = foods_search(food_name, max_results=3)

    # 응답 구조 체크 (에러 메시지 있는지 먼저 확인)
    if "foods" not in data:
        print("foods 검색 결과에 'foods' 키가 없습니다. 전체 응답:")
        print(data)
        return

    foods = data["foods"].get("food")
    if not foods:
        print("검색 결과(food)가 없습니다.")
        return

    # food가 dict 하나일 수도, list일 수도 있어서 통일
    if isinstance(foods, dict):
        foods = [foods]

    for idx, f in enumerate(foods, start=1):
        food_id = f.get("food_id")
        food_name_api = f.get("food_name")
        food_desc = f.get("food_description")

        print(f"\n--- 결과 #{idx} ---")
        print("food_id:", food_id)
        print("food_name:", food_name_api)
        print("description:", food_desc)

        if not food_id:
            print("food_id 없음, food.get 호출 스킵")
            continue

        detail = food_get(food_id)
        food = detail.get("food")
        if not food:
            print("food.get 응답에 'food' 키 없음:", detail)
            continue

        servings = food.get("servings", {}).get("serving")
        if not servings:
            print("servings 정보 없음")
            continue

        if isinstance(servings, dict):
            servings = [servings]

        print("\n[서빙 리스트]")
        for s in servings:
            serving_desc = s.get("serving_description")
            calories = s.get("calories")
            metric_amount = s.get("metric_serving_amount")
            metric_unit = s.get("metric_serving_unit")

            print(f"- {serving_desc}")
            print(f"    칼로리: {calories} kcal")
            if metric_amount and metric_unit:
                print(f"    기준: {metric_amount} {metric_unit}")

        # g 기준 서빙 하나 골라서 g당 칼로리 계산 예시
        metric_servings = [
            s for s in servings
            if s.get("metric_serving_unit") == "g" and s.get("metric_serving_amount")
        ]
        if metric_servings:
            def diff_from_100(s):
                try:
                    return abs(float(s["metric_serving_amount"]) - 100.0)
                except Exception:
                    return 9999

            best = min(metric_servings, key=diff_from_100)
            try:
                grams = float(best["metric_serving_amount"])
                kcal = float(best["calories"])
                kcal_per_gram = kcal / grams
                print("\n[g당 칼로리 계산]")
                print(f"선택된 서빙: {best.get('serving_description')} ({grams} g, {kcal} kcal)")
                print(f"→ g당: {kcal_per_gram:.3f} kcal/g")
            except Exception as e:
                print("g당 칼로리 계산 에러:", e)


if __name__ == "__main__":
    # 여기서 원하는 음식 이름 바꿔가며 테스트
    search_and_show("banana")
    search_and_show("fried chicken")
    search_and_show("ramen")
