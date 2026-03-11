import config
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

def summarize_nitter_posts(
    keyword: str,
    max_posts: int = 30,
    nitter_base_url: str = "https://nitter.net"
) -> None:
    """
    Nitter検索結果から投稿を取得し、OpenAIで要約して表示する
    """

    # 1. 検索ワードの設定
    search_query = keyword.strip()
    if not search_query:
        raise ValueError("検索ワードを指定してください")

    # 2. Nitterの検索URL作成
    # Nitterは /search?q=keyword のようなURLを使う（URLエンコード済み）
    search_url = f"{nitter_base_url}/search?f=tweets&q={requests.utils.quote(search_query)}"

    # 3. Nitterページの取得
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ln-search-bot/1.0; +https://example.com)"
    }
    resp = requests.get(search_url, headers=headers, timeout=10)
    resp.raise_for_status()
    html = resp.text

    # 4. HTMLからポスト本文の抽出
    soup = BeautifulSoup(html, "html.parser")
    tweet_blocks = soup.select("div.timeline-item")
    tweets = []
    for block in tweet_blocks:
        content = block.select_one("div.tweet-content")
        if content:
            text = content.get_text(separator=" ", strip=True)
            if text:
                tweets.append(text)

    # 5. 指定件数まで取得
    tweets = tweets[:max_posts]

    if not tweets:
        print("投稿が見つかりませんでした。検索ワードを確認してください。")
        return

    # 6. 取得したポストをまとめる
    joined_text = "\n\n".join(f"{i+1}. {t}" for i, t in enumerate(tweets))

    # 7. OpenAI APIに送信
    client = OpenAI(api_key=config.OPENAI_API_KEY)

    prompt = (
        "以下はNitterから取得したツイート本文です。日本語で簡潔に要約してください。\n\n"
        f"{joined_text}\n\n"
        "要約:"
    )
    response = client.responses.create(
        model="gpt-4.1-mini",  # 利用可能なモデル名に合わせて調整
        input=prompt,
        max_tokens=350,
        temperature=0.3,
    )

    # 8. 要約結果を出力
    summary_text = ""
    if isinstance(response.output, list):
        summary_text = "\n".join(
            part.get("content", "") for part in response.output if part.get("content")
        )
    elif isinstance(response.output, dict):
        summary_text = response.output.get("text", "")
    else:
        summary_text = str(response)

    print("=== 要約結果 ===")
    print(summary_text.strip())


if __name__ == "__main__":
    # 実行例
    keyword = '"小松海佑"'
    max_posts = 30
    summarize_nitter_posts(keyword=keyword, max_posts=max_posts)