import time
import requests
import trafilatura
from config import BRAVE_SEARCH_API_KEY, GEMINI_API_KEY

# -----------------------------
# 設定
# -----------------------------
query = "新宿 本日 天気"
num_results = 5
score_threshold = 0.7

# -----------------------------
# Brave Search API
# -----------------------------
brave_url = "https://api.search.brave.com/res/v1/web/search"
brave_headers = {
    "Accept": "application/json",
    "X-Subscription-Token": BRAVE_SEARCH_API_KEY
}
params = {"q": query, "count": num_results}

response = requests.get(brave_url, headers=brave_headers, params=params)
data = response.json()

# -----------------------------
# 1. URLとスニペット取得
# -----------------------------
results = []
with open("001_Brave_URL.txt", "w", encoding="utf-8") as f:
    for item in data.get("web", {}).get("results", []):
        url = item.get("url", "")
        snippet = item.get("description", "") or item.get("snippet", "")
        if url:
            results.append({"url": url, "snippet": snippet})
            f.write(f"{url}\t{snippet}\n")

print("URLとスニペット保存完了")

# -----------------------------
# Gemini API呼び出し関数
# -----------------------------
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

def call_gemini(prompt: str) -> str:
    resp = requests.post(
        GEMINI_URL,
        headers={"Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}]
        },
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

# -----------------------------
# 2. Geminiでスコア化（スニペット）
# -----------------------------
scored_results = []

with open("002_score.txt", "w", encoding="utf-8") as f:
    for r in results:
        prompt = f"検索クエリ: {query}\nスニペット: {r['snippet']}\nこのページは必要か？0から1の数値のみ返してください（例: 0.8）"
        try:
            score_text = call_gemini(prompt)
            score = float(score_text.strip())
        except Exception as e:
            print(f"スコア取得失敗: {e}, デフォルト0.5を使用")
            score = 0.5
        r["score"] = score
        f.write(f"{r['url']}\t{r['snippet']}\t{score}\n")
        if score >= score_threshold:
            scored_results.append(r)
        time.sleep(3)  # レート制限対策

print("スコア化完了")

# -----------------------------
# 3. スコア上位ページのみスクレイピング
# -----------------------------
html_list = []
for r in scored_results:
    try:
        req = requests.get(r["url"], timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        html = req.text
        html_list.append({"url": r["url"], "html": html})
    except Exception as e:
        print("取得失敗:", r["url"], e)

with open("003_request.txt", "w", encoding="utf-8") as f:
    for h in html_list:
        f.write(f"{h['url']}\n")
        f.write(h["html"])
        f.write("\n\n\n-----PAGE-END-----\n\n\n")

print("HTML保存完了")

# -----------------------------
# 4. 本文抽出
# -----------------------------
main_texts = []
with open("004_main.txt", "w", encoding="utf-8") as f:
    for h in html_list:
        text = trafilatura.extract(h["html"])
        if text:
            main_texts.append({"url": h["url"], "text": text})
            f.write(f"{h['url']}\n{text}\n\n\n-----ARTICLE-END-----\n\n\n")

print("本文抽出完了")

# -----------------------------
# 5. 本文要約（Gemini）
# -----------------------------
summaries = []
for mt in main_texts:
    prompt = f"以下の記事を日本語で要約してください:\n{mt['text']}\n---要約---"
    try:
        summary = call_gemini(prompt)
    except Exception as e:
        print(f"要約失敗: {e}")
        summary = "要約失敗"
    summaries.append({"url": mt["url"], "summary": summary})

with open("005_summary.txt", "w", encoding="utf-8") as f:
    for s in summaries:
        f.write(f"{s['url']}\n{s['summary']}\n\n\n")

print("要約完了")
