"""
Bluesky AT Protocol を使用して
フレーズ一致検索で最新ポスト10件を取得するスクリプト
"""

from atproto import Client
from datetime import datetime
from config import BLUESKY_ID, BLUESKY_PASSWORD  # ここから読み込む

# -----------------------------
# 検索ワード（フレーズ完全一致）
# -----------------------------
QUERY = '"ダダルズ"'

# 取得件数
LIMIT = 10

# -----------------------------
# Client作成
# -----------------------------
client = Client(base_url="https://bsky.social")

# Blueskyにログイン
client.login(BLUESKY_ID, BLUESKY_PASSWORD)

# -----------------------------
# 投稿検索
# -----------------------------
response = client.app.bsky.feed.search_posts(
    params={
        "q": QUERY,
        "limit": LIMIT
    }
)

# -----------------------------
# 結果表示
# -----------------------------
for post in response.posts:
    # 投稿日時
    created_at = post.record.created_at
    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

    # 投稿者
    handle = post.author.handle

    # 投稿本文
    text = post.record.text

    # URI例
    # at://did:xxx/app.bsky.feed.post/3kxxxxx
    uri = post.uri

    # post_id抽出
    post_id = uri.split("/")[-1]

    # 投稿URL生成
    post_url = f"https://bsky.app/profile/{handle}/post/{post_id}"

    print(dt)
    print(f"@{handle}")
    print(text)
    print(post_url)
    print("-" * 40)