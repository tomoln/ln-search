"""
Reddit 最新投稿取得スクリプト
Apify の無料プランで利用可能な Actor を使用
"""

from apify_client import ApifyClient
from config import APIFY_API_KEY
import json
from datetime import datetime


def search_reddit_posts(
    query: str,
    limit: int = 10,
    sort: str = "new",
) -> list[dict]:
    """
    Reddit を検索して最新投稿を取得する

    Args:
        query:  検索ワード (例: "yuyushiki")
        limit:  取得件数 (デフォルト: 10)
        sort:   ソート順 ("new" | "hot" | "top" | "relevance")

    Returns:
        投稿情報の dict リスト
    """
    client = ApifyClient(APIFY_API_KEY)

    # Apify 無料プランで利用可能な Reddit Scraper Actor
    # Actor ID: trudax/reddit-scraper-lite  (無料・軽量版)
    actor_id = "trudax/reddit-scraper-lite"

    run_input = {
        "searches": [query],
        "type": "posts",          # "posts" or "comments"
        "sort": sort,             # new / hot / top / relevance
        "time": "all",            # hour / day / week / month / year / all
        "maxItems": limit,
        "proxy": {
            "useApifyProxy": True,
            "apifyProxyGroups": ["RESIDENTIAL"],
        },
    }

    print(f"[INFO] 検索ワード : {query!r}")
    print(f"[INFO] 取得件数   : {limit} 件")
    print(f"[INFO] ソート順   : {sort}")
    print(f"[INFO] Actor を実行中 ...")

    # Actor を実行し、終了まで待機
    run = client.actor(actor_id).call(run_input=run_input)

    # データセットから結果を取得
    results = []
    dataset_items = client.dataset(run["defaultDatasetId"]).iterate_items()

    for item in dataset_items:
        post = _normalize_post(item)
        results.append(post)
        if len(results) >= limit:
            break

    print(f"[INFO] 取得完了: {len(results)} 件\n")
    return results


def _normalize_post(raw: dict) -> dict:
    """Actor の出力を統一フォーマットに変換"""

    # UNIX タイムスタンプ → 人間が読める形式
    created_utc = raw.get("createdAt") or raw.get("created_utc")
    if isinstance(created_utc, (int, float)):
        created_str = datetime.utcfromtimestamp(created_utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    else:
        created_str = str(created_utc) if created_utc else "N/A"

    # Reddit の permalink から完全 URL を生成
    permalink = raw.get("permalink", "")
    if permalink and not permalink.startswith("http"):
        url = f"https://www.reddit.com{permalink}"
    else:
        url = permalink or raw.get("url", "N/A")

    return {
        "title":       raw.get("title", "N/A"),
        "url":         url,
        "created_at":  created_str,
        "subreddit":   raw.get("subreddit") or raw.get("communityName", "N/A"),
        "author":      raw.get("author") or raw.get("username", "N/A"),
        "score":       raw.get("score", 0),
        "num_comments":raw.get("numComments") or raw.get("num_comments", 0),
        "selftext":    (raw.get("selftext") or raw.get("text") or "")[:300],  # 先頭300文字
        "id":          raw.get("id", "N/A"),
    }


def print_posts(posts: list[dict]) -> None:
    """投稿一覧を見やすく表示"""
    for i, post in enumerate(posts, 1):
        print(f"{'='*60}")
        print(f"[{i}] {post['title']}")
        print(f"  サブレディット : r/{post['subreddit']}")
        print(f"  投稿者        : u/{post['author']}")
        print(f"  投稿日時      : {post['created_at']}")
        print(f"  スコア        : {post['score']}  コメント数: {post['num_comments']}")
        print(f"  URL           : {post['url']}")
        if post["selftext"]:
            print(f"  本文 (抜粋)   : {post['selftext']} ...")
    print(f"{'='*60}")


if __name__ == "__main__":
    # ---- 設定 ----
    SEARCH_QUERY = "yuyushiki"
    LIMIT        = 10
    SORT         = "new"          # 最新順
    OUTPUT_JSON  = "results.json"
    # --------------

    posts = search_reddit_posts(query=SEARCH_QUERY, limit=LIMIT, sort=SORT)

    # コンソール表示
    print_posts(posts)

    # JSON ファイルに保存
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)
    print(f"\n[INFO] 結果を {OUTPUT_JSON!r} に保存しました。")