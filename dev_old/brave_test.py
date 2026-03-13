import requests
from config import BRAVE_SEARCH_API_KEY

def brave_search(query: str, count: int = 5) -> None:
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": BRAVE_SEARCH_API_KEY,
    }
    params = {
        "q": query,
        "count": count,
    }

    response = requests.get(url, headers=headers, params=params)

    # デバッグ用：ステータスコードとレスポンス内容を表示
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
    print(f"API Key (先頭10文字): {BRAVE_SEARCH_API_KEY[:10]}...")

    response.raise_for_status()

    data = response.json()
    results = data.get("web", {}).get("results", [])
    print(f"\n検索ワード: {query}")
    print(f"上位{len(results)}件の結果:\n")

    for i, result in enumerate(results, 1):
        print(f"[{i}] {result.get('title')}")
        print(f"    URL: {result.get('url')}")
        print(f"    概要: {result.get('description', 'なし')}")
        print()


if __name__ == "__main__":
    brave_search("新宿 温度 本日")