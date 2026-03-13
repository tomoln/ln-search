import requests
import json
from config import SERPER_API_KEY

url = "https://google.serper.dev/search"

payload = {
    "q": "天気　東京　リアルタイム"
}

headers = {
    "X-API-KEY": SERPER_API_KEY,
    "Content-Type": "application/json"
}

response = requests.post(url, headers=headers, json=payload)

data = response.json()

print(json.dumps(data, indent=2, ensure_ascii=False))