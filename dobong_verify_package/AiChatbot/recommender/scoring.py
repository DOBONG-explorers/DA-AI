# AiChatbot/recommender/scoring.py
import random

# 키워드 → 대분류(하이브리드 비율 허용)
KEYWORD_TO_TAG_MAP = {
    "친구": {"느좋": 0.4, "핫플": 0.6},
    "연인": {"느좋": 0.6, "핫플": 0.4},   # 하이브리드
    "데이트": {"핫플": 1.0},
    "카페": {"핫플": 1.0},
    "맛집": {"핫플": 1.0},
    "가족": {"느좋": 1.0},
    "조용한": {"느좋": 1.0},
    "둘레길": {"느좋": 1.0},
    "공원": {"느좋": 1.0},
    "자연": {"느좋": 1.0},
    "정원": {"느좋": 1.0},
    "야경": {"느좋": 1.0},
}

WEIGHTS = {
    "W_band": 0.55,
    "W_kw":   0.25,
    "W_dist": 0.10,  # TODO: 거리 가중치 자리
    "W_div":  0.05,  # TODO
    "W_rand": 0.05,
}

def _to_id(place: dict):
    return (
        place.get("id")
        or place.get("placeId")
        or place.get("place_id")
        or place.get("name")
    )

def _to_id_set(maybe_list):
    s = set()
    for x in (maybe_list or []):
        if isinstance(x, str):
            s.add(x)
        elif isinstance(x, dict):
            pid = _to_id(x)
            if pid:
                s.add(pid)
    return s

def score_places(
    places_all,
    low20_ids,
    low50_ids,
    keyword,
    user_loc,
    seed,
    requested_bias=None,
):
    """숨은공간 가중 + 키워드(하이브리드) 가중 + 랜덤 소량."""
    # 키워드 → 태그 분배비율
    target_weights = None
    if keyword:
        for kw, mapping in KEYWORD_TO_TAG_MAP.items():
            if kw in str(keyword):
                target_weights = mapping  # 예: {"느좋":0.6, "핫플":0.4}
                break

    rnd = random.Random(str(seed)) if seed is not None else None
    scored = []

    for place in places_all or []:
        pid = _to_id(place)
        if not pid:
            continue

        score = 0.0

        # 1) 숨은 공간 가중
        if pid in low20_ids:
            score += WEIGHTS["W_band"]
            place["band_label"] = "숨은(20%)"
        elif pid in low50_ids:
            score += WEIGHTS["W_band"] * 0.5
            place["band_label"] = "숨은(50%)"
        else:
            place["band_label"] = "일반"

        # 2) 키워드/대분류 가중 (요청 바이어스 + 하이브리드 분배)
        tags = place.get("tags", [])

        if requested_bias in ("느좋", "핫플") and requested_bias in tags:
            score += WEIGHTS["W_kw"] * 0.9

        if target_weights:
            for tag, frac in target_weights.items():
                if tag in tags:
                    score += WEIGHTS["W_kw"] * float(frac)

        # 3) 거리 가중 (TODO user_loc 활용)

        # 4) 랜덤성
        if rnd:
            score += rnd.random() * WEIGHTS["W_rand"]

        place["final_score"] = score
        scored.append(place)

    scored.sort(key=lambda x: x["final_score"], reverse=True)
    return scored
