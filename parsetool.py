import os
import json
import time
import random
import hmac
import hashlib
import base64
import urllib.parse
import requests
from dotenv import load_dotenv
from openai import OpenAI

# --------------------------------------------------------------------------------
# 1. 설정 및 초기화
# --------------------------------------------------------------------------------
# .env 파일에서 API 키 로드
load_dotenv()

FATSECRET_KEY = os.getenv("FATSECRET_CONSUMER_KEY")
FATSECRET_SECRET = os.getenv("FATSECRET_CONSUMER_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 필수 키 확인
if not all([FATSECRET_KEY, FATSECRET_SECRET, OPENAI_API_KEY]):
    print("❌ 오류: .env 파일에 다음 키가 모두 정의되어 있어야 합니다:")
    print(" - FATSECRET_CONSUMER_KEY")
    print(" - FATSECRET_CONSUMER_SECRET")
    print(" - OPENAI_API_KEY")
    exit(1)

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=OPENAI_API_KEY)


# --------------------------------------------------------------------------------
# 2. FatSecret API 클라이언트 (OAuth 1.0 구현)
# --------------------------------------------------------------------------------
class FatSecretAPI:
    def __init__(self, key, secret):
        self.consumer_key = key
        self.consumer_secret = secret
        self.url = "https://platform.fatsecret.com/rest/server.api"
    
    def _sign_request(self, params):
        """OAuth 1.0 HMAC-SHA1 서명 생성"""
        # 1. 기본 OAuth 파라미터 추가
        params['oauth_consumer_key'] = self.consumer_key
        params['oauth_nonce'] = str(random.randint(0, 100000000))
        params['oauth_signature_method'] = 'HMAC-SHA1'
        params['oauth_timestamp'] = str(int(time.time()))
        params['oauth_version'] = '1.0'

        # 2. 파라미터 정렬 및 정규화
        sorted_params = sorted(params.items())
        normalized_params = urllib.parse.urlencode(sorted_params)

        # 3. Base String 생성 (Method + URL + Params)
        # FatSecret은 GET 요청을 주로 사용
        base_string = "&".join([
            "GET",
            urllib.parse.quote(self.url, safe=''),
            urllib.parse.quote(normalized_params, safe='')
        ])

        # 4. Signing Key 생성 (Consumer Secret + "&")
        # Access Token이 없으므로 & 뒤는 비워둡니다.
        signing_key = f"{self.consumer_secret}&"

        # 5. HMAC-SHA1 서명 생성
        hashed = hmac.new(
            signing_key.encode('utf-8'),
            base_string.encode('utf-8'),
            hashlib.sha1
        )
        signature = base64.b64encode(hashed.digest()).decode('utf-8')
        
        return signature

    def _request(self, method, params):
        """API 요청 공통 함수 (OAuth 1.0 적용)"""
        params['method'] = method
        params['format'] = 'json'
        
        # 서명 생성 및 추가
        signature = self._sign_request(params)
        params['oauth_signature'] = signature
        
        try:
            response = requests.get(self.url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[API Error] 요청 실패 ({method}): {e}")
            if response is not None:
                print(f"[Debug] Response: {response.text}")
            return None

    def search_food(self, query):
        """음식 이름으로 검색하여 가장 연관성 높은 결과 반환"""
        # 새로운 딕셔너리로 파라미터 전달 (참조로 인한 오염 방지)
        params = {"search_expression": query, "max_results": 1}
        data = self._request("foods.search", params)
        
        if not data or 'foods' not in data:
            return None
        
        food_list = data['foods'].get('food', [])
        
        # 결과가 1개일 때는 dict, 여러 개일 때는 list로 반환됨
        if isinstance(food_list, list):
            return food_list[0] if food_list else None
        return food_list

    def get_food_details(self, food_id):
        """음식 ID로 상세 정보(서빙 단위 포함) 조회"""
        params = {"food_id": str(food_id)}
        return self._request("food.get.v2", params)


# --------------------------------------------------------------------------------
# 3. LLM 파싱 및 추정 모듈
# --------------------------------------------------------------------------------
def parse_user_input_to_food_list(user_text):
    """
    자연어 입력을 분석하여 구조화된 JSON 데이터로 변환
    """
    prompt = f"""
    You are a professional nutritionist assistant. 
    Analyze the input text and extract food items.
    For each item, estimate the weight in grams (g) based on standard serving sizes (e.g., 1 bowl of rice ≈ 210g).
    
    Return a strictly valid JSON list of objects with these keys:
    - "name_kr": Korean name of the food.
    - "search_term_specific": Specific English name for database search (e.g., specific brand or detailed dish name).
    - "search_term_generic": Very generic English name for fallback search (e.g., 'Shin Ramyun' -> 'Instant Noodles').
    - "weight_g": Estimated weight in grams (integer).

    Input: "{user_text}"
    
    Output example: 
    [{{"name_kr": "밥", "search_term_specific": "Steamed Rice", "search_term_generic": "Rice", "weight_g": 210}}]
    
    Do not include markdown formatting like ```json. Just raw JSON.
    """
    
    try:
        completion = client.chat.completions.create(
            model="gpt-4o", # 또는 gpt-3.5-turbo
            messages=[{"role": "system", "content": "You are a JSON extractor."},
                      {"role": "user", "content": prompt}],
            temperature=0
        )
        content = completion.choices[0].message.content.strip()
        # 마크다운 제거 (혹시 포함될 경우 대비)
        content = content.replace("```json", "").replace("```", "")
        return json.loads(content)
    except Exception as e:
        print(f"[LLM Error] 파싱 실패: {e}")
        return []

def estimate_calories_with_llm(name, weight_g):
    """
    API 데이터 확보 실패 시 LLM에게 추정 요청
    """
    prompt = f"""
    I ate {weight_g}g of {name}. 
    I cannot find this food in the database.
    Please estimate the total calories.
    
    Return a strictly valid JSON object:
    {{
        "calories": (float) estimated total calories,
        "reason": "Short explanation in Korean about how you estimated it."
    }}
    Do not include markdown formatting.
    """
    
    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        content = completion.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "")
        data = json.loads(content)
        return data['calories'], data['reason']
    except Exception:
        return 0, "데이터 부족으로 계산 불가"


