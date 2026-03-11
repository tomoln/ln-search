import requests
from openai import OpenAI
import os
import config

client = OpenAI(api_key=config.OPENAI_API_KEY)
SERPER_API_KEY = config.SERPER_API_KEY

def google_search(query):

    url = "https://google.serper.dev/search"

    payload = {"q": query}

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }

    res = requests.post(url, headers=headers, json=payload)
    data = res.json()

    results = []

    for r in data["organic"][:5]:
        results.append(f"{r['title']} : {r['link']}")

    return "\n".join(results)


def ask_ai(question):

    search_result = google_search(question)

    prompt = f"""
次の検索結果を参考にして質問に答えてください。

検索結果:
{search_result}

質問:
{question}
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content


print(ask_ai("社会人で、演説とかできる人って普段表立ってないのになんであんなに喋れるの？"))