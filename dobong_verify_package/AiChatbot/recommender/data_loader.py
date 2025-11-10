# AiChatbot/recommender/data_loader.py
import os, json

def _extract_list(obj):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for k in ("data", "results", "items", "places", "list"):
            v = obj.get(k)
            if isinstance(v, list):
                return v
        feats = obj.get("features")
        if isinstance(feats, list):
            return feats
    return []

def _to_place_dict_list(lst):
    out = []
    for x in lst or []:
        if isinstance(x, dict):
            name = x.get("name") or x.get("title") or x.get("place_name") or x.get("id")
            rec = dict(x)
            if name: rec["name"] = name
            if "tags" not in rec or rec["tags"] is None: rec["tags"] = []
            out.append(rec)
        else:
            sx = str(x)
            out.append({"id": sx, "name": sx, "tags": []})
    return out

def _as_id_list(lst):
    out = []
    for x in lst or []:
        if isinstance(x, dict):
            pid = x.get("id") or x.get("placeId") or x.get("place_id") or x.get("name")
            if pid: out.append(str(pid))
        else:
            out.append(str(x))
    return out

def _load_json(base_path, filename):
    path = os.path.join(base_path, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        if filename.endswith(".geojson"):
            return {"type":"FeatureCollection","features":[]}
        return []
    except Exception:
        if filename.endswith(".geojson"):
            return {"type":"FeatureCollection","features":[]}
        return []

def _ensure_tag(lst, tag):
    """각 레코드에 출처 태그(핫플/느좋)를 주입하고 main_category로도 보관"""
    for p in lst:
        tags = p.get("tags") or []
        if not isinstance(tags, list):
            tags = [str(tags)]
        if tag not in tags:
            tags.append(tag)
        p["tags"] = tags
        p.setdefault("main_category", tag)

def _bootstrap_data():
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.dirname(current_dir)
        base_path = os.path.join(base_dir, "tests")
        if not os.path.isdir(base_path):
            base_path = "tests"
    except Exception:
        base_path = "tests"

    raw_neu_all = _load_json(base_path, "dobong_neujoh.json")
    raw_hot_all = _load_json(base_path, "dobong_hotple.json")
    raw_neu_low = _load_json(base_path, "dobong_neujoh_in_low.json")
    raw_hot_low = _load_json(base_path, "dobong_hotple_in_low.json")

    neujoh_all = _to_place_dict_list(_extract_list(raw_neu_all))
    hotple_all = _to_place_dict_list(_extract_list(raw_hot_all))

    # ★ 출처 태그 주입 (핵심)
    _ensure_tag(neujoh_all, "느좋")
    _ensure_tag(hotple_all, "핫플")

    neujoh_low = _as_id_list(_extract_list(raw_neu_low))
    hotple_low = _as_id_list(_extract_list(raw_hot_low))

    return {
        "느좋": neujoh_all,
        "핫플": hotple_all,
        "느좋_low": neujoh_low,
        "핫플_low": hotple_low,
    }

_ALL_DATA = _bootstrap_data()

def get_all_data():
    return _ALL_DATA
