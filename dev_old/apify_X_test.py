import os
from apify_client import ApifyClient
from config import APIFY_API_KEY

# Apifyクライアント初期化
client = ApifyClient(APIFY_API_KEY)

# -----------------------------------------------
# Actor入力パラメータの設定
# 公式スキーマ参照: https://apify.com/altimis/scweet/api
# Scweet Twitter/X Scraper
# -----------------------------------------------
run_input = {
    # フレーズ検索: "小松海佑" を完全一致で検索（配列で指定）
    "exact_phrases": ['"小松海佑"'],

    # 取得件数の上限 ※ "maxItems" ではなく "max_items"
    "max_items": 100,

    # ツイートの並び順 ※ "display_type" ではなく "search_sort"
    "search_sort": "Latest",
}

# -----------------------------------------------
# Actor実行（完了まで待機）
# -----------------------------------------------
print("▶ Actor実行中: altimis/scweet")
print(f"  検索クエリ: \"{run_input['exact_phrases'][0]}\"")
print(f"  取得件数上限: {run_input['max_items']}件\n")

run = client.actor("altimis/scweet").call(run_input=run_input)

print(f"✅ Actor実行完了")
print(f"   Dataset ID: {run['defaultDatasetId']}\n")

# -----------------------------------------------
# DatasetからTweet一覧を取得して表示
# -----------------------------------------------
items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

print("=" * 60)
print("📋 検索結果")
print("=" * 60)

if not items:
    print("⚠️ 結果が0件でした。")
else:
    print(f"取得件数: {len(items)}件\n")
    for i, tweet in enumerate(items, start=1):
        created_at = tweet.get("created_at") or tweet.get("Timestamp") or "不明"
        username   = tweet.get("author_username") or tweet.get("Username") or tweet.get("username") or "不明"
        content    = tweet.get("text") or tweet.get("Tweet") or tweet.get("full_text") or "不明"
        tweet_url  = tweet.get("url") or tweet.get("Url") or tweet.get("tweet_url") or "不明"

        print(f"【{i}件目】")
        print(f"  投稿日時  : {created_at}")
        print(f"  ユーザー名: @{username}")
        print(f"  内容      : {content}")
        print(f"  URL       : {tweet_url}")
        print("-" * 60)

# 結果を同一フォルダへtxt保存
output_path = os.path.join(os.path.dirname(__file__), "scweet_results.txt")
with open(output_path, "w", encoding="utf-8") as f:
    if not items:
        f.write("⚠️ 結果が0件でした。\n")
    else:
        f.write(f"取得件数: {len(items)}件\n\n")
        for i, tweet in enumerate(items, start=1):
            created_at = tweet.get("created_at") or tweet.get("Timestamp") or "不明"
            username   = tweet.get("author_username") or tweet.get("Username") or tweet.get("username") or "不明"
            content    = tweet.get("text") or tweet.get("Tweet") or tweet.get("full_text") or "不明"
            tweet_url  = tweet.get("url") or tweet.get("Url") or tweet.get("tweet_url") or "不明"

            f.write(f"【{i}件目】\n")
            f.write(f"  投稿日時  : {created_at}\n")
            f.write(f"  ユーザー名: @{username}\n")
            f.write(f"  内容      : {content}\n")
            f.write(f"  URL       : {tweet_url}\n")
            f.write("-" * 60 + "\n")

print(f"✅ 保存完了: {output_path}")

# デバッグ用: 1件目のrawデータを確認したい場合はコメントアウトを外す
# if items:
#     import json
#     print("\n[DEBUG] 1件目のrawデータ:")
#     print(json.dumps(items[0], ensure_ascii=False, indent=2))