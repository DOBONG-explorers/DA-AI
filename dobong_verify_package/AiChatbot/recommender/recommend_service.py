# AiChatbot/recommender/recommend_service.py
from recommender.data_loader import get_all_data
from recommender.scoring import score_places, _to_id_set, KEYWORD_TO_TAG_MAP

def _detect_requested_bias(category, keyword):
    if category in ("느좋", "핫플"):
        return category
    if keyword:
        if keyword in ("느좋", "핫플"):
            return keyword
        for k in ("느좋", "핫플"):
            if k in keyword:
                return k
    return None

def recommend_places(category, keyword, user_loc, k, seed, offset=0):
    data = get_all_data()

    hot_all = data.get("핫플", []) or []
    neu_all = data.get("느좋", []) or []
    hot_low = data.get("핫플_low", []) or []
    neu_low = data.get("느좋_low", []) or []

    # id 병합
    def _to_id(p):
        return p.get("id") or p.get("placeId") or p.get("place_id") or p.get("name")

    merged = {}
    for p in hot_all:
        pid = _to_id(p)
        if pid: merged[pid] = p
    for p in neu_all:
        pid = _to_id(p)
        if pid: merged[pid] = p

    low20_ids = _to_id_set(hot_low) | _to_id_set(neu_low)
    low50_ids = set()  # 필요 시 확장

    requested_bias = _detect_requested_bias(category, keyword)

    scored_list = score_places(
        places_all=list(merged.values()),
        low20_ids=low20_ids,
        low50_ids=low50_ids,
        keyword=keyword,
        user_loc=user_loc,
        seed=seed,
        requested_bias=requested_bias,
    )

    start = max(0, int(offset or 0))
    end = start + int(k or 5)
    return scored_list[start:end]

def health_status():
    data = get_all_data()
    return {
        "data_loaded": bool(data),
        "hotple_count_all": len(data.get("핫플", [])),
        "neujoh_count_all": len(data.get("느좋", [])),
        "hotple_count_low": len(data.get("핫플_low", [])),
        "neujoh_count_low": len(data.get("느좋_low", [])),
    }
