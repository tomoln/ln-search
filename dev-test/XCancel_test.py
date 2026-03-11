import requests
from bs4 import BeautifulSoup
import urllib.parse
import time

# ======================================
# 1. 検索キーワード（フレーズ検索）
# ======================================
keyword = '"小松海佑"'


# ======================================
# 2. URLエンコード
# ======================================
encoded_keyword = urllib.parse.quote(keyword)

url = f"https://xcancel.com/search?q={encoded_keyword}&f=live"


# ======================================
# 3. ヘッダー（Bot対策）
# ======================================
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8"
}


# ======================================
# 4. リトライ付きリクエスト
# ======================================
for i in range(3):

    response = requests.get(url, headers=headers, timeout=10)

    if response.status_code == 200:
        break

    print(f"Retry {i+1} : status={response.status_code}")
    time.sleep(3)

else:
    raise Exception("xcancel access failed")


# ======================================
# 5. HTML解析
# ======================================
soup = BeautifulSoup(response.text, "html.parser")


# ======================================
# 6. ポスト取得
# ======================================
tweets = soup.find_all("div", class_="tweet-text")


# ======================================
# 7. 最新10件表示
# ======================================
print("検索結果（最新10件）\n")

for i, tweet in enumerate(tweets[:10], start=1):

    text = tweet.get_text(strip=True)

    print(f"{i}. {text}")
    print("-" * 50)