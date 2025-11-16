# AiChatbot/app.py
import os
import json
import math
from flask import Flask, request, Response, render_template
from recommender.recommend_service import recommend_places, health_status
from recommender.reask import suggest_alternatives, parse_user_text

app = Flask(__name__)

# ───────────────────────── JSON NaN/Infinity 정규화 ─────────────────────────
def _sanitize_json(obj):
    """dict/list 깊은 곳까지 NaN/Infinity를 None으로 치환"""
    if isinstance(obj, dict):
        return {k: _sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_json(x) for x in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
    return obj

def json_response(data, status=200, mimetype="application/json"):
    """Flask jsonify 대체: NaN/Infinity 제거 + UTF-8"""
    safe = _sanitize_json(data)
    return Response(
        json.dumps(safe, ensure_ascii=False, allow_nan=False),
        status=status,
        mimetype=mimetype,
    )

# ───────────────────────── Minimal UI (HTML은 script 바깥, JS는 script 안) ─────────────────────────
CLEAN_HTML_UI = """
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>Dobong Chatbot</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  :root { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }
  body { margin: 0; background:#fafafa; color:#111; }
  header { padding:14px 16px; font-weight:700; background:#111; color:#fff; }
  #wrap { max-width: 680px; margin: 0 auto; padding: 16px; }
  #chat { background:#fff; border:1px solid #e5e5e1; border-radius:12px; padding:12px; height:60vh; overflow:auto; }
  .row { margin:10px 0; display:flex; gap:8px; }
  .ai, .me { max-width: 85%; padding:10px 12px; border-radius:12px; white-space:pre-wrap; line-height:1.4; }
  .ai { background:#f0f3ff; border:1px solid #dfe6ff; }
  .me { background:#e8fff2; border:1px solid #c9f5dc; margin-left:auto; }
  form { display:flex; gap:8px; margin-top:12px; }
  input[type=text]{ flex:1; padding:12px; border-radius:10px; border:1px solid #d0d0d0; }
  button{ padding:12px 16px; border-radius:10px; border:0; background:#111; color:#fff; cursor:pointer; }
  button:disabled{ opacity:.5; cursor:not-allowed; }
  small{ color:#666 }
  .hint{ margin-top:8px; }
  .pill{ display:inline-block; padding:6px 10px; border-radius:999px; background:#f2f2f2; margin: 4px 4px 0 0; cursor:pointer; }
</style>
</head>
<body>
<header>Dobong Chatbot</header>

<div id="wrap">
  <div id="chat"></div>

  <form id="f">
    <input id="q" type="text" placeholder="키워드를 입력하거나 선택하세요" autocomplete="off">
    <button id="send" type="submit">보내기</button>
  </form>

  <!-- 예시 키워드 (HTML은 script 바깥) -->
  <div class="hint">
    <small>예시 키워드:</small>
    <div>
        <span class="pill">친구</span>
        <span class="pill">연인</span>
        <span class="pill">가족</span>
        <span class="pill">느좋</span>
        <span class="pill">핫플</span>
        <span class="pill">브런치 카페</span>
        <span class="pill">야경 좋은 곳</span>
        <span class="pill">조용한 정원</span>
        <span class="pill">둘레길</span>
    </div>
  </div>
</div>

<script>
const chat = document.getElementById('chat');
const form = document.getElementById('f');
const input = document.getElementById('q');
const btn = document.getElementById('send');

let convState = { state: 'init', keyword: null, offset: 0, lastResults: [] };

/** ▼ 필요 시 직접 채워 넣을 기본 키 (없으면 자동 추출 시도) */
const STATIC_MAPS_KEY = ''; // 예: 'AIzaSy...'

function addMe(text){
  const row = document.createElement('div'); row.className='row';
  const b = document.createElement('div'); b.className='me'; b.textContent = text;
  row.appendChild(b); chat.appendChild(row); chat.scrollTop = chat.scrollHeight;
}
function addAI(text){
  const row = document.createElement('div'); row.className='row';
  const b = document.createElement('div'); b.className='ai'; b.textContent = text;
  row.appendChild(b); chat.appendChild(row); chat.scrollTop = chat.scrollHeight;
}
function addAIHTML(html){
  const row = document.createElement('div'); row.className='row';
  const b = document.createElement('div'); b.className='ai'; b.innerHTML = html;
  row.appendChild(b); chat.appendChild(row); chat.scrollTop = chat.scrollHeight;
}
function esc(s){
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function escURL(u){
  try { return encodeURI(u); } catch(e){ return '#'; }
}

/** imageUrl에 포함된 Google key= 파라미터를 뽑아내기 */
function extractKeyFromUrl(url){
  try {
    const u = new URL(url);
    const k = u.searchParams.get('key');
    return k || '';
  } catch(e){ return ''; }
}

/** 주변 결과들에서 key를 한 번 더 시도 추출 */
function findAnyImageKeyFromState(){
  for (const p of convState.lastResults || []) {
    const iu = p?.imageUrl || p?.imageURL || p?.photoUrl;
    if (iu) {
      const k = extractKeyFromUrl(iu);
      if (k) return k;
    }
  }
  return '';
}

/** Static Maps URL 만들기: lat/lon 우선, 없으면 placeId */
function buildStaticMapUrl(place){
  const lat = place.lat ?? place.latitude;
  const lon = place.lon ?? place.longitude;
  const placeId = place.placeId || place.place_id;

  // 사용할 API 키 결정: 1) place.imageUrl에서 추출 2) convState에서 추출 3) 상수
  const keyFromImageUrl =
    extractKeyFromUrl(place.imageUrl || place.imageURL || place.photoUrl || '') ||
    findAnyImageKeyFromState() ||
    STATIC_MAPS_KEY;

  if (!keyFromImageUrl) return ''; // 키 없으면 생성하지 않음

  const base = 'https://maps.googleapis.com/maps/api/staticmap';
  const params = new URLSearchParams();
  params.set('size', '720x480');     // 필요시 조정
  params.set('scale', '2');          // 레티나 품질
  params.set('zoom', '16');
  params.set('key', keyFromImageUrl);

  if (lat && lon) {
    params.set('center', `${lat},${lon}`);
    params.append('markers', `${lat},${lon}`);
  } else if (placeId) {
    params.set('center', `place_id:${placeId}`);
    params.append('markers', `place_id:${placeId}`);
  } else {
    return ''; // 위치 정보 없으면 생성 불가
  }

  return `${base}?${params.toString()}`;
}

function showDetails(place) {
  if (!place) return;

  const name = place.name || '';
  const address = place.address || '';
  const imageUrl = place.imageUrl || place.imageURL || place.photoUrl || '';
  const mapsUrl = place.mapsUrl || place.mapUrl || '';
  const sub = place.sub_category || ''; // "분류없음" 같은 디폴트 텍스트는 숨김
  const tags = (place.tags && place.tags.length) ? place.tags.join(', ') : '';

  // 이미지: 1) imageUrl 있으면 그걸 표시  2) 없으면 Static Maps 이미지 시도
  let visualUrl = '';
  if (imageUrl) {
    visualUrl = imageUrl;
  } else {
    visualUrl = buildStaticMapUrl(place); // 키/좌표가 있어야 생성됨
  }
  const imgBlock = visualUrl
    ? `<div style="margin:8px 0 10px">
         <a href="${escURL(visualUrl)}" target="_blank" rel="noopener">
           <img src="${escURL(visualUrl)}" alt="${esc(name)||'이미지'}" style="max-width:100%;border-radius:8px"/>
         </a>
       </div>`
    : '';

  // 메타 필드 나열 (불필요 키 제외 & 값 없으면 숨김)
  const metaLines = [];
  const lat = place.lat ?? place.latitude;
  const lon = place.lon ?? place.longitude;

  for (const key in place) {
    if (['name','sub_category','address','tags','lat','lon','latitude','longitude','id','band_label','final_score','imageUrl','imageURL','photoUrl','mapsUrl','mapUrl','placeId','place_id'].includes(key)) continue;
    const v = place[key];
    if (v !== null && v !== undefined && v !== '') {
      metaLines.push(`· ${esc(key)}: ${esc(v)}`);
    }
  }
  if (lat && lon) {
    metaLines.push(`· 좌표: ${lat}, ${lon}`);
  }

  // 지도 링크(있으면 표시)
  const mapLink = mapsUrl ? `<a href="${escURL(mapsUrl)}" target="_blank" rel="noopener">지도 열기</a>` : '';

  // 본문 구성: 불필요한 “분류없음/없음” 같은 텍스트는 숨김
  const lines = [
    `[상세 정보: ${esc(name || '이름없음')}]`,
  ];
  if (sub) lines.push(`· 분류: ${esc(sub)}`);
  if (address) lines.push(`· 주소: ${esc(address)}`);
  if (tags) lines.push(`· 태그: ${esc(tags)}`);
  if (metaLines.length) lines.push(...metaLines);
  if (mapLink) lines.push(`· ${mapLink}`);

  addAIHTML([lines.join('<br>'), imgBlock].join(''));
}

async function callChatbotAPI(text, offset = 0){
  btn.disabled = true;
  try{
    const res = await fetch('/api/chatbot', {
      method:'POST',
      headers:{'Content-Type':'application/json', 'Accept':'application/json'},
      body: JSON.stringify({ text, k: 5, offset })
    });

    const ct = (res.headers.get('content-type') || '').toLowerCase();
    const payload = ct.includes('application/json')
      ? await res.json()
      : { status:'error', message: await res.text() };

    if (!res.ok && payload.status !== 'success') {
      addAI('오류: ' + (payload.detail || payload.message || '알 수 없는 오류'));
      convState.state = 'init';
      return;
    }
    if (payload.status === 'error') {
      addAI('오류: ' + (payload.detail || payload.message || '알 수 없는 오류'));
      convState.state = 'init';
      return;
    }

    if(payload.message){
      addAI(payload.message);
      convState.lastResults = payload.results || [];
      if (convState.lastResults.length > 0) {
        addAI("원하시는 장소가 없다면 '다시 추천'을 입력해주세요.\\n자세히 보고 싶다면 '번호(1~5)'를 입력해주세요.");
        convState.state = 'awaiting_followup';
        convState.keyword = text;
        convState.offset = offset;
      } else {
        if (offset > 0) addAI("더 이상 추천할 장소가 없습니다. 새로운 키워드로 검색해주세요.");
        convState.state = 'init'; convState.offset = 0; convState.lastResults = [];
      }
    } else {
      addAI('응답이 비어있어요.');
      convState.state = 'init';
    }
  } catch(e) {
    addAI('오류: ' + e);
    convState.state = 'init';
  } finally {
    btn.disabled = false;
  }
}

form.addEventListener('submit', (e)=>{
  e.preventDefault();
  const text = input.value.trim();
  if(!text) return;
  addMe(text); input.value = '';
  if (convState.state === 'awaiting_followup') {
    const num = parseInt(text);
    if (text.includes('추천')) {
        addAI("네, 다음 장소(Top 6-10)를 추천해드릴게요.");
        const nextOffset = convState.offset + 5;
        callChatbotAPI(convState.keyword, nextOffset);
    } else if (!Number.isNaN(num) && num >= 1 && num <= convState.lastResults.length) {
        const place = convState.lastResults[num - 1];
        showDetails(place);
        addAI("원하시는 장소가 없다면 '다시 추천'을 입력해주세요.\\n다른 키워드로 검색하셔도 좋습니다.");
    } else {
        convState.state = 'init'; convState.offset = 0;
        callChatbotAPI(text, 0);
    }
  } else {
    convState.state = 'init'; convState.offset = 0;
    callChatbotAPI(text, 0);
  }
});

document.querySelectorAll('.pill').forEach(p=>{
  p.addEventListener('click', ()=>{
    input.value = p.textContent;
    form.dispatchEvent(new Event('submit'));
  });
});

addAI("안녕하세요! 누구와 함께할 장소를 찾으시나요? (예: 친구, 연인, 가족)\\n다른 키워드(예: 브런치 카페)도 좋습니다.");
</script>
</body>
</html>
"""

# ───────────────────────── Routes ─────────────────────────
@app.get("/")
def index():
    return render_template("chat.html")  # templates/chat.html

@app.get("/chat")
def chat_ui():
    return render_template("chat.html")  # 동일 템플릿 재사용

@app.get("/favicon.ico")
def favicon():
    # 404 로그 없애기
    return Response(status=204)

@app.get("/api/health")
def api_health():
    return json_response({"ok": True, "data": health_status()})

@app.post("/api/dobong/recommend")
def api_recommend():
    try:
        body = request.get_json(force=True, silent=True) or {}
        category = body.get("category")            # '느좋' | '숨은핫플' (있으면 사용, 없어도 됨)
        keyword  = body.get("keyword")
        k        = int(body.get("k", 5))
        seed     = body.get("seed")
        offset   = int(body.get("offset", 0))
        user     = body.get("user_location")

        user_loc = None
        if isinstance(user, dict) and "lat" in user and "lon" in user:
            try:
                user_loc = (float(user["lat"]), float(user["lon"]))
            except Exception:
                user_loc = None

        results = recommend_places(category, keyword, user_loc, k, seed, offset)
        explain = f"k={k}, offset={offset} 적용. 20% 우선 → 50% → 전체 순으로 추천."

        payload = {"status":"success","count":len(results),"results":results,"explain":explain}
        if len(results) < max(1, k // 2) and offset == 0:
            payload["reask"] = suggest_alternatives(category, keyword)

        return json_response(payload, status=200)
    except Exception as e:
        return json_response({"status":"error","message":"서버 내부 오류","detail":str(e)}, status=500)

@app.post("/api/chatbot")
def api_chatbot():
    try:
        body = request.get_json(force=True, silent=True) or {}
        user_text = body.get("text", "")
        k         = int(body.get("k", 5))
        seed      = body.get("seed")
        offset    = int(body.get("offset", 0))

        parsed = parse_user_text(user_text)
        category = parsed.get("category") or body.get("category")
        keyword  = parsed.get("keyword")  or body.get("keyword")
        user_loc = parsed.get("user_location")

        # 기본 카테고리 추론
        if category not in ("느좋","숨은핫플"):
            if keyword and any(kw in (keyword or "") for kw in ["친구","연인","핫플","카페","맛집"]):
                category = "숨은핫플"
            else:
                category = "느좋"

        results = recommend_places(category, keyword, user_loc, k, seed, offset)

        if results:
            lines = []
            final_category_text = "숨은핫플" if category == "숨은핫플" else "느좋"
            if offset == 0:
                lines.append(f"요청: {final_category_text} / 키워드: {keyword or '없음'} (Top 1-5)")
            else:
                lines.append(f"요청: {final_category_text} / 키워드: {keyword or '없음'} (Top {offset+1}-{offset+k})")

            for i, r in enumerate(results, 1):
                name = r.get("name") or r.get("id") or "이름없음"
                lines.append(f"{i}. {name}")

            summary = "\n".join(lines)
        else:
            if offset > 0:
                summary = "더 이상 추천할 장소가 없습니다. 다른 키워드를 입력해보세요."
            else:
                alt = suggest_alternatives(category, keyword)
                summary = f"해당 조건에서는 추천이 적습니다. 대신 이런 키워드는 어때요? {', '.join(alt.get('alt_keywords', []))}"

        return json_response({
            "status":"success",
            "parsed": parsed,
            "k": k,
            "offset": offset,
            "results": results,
            "message": summary
        }, status=200)
    except Exception as e:
        # 항상 JSON으로 에러 반환
        return json_response({
            "status":"error",
            "message":"서버 내부 오류",
            "detail": str(e)
        }, status=500)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(debug=True, port=port, threaded=True)
