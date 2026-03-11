import requests
from bs4 import BeautifulSoup
import urllib.parse

# ======================================
# 1. 検索キーワードを設定（フレーズ検索）
# ======================================
keyword = '"小松海佑"'


# ======================================
# 2. Nitterの検索URLを作成
#   ・urllib.parse.quoteでURLエンコード
#   ・sort=latest で最新順
# ======================================
encoded_keyword = urllib.parse.quote(keyword)
url = f"https://nitter.net/search?f=tweets&q={encoded_keyword}&since=&until=&near="


# ======================================
# 3. Webページを取得
# ======================================
headers = {
    "User-Agent": "Mozilla/5.0"
}

response = requests.get(url, headers=headers)
response.raise_for_status()


# ======================================
# 4. HTMLを解析
# ======================================
soup = BeautifulSoup(response.text, "html.parser")


# ======================================
# 5. ツイート本文を取得
#   Nitterでは tweet-content クラス
# ======================================
tweets = soup.find_all("div", class_="tweet-content")


# ======================================
# 6. 最新10件を取得して表示
# ======================================
print("検索結果（最新10件）\n")

for i, tweet in enumerate(tweets[:10], start=1):
    text = tweet.get_text(strip=True)
    
    print(f"{i}. {text}")
    print("-" * 60)