import os
import json
import time
import random
import hmac
import hashlib
import base64
import urllib.parse
import requests
from datetime import datetime
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

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


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
        base_string = "&".join([
            "GET",
            urllib.parse.quote(self.url, safe=''),
            urllib.parse.quote(normalized_params, safe='')
        ])

        # 4. Signing Key 생성 (Consumer Secret + "&")
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
            return None

    def search_food(self, query):
        """음식 이름으로 검색"""
        params = {"search_expression": query, "max_results": 1}
        data = self._request("foods.search", params)

        if not data or 'foods' not in data:
            return None

        food_list = data['foods'].get('food', [])
        if isinstance(food_list, list):
            return food_list[0] if food_list else None
        return food_list

    def get_food_details(self, food_id):
        """음식 ID로 상세 정보 조회"""
        params = {"food_id": str(food_id)}
        return self._request("food.get.v2", params)


# --------------------------------------------------------------------------------
# 3. LLM 파싱 및 추정 모듈
# --------------------------------------------------------------------------------
def parse_user_input_to_food_list(user_text):
    """자연어 입력 -> 음식 목록 및 g 단위 추정"""
    if not client:
        return []

    prompt = f"""
    You are a professional nutritionist assistant.
    Analyze the input text and extract food items.
    For each item, estimate the weight in grams (g) based on standard serving sizes.

    Return a strictly valid JSON list of objects:
    - "name_kr": Korean name.
    - "search_term_specific": Specific English name for DB search.
    - "search_term_generic": Generic English name for fallback.
    - "weight_g": Estimated weight in grams (integer).

    Input: "{user_text}"
    Output example: [{{"name_kr": "밥", "search_term_specific": "Steamed Rice", "search_term_generic": "Rice", "weight_g": 210}}]
    """

    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "You are a JSON extractor."},
                      {"role": "user", "content": prompt}],
            temperature=0
        )
        content = completion.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "")
        return json.loads(content)
    except Exception as e:
        print(f"[LLM Error] 파싱 실패: {e}")
        return []

def estimate_nutrients_with_llm(name, weight_g):
    """API 데이터 확보 실패 시 LLM에게 상세 영양 성분 추정 요청"""
    if not client:
        return {
            "calories": 0, "carbohydrate": 0, "protein": 0, "fat": 0,
            "sodium": 0, "sugar": 0, "reason": "OpenAI client not initialized"
        }

    prompt = f"""
    I ate {weight_g}g of {name}.
    I cannot find this food in the database.
    Please estimate the nutritional information.

    Return a strictly valid JSON object:
    {{
        "calories": (float) kcal,
        "carbohydrate": (float) g,
        "protein": (float) g,
        "fat": (float) g,
        "sodium": (float) mg,
        "sugar": (float) g,
        "reason": "Short explanation in Korean."
    }}
    """

    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        content = completion.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "")
        return json.loads(content)
    except Exception:
        # 실패 시 0으로 채워진 기본값 반환
        return {
            "calories": 0, "carbohydrate": 0, "protein": 0, "fat": 0,
            "sodium": 0, "sugar": 0, "reason": "데이터 부족 및 추정 실패"
        }


# --------------------------------------------------------------------------------
# 4. 핵심 로직: 영양 성분 계산 파이프라인
# --------------------------------------------------------------------------------
def calculate_nutrients_from_api(api_details, user_g):
    """
    API 상세 정보에서 'g' 단위 서빙 정보를 찾아 영양 성분 계산
    반환: (영양정보Dict, 서빙설명) 또는 None
    """
    if not api_details or 'food' not in api_details:
        return None

    servings_data = api_details['food'].get('servings', {}).get('serving', [])
    if isinstance(servings_data, dict):
        servings_data = [servings_data]

    for s in servings_data:
        if s.get('metric_serving_unit') == 'g':
            try:
                metric_amt = float(s.get('metric_serving_amount', 0))
                if metric_amt <= 0: continue

                # 비율 계산 (사용자가 먹은 양 / 기준 양)
                ratio = user_g / metric_amt

                # 영양소 추출 및 계산 (없으면 0 처리)
                nutrients = {
                    "calories": float(s.get('calories', 0)) * ratio,
                    "carbohydrate": float(s.get('carbohydrate', 0)) * ratio,
                    "protein": float(s.get('protein', 0)) * ratio,
                    "fat": float(s.get('fat', 0)) * ratio,
                    "sodium": float(s.get('sodium', 0)) * ratio, # mg
                    "sugar": float(s.get('sugar', 0)) * ratio
                }

                return nutrients, s
            except ValueError:
                continue

    return None

