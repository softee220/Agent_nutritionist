from datetime import datetime
from parseandnutrition import (
    parse_user_input_to_food_list,
    process_pipeline,
    FatSecretAPI,
    FATSECRET_KEY,
    FATSECRET_SECRET
)
from coach import (
    append_meal_log,
    generate_daily_report_for,
)

# 끼니 정보
MEAL_TYPES = {
    "1": ("breakfast", "아침"),
    "2": ("lunch", "점심"),
    "3": ("dinner", "저녁")
}
MEAL_NAME_KR = {cfg[0]: cfg[1] for cfg in MEAL_TYPES.values()}


def calculate_total_nutrients(results):
    """process_pipeline 결과에서 총 영양 성분 계산"""
    total = {
        "calories": 0.0,
        "carbohydrate": 0.0,
        "protein": 0.0,
        "fat": 0.0,
        "sugar": 0.0,
        "sodium": 0.0
    }
    
    for r in results:
        n = r.get('nutrients', {})
        # reason 키는 제거 (LLM 추정 시 포함될 수 있음)
        if 'reason' in n:
            del n['reason']
        
        for key in total.keys():
            total[key] += float(n.get(key, 0.0))
    
    return total


def process_meal(meal_type_en: str, meal_type_kr: str, api: FatSecretAPI):
    """한 끼니 처리: 입력받고 분석하여 로그 저장"""
    print(f"\n{'='*100}")
    print(f"🍽️  {meal_type_kr} 식사 기록")
    print(f"{'='*100}")
    
    user_input = input(
        f"{meal_type_kr}에 무엇을 드셨나요? (예: 현미밥 200g이랑 닭가슴살 100g 먹었어)\n"
        "입력 (엔터만 누르면 건너뜀): "
    ).strip()
    
    if not user_input:
        print(f"⏭️  {meal_type_kr} 식사를 건너뛰었습니다.\n")
        return None, True
    
    # 1. LLM 파싱
    print(f"\n>>> {meal_type_kr} 텍스트 분석 중...")
    food_list = parse_user_input_to_food_list(user_input)
    if not food_list:
        print(f"❌ {meal_type_kr} 음식 정보를 찾지 못했습니다.")
        return None, False
    
    # 2. 영양 정보 계산
    print(f">>> {meal_type_kr} 영양 정보 데이터베이스 조회 및 계산 중...")
    results = process_pipeline(food_list, api)
    
    # 3. 총 영양 성분 계산
    total_nutrients = calculate_total_nutrients(results)
    
    # 4. 결과 출력
    print(f"\n{'─'*100}")
    print(f"📊 {meal_type_kr} 섭취 리포트")
    print(f"{'─'*100}")
    print(f"{'음식명':<15} | {'열량':<8} | {'탄수':<7} | {'단백':<7} | {'지방':<7} | {'당류':<7} | {'나트륨':<8}")
    print("-" * 100)
    
    for r in results:
        n = r.get('nutrients', {})
        # reason 키 제거 (출력용이 아님)
        n_display = {k: v for k, v in n.items() if k != 'reason'}
        print(f"{r['name']:<15} | {n_display.get('calories', 0):>6.1f}kc | "
              f"{n_display.get('carbohydrate', 0):>5.1f}g  | "
              f"{n_display.get('protein', 0):>5.1f}g  | "
              f"{n_display.get('fat', 0):>5.1f}g  | "
              f"{n_display.get('sugar', 0):>5.1f}g  | "
              f"{n_display.get('sodium', 0):>6.0f}mg")
    
    print("-" * 100)
    print(f"💡 {meal_type_kr} 총합:")
    print(f"   • 칼로리: {total_nutrients['calories']:,.1f} kcal")
    print(f"   • 탄수화물: {total_nutrients['carbohydrate']:,.1f} g")
    print(f"   • 단백질: {total_nutrients['protein']:,.1f} g")
    print(f"   • 지방: {total_nutrients['fat']:,.1f} g")
    print(f"   • 당류: {total_nutrients['sugar']:,.1f} g")
    print(f"   • 나트륨: {total_nutrients['sodium']:,.0f} mg")
    print(f"{'─'*70}\n")
    
    # 5. 로그 저장
    append_meal_log(meal_type_en, total_nutrients)
    print(f"✅ {meal_type_kr} 식사 기록이 저장되었습니다.\n")
    
    return total_nutrients, False


