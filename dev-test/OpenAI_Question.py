import os
from openai import OpenAI
import config

# APIキーを使ってクライアントを作成
client = OpenAI(api_key=config.OPENAI_API_KEY)

# 利用可能なモデル一覧（必要に応じて追加・変更OK）
available_models = {
    "1": "gpt-3.5-turbo",
    "2": "gpt-4",
    "3": "gpt-4-turbo"
    # "4": "gpt-5.2"  # 利用可能になったら追加
}

def ask_ai(prompt, model):
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "あなたは親切なアシスタントです。"},
            {"role": "user", "content": prompt}
        ]
    )
    # レスポンスと消費トークン数を返す
    content = response.choices[0].message.content
    tokens = response.usage.total_tokens if hasattr(response.usage, 'total_tokens') else None
    return content, tokens

if __name__ == "__main__":
    print("使用するモデルを選んでください：")
    for key, model_name in available_models.items():
        print(f"{key}: {model_name}")

    selected_key = ""
    while selected_key not in available_models:
        selected_key = input("番号を入力してください：").strip()

    selected_model = available_models[selected_key]
    print(f"→ {selected_model} を使用します。\n")

    while True:
        user_input = input("質問をどうぞ（終了するには 'exit' と入力）：")
        if user_input.lower() == "exit":
            break
        answer, tokens = ask_ai(user_input, model=selected_model)
        print("AIの答え：", answer)
        if tokens is not None:
            print(f"消費トークン数：{tokens}")
        # トークン残量確認への案内を追加
        print("残りのトークンはこちらで確認\nhttps://platform.openai.com/usage")