def process_pipeline(food_list, api):
    """3단계 전략: 구체적 검색 -> 일반 검색 -> LLM 추정"""
    final_results = []

    for item in food_list:
        name = item['name_kr']
        weight = item['weight_g']
        specific = item['search_term_specific']
        generic = item['search_term_generic']

        print(f"🔍 '{name}' ({weight}g) 분석 중...")

        nutrients = None
        method = ""

        # [전략 1] 구체적 이름 검색
        search_res = api.search_food(specific)
        if search_res:
            details = api.get_food_details(search_res['food_id'])
            result = calculate_nutrients_from_api(details, weight)
            if result:
                nutrients, s_info = result
                method = f"API (상세: {s_info.get('serving_description')})"

        # [전략 2] 일반 이름 검색
        if not nutrients:
            print(f"   ↳상세 정보 부족, '{generic}'(으)로 재검색...")
            search_res_gen = api.search_food(generic)
            if search_res_gen:
                details_gen = api.get_food_details(search_res_gen['food_id'])
                result = calculate_nutrients_from_api(details_gen, weight)
                if result:
                    nutrients, s_info = result
                    method = f"API (일반: {generic})"

        # [전략 3] LLM 추정
        if not nutrients:
            print(f"   ↳API 데이터 없음, AI 추정 모드로 전환...")
            nutrients = estimate_nutrients_with_llm(name, weight)
            method = f"AI 추정 ({nutrients.get('reason', '')})"

        final_results.append({
            "name": name,
            "weight": weight,
            "nutrients": nutrients,
            "note": method
        })

    return final_results


# --------------------------------------------------------------------------------
# 5. 외부에서 사용할 수 있는 함수 (모듈용)
# --------------------------------------------------------------------------------
def record_nutrition(user_input: str, log_path: str = "./log/nutrition.txt"):
    """
    사용자 입력을 받아 영양 정보를 계산하고 파일에 기록합니다.

    Args:
        user_input: 음식 설명 (예: "현미밥 200g이랑 닭가슴살 100g 먹었어")
        log_path: 저장할 로그 파일 경로 (기본: ./log/nutrition.txt)

    Returns:
        dict: 총합 영양 정보 딕셔너리
    """
    if not user_input.strip():
        print("입력된 내용이 없습니다.")
        return None

    # 1. LLM 파싱
    print("\n>>> 1. 텍스트 분석 중...")
    food_list = parse_user_input_to_food_list(user_input)
    if not food_list:
        print("음식 정보를 찾지 못했습니다.")
        return None

    # 2. API 연결
    if not FATSECRET_KEY or not FATSECRET_SECRET:
        print("FatSecret API 키가 설정되지 않았습니다.")
        return None

    api = FatSecretAPI(FATSECRET_KEY, FATSECRET_SECRET)

    # 3. 데이터 조회 및 계산
    print(">>> 2. 영양 정보 데이터베이스 조회 및 계산 중...")
    results = process_pipeline(food_list, api)

    # 4. 결과 리포트
    print("\n" + "="*70)
    print(f"🍽️  섭취 리포트: \"{user_input}\"")
    print("="*70)
    print(f"{'음식명':<10} | {'열량':<8} | {'탄수':<7} | {'단백':<7} | {'지방':<7} | {'당류':<7} | {'나트륨':<8}")
    print("-" * 70)

    total = {"calories": 0, "carbohydrate": 0, "protein": 0, "fat": 0, "sugar": 0, "sodium": 0}

    for r in results:
        n = r['nutrients']
        print(f"{r['name']:<10} | {n['calories']:>6.1f}kc | {n['carbohydrate']:>5.1f}g  | {n['protein']:>5.1f}g  | {n['fat']:>5.1f}g  | {n['sugar']:>5.1f}g  | {n['sodium']:>6.0f}mg")
        # 합계 누적
        for key in total:
            total[key] += n.get(key, 0)

    print("="*70)
    print(f"🏆 [총 합계]")
    print(f"   ● 칼로리 : {total['calories']:,.1f} kcal")
    print(f"   ● 탄수화물: {total['carbohydrate']:,.1f} g")
    print(f"   ● 단백질  : {total['protein']:,.1f} g")
    print(f"   ● 지방    : {total['fat']:,.1f} g")
    print(f"   ● 당류    : {total['sugar']:,.1f} g")
    print(f"   ● 나트륨  : {total['sodium']:,.0f} mg")
    print("="*70)

    # 5. 파일 로그 저장
    try:
        log_dir = os.path.dirname(log_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # 현재 시간
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 저장할 문자열 생성
        log_content = f"[{now_str}]\n"
        log_content += f"   ● 칼로리 : {total['calories']:,.1f} kcal\n"
        log_content += f"   ● 탄수화물: {total['carbohydrate']:,.1f} g\n"
        log_content += f"   ● 단백질  : {total['protein']:,.1f} g\n"
        log_content += f"   ● 지방    : {total['fat']:,.1f} g\n"
        log_content += f"   ● 당류    : {total['sugar']:,.1f} g\n"
        log_content += f"   ● 나트륨  : {total['sodium']:,.0f} mg\n"

        # 파일이 이미 존재하면 앞에 2칸 줄바꿈(\n\n) 추가
        prefix = "\n\n" if os.path.exists(log_path) else ""

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(prefix + log_content)

        print(f"📄 결과가 '{log_path}'에 저장되었습니다.")

    except Exception as e:
        print(f"⚠️ 로그 저장 실패: {e}")

    return total


# --------------------------------------------------------------------------------
# 6. 메인 실행 함수 (CLI용)
# --------------------------------------------------------------------------------
def main():
    print("\n🥑 AI 영양사: 무엇을 드셨나요?")
    user_input = input("입력 (예: 현미밥 200g이랑 닭가슴살 100g 먹었어): ")
    record_nutrition(user_input)


if __name__ == "__main__":
    main()