def build_basic_daily_report(date_str, recorded_meals, skipped_meals):
    """LLM 실패 시 사용할 기본 일일 리포트 문자열"""
    if not recorded_meals:
        report_lines = [
            f"📅 날짜: {date_str}",
            "📝 오늘 기록된 식사가 없습니다.",
        ]
        if skipped_meals:
            report_lines.append(f"⏭️  건너뛴 끼니: {', '.join(skipped_meals)}")
        return "\n".join(report_lines)
    
    total = {
        "calories": 0.0,
        "carbohydrate": 0.0,
        "protein": 0.0,
        "fat": 0.0,
        "sugar": 0.0,
        "sodium": 0.0
    }
    
    for nutrients in recorded_meals.values():
        for key in total.keys():
            total[key] += nutrients.get(key, 0.0)
    
    recorded_names = [
        MEAL_NAME_KR.get(meal_key, meal_key)
        for meal_key in recorded_meals.keys()
    ]
    
    report_lines = [
        f"📅 날짜: {date_str}",
        f"🍽️  기록된 끼니: {', '.join(recorded_names)}" if recorded_names else "🍽️  기록된 끼니: 없음",
    ]
    
    if skipped_meals:
        report_lines.append(f"⏭️  건너뛴 끼니: {', '.join(skipped_meals)}")
    
    report_lines.extend([
        "",
        "💡 오늘의 총 섭취량:",
        f"   • 칼로리: {total['calories']:,.1f} kcal",
        f"   • 탄수화물: {total['carbohydrate']:,.1f} g",
        f"   • 단백질: {total['protein']:,.1f} g",
        f"   • 지방: {total['fat']:,.1f} g",
        f"   • 당류: {total['sugar']:,.1f} g",
        f"   • 나트륨: {total['sodium']:,.0f} mg",
        "",
        "💡 세 끼 식사를 모두 기록하시면 더 상세한 일일 리포트를 받으실 수 있습니다.",
    ])
    
    return "\n".join(report_lines)


def main():
    """메인 실행 함수: 하루 세 끼 입력받고 리포트 생성"""
    print("\n" + "="*100)
    print("🥑 AI 영양사 - 하루 식사 기록")
    print("="*100)
    print("오늘 하루 동안 드신 세 끼 식사를 기록해주세요.")
    print("각 끼니를 입력하지 않으시면 해당 끼니는 건너뛰기로 기록됩니다.\n")
    
    # API 초기화
    api = FatSecretAPI(FATSECRET_KEY, FATSECRET_SECRET)
    
    # 세 끼니 기록
    recorded_meals = {}
    skipped_meals = []
    
    for _, (meal_type_en, meal_type_kr) in MEAL_TYPES.items():
        total_nutrients, skipped = process_meal(meal_type_en, meal_type_kr, api)
        if total_nutrients:
            recorded_meals[meal_type_en] = total_nutrients
        if skipped:
            skipped_meals.append(meal_type_kr)
    
    # 일일 리포트 생성 (항상 출력)
    today = datetime.now().date().isoformat()
    daily_report = generate_daily_report_for(today, skipped_meals)
    
    if not daily_report:
        daily_report = build_basic_daily_report(today, recorded_meals, skipped_meals)
    
    print("\n" + "="*100)
    print("📋 오늘의 일일 리포트")
    print("="*100)
    print(daily_report)
    print("="*100 + "\n")
    
    print("✨ 하루 식사 기록이 완료되었습니다!")


if __name__ == "__main__":
    main()