# --------------------------------------------------------------------------------
# 4. 핵심 로직: 칼로리 계산 파이프라인
# --------------------------------------------------------------------------------
def try_get_metric_calories(api_details, user_g):
    """
    API 상세 정보에서 'g' 단위 서빙 정보를 찾아 계산
    반환: (총 칼로리, g당 칼로리, 서빙설명) 또는 None
    """
    if not api_details or 'food' not in api_details:
        return None
    
    # servings가 dict일수도 list일수도 있음
    servings_data = api_details['food'].get('servings', {}).get('serving', [])
    if isinstance(servings_data, dict):
        servings_data = [servings_data]
        
    # 1순위: metric_serving_unit이 'g'인 항목 찾기
    for s in servings_data:
        if s.get('metric_serving_unit') == 'g':
            try:
                metric_amt = float(s.get('metric_serving_amount', 0))
                kcal = float(s.get('calories', 0))
                
                if metric_amt > 0:
                    kcal_per_g = kcal / metric_amt
                    total_cal = user_g * kcal_per_g
                    return total_cal, kcal_per_g, s
            except ValueError:
                continue
    
    # 2순위: g 단위가 없다면 일반 서빙(1 serving) 기준으로 대략적 환산 시도 (여기선 생략하고 g 우선 전략 유지)
    return None

def process_pipeline(food_list, api):
    """
    3단계 전략 실행: 구체적 검색 -> 일반 검색 -> LLM 추정
    """
    final_results = []
    
    for item in food_list:
        name = item['name_kr']
        weight = item['weight_g']
        specific = item['search_term_specific']
        generic = item['search_term_generic']
        
        print(f"🔍 '{name}' ({weight}g) 분석 중...")
        
        # [전략 1] 구체적 이름으로 API 검색
        cal_info = None
        method = "API (상세)"
        
        search_res = api.search_food(specific)
        if search_res:
            details = api.get_food_details(search_res['food_id'])
            cal_info = try_get_metric_calories(details, weight)
        
        # [전략 2] 데이터 없으면 Generic 이름으로 API 검색
        if not cal_info:
            print(f"   ↳상세 정보 부족, '{generic}'(으)로 재검색...")
            search_res_gen = api.search_food(generic)
            if search_res_gen:
                details_gen = api.get_food_details(search_res_gen['food_id'])
                cal_info = try_get_metric_calories(details_gen, weight)
                if cal_info:
                    method = f"API (일반: {generic})"
        
        # 결과 정리
        if cal_info:
            total_cal, per_g, serving_info = cal_info
            note = f"{method} - {serving_info.get('serving_description')} 기준"
            k_unit = f"{per_g:.2f} kcal/g"
        else:
            # [전략 3] LLM 추정
            print(f"   ↳API 데이터 없음, AI 추정 모드로 전환...")
            total_cal, reason = estimate_calories_with_llm(name, weight)
            note = f"AI 추정 - {reason}"
            k_unit = "추정치"

        final_results.append({
            "name": name,
            "weight": weight,
            "calories": total_cal,
            "unit_rate": k_unit,
            "note": note
        })
        
    return final_results


# --------------------------------------------------------------------------------
# 5. 메인 실행 함수
# --------------------------------------------------------------------------------
def main():
    print("\n🥑 AI 영양사: 무엇을 드셨나요?")
    user_input = input("입력 (예: 점심에 짬뽕 한 그릇이랑 탕수육 소자 반 정도 먹었어): ")
    
    if not user_input.strip():
        print("입력된 내용이 없습니다.")
        return

    # 1. LLM 파싱
    print("\n>>> 1. 텍스트 분석 중...")
    food_list = parse_user_input_to_food_list(user_input)
    if not food_list:
        print("음식 정보를 찾지 못했습니다.")
        return
    
    # 2. API 연결
    api = FatSecretAPI(FATSECRET_KEY, FATSECRET_SECRET)
    
    # 3. 데이터 조회 및 계산
    print(">>> 2. 영양 정보 데이터베이스 조회 및 계산 중...")
    results = process_pipeline(food_list, api)
    
    # 4. 결과 리포트
    print("\n" + "="*60)
    print(f"🍽️  섭취 리포트: \"{user_input}\"")
    print("="*60)
    
    total_sum = 0
    for r in results:
        print(f"● {r['name']}")
        print(f"  - 섭취량: {r['weight']}g")
        print(f"  - 열량: {r['calories']:.1f} kcal")
        print(f"  - 근거: {r['note']} ({r['unit_rate']})")
        print("-" * 60)
        total_sum += r['calories']
        
    print(f"🏆 총 섭취 칼로리: {total_sum:,.1f} kcal")
    print("="*60)

if __name__ == "__main__":
    main()