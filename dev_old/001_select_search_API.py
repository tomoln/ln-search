# 検索エンジンの選択
# Brave Search APIとSerper APIの無料枠を確認し、利用可能な方を選択する。
# 1が返れば使えるという判断


import os
import json
import requests

from config import BRAVE_SEARCH_API_KEY, SERPER_API_KEY

RESULT_DIR = "result"
OUTPUT_FILE = os.path.join(RESULT_DIR, "001_select_search_engine.txt")


def check_brave_credits():
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": BRAVE_SEARCH_API_KEY,
    }
    params = {"q": "test", "count": 1}

    try:
        res = requests.get(url, headers=headers, params=params, timeout=5)
        if res.status_code == 200:
            return 1  # 使えると判断
        else:
            return 0
    except Exception as e:
        print(f"Brave API error: {e}")
        return 0




def check_serper_credits():
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": SERPER_API_KEY}
    payload = {"q": "test"}

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=5)
        if res.status_code == 200:
            return 1  # 無料枠が残っていると判断
        else:
            return 0
    except requests.exceptions.Timeout:
        print("Serper API timeout")
        return 0
    except Exception as e:
        print(f"Serper API error: {e}")
        return 0



def select_engine():
    brave = check_brave_credits()
    serper = check_serper_credits()

    # 優先順位：Brave → Serper（任せると言われたのでこの順にした）
    if brave > 0:
        return "BRAVE", brave
    elif serper > 0:
        return "SERPER", serper
    else:
        return "NONE", 0


def save_result(engine, credits):
    os.makedirs(RESULT_DIR, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"ENGINE={engine}\n")
        f.write(f"CREDITS={credits}\n")

    print(f"Saved: {OUTPUT_FILE}")


def main():
    engine, credits = select_engine()
    save_result(engine, credits)


if __name__ == "__main__":
    main()
