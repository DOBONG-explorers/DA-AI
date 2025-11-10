# AiChatbot/recommender/reask.py
def parse_user_text(user_text: str):
    parsed = {"category": None, "keyword": None, "user_location": None}
    s = (user_text or "").lower()

    if any(kw in s for kw in ["조용한", "둘레길", "공원", "자연", "느긋", "정원", "야경"]):
        parsed["category"] = "느좋"
    elif any(kw in s for kw in ["핫플", "카페", "맛집", "친구", "연인", "데이트"]):
        parsed["category"] = "숨은핫플"

    for kw in ["친구","연인","데이트","카페","맛집","가족","조용한","둘레길","공원","자연","정원","야경"]:
        if kw in s:
            parsed["keyword"] = kw
            break

    parsed["user_location"] = None
    return parsed

def suggest_alternatives(category, keyword):
    base = ["브런치 카페", "야경 좋은 곳", "조용한 정원", "둘레길"]
    try:
        if keyword in base: base.remove(keyword)
    except Exception:
        pass
    return {"message": "대안 키워드를 제시합니다.", "alt_keywords": base[:3]}
