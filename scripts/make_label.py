# github ラベルを一括作成するスクリプト
# 使うときは、config.pyと階層を合わせて、ACCESS_TOKENとREPO_NAMEを設定してください。

from github import Github
from github.GithubException import GithubException
from config import ACCESS_TOKEN, REPO_NAME

# 作成したいラベル一覧
LABELS = [
    "1.2 設計書の確認と調整",
    "2.1 モジュール構成の雛形作成",
    "2.2 モデルアダプターの実装（1つだけ）",
    "2.3 オーケストレーターの初期実装",
    "3.1 モデルアダプターの追加",
    "3.2 検証ロジックの実装",
    "3.3 対話の繰り返し処理",
    "4.1 検索アダプターの実装",
    "4.2 検索とLLMの組み合わせ",
    "5.1 ストレージマネージャーの実装",
    "5.2 設定ファイルの導入",
    "5.3 ログと使用状況の記録",
    "6.1 テストケースの作成",
    "6.2 実行ログの分析",
    "6.3 コスト試算",
    "7.1 モデルの追加",
    "7.2 UIの検討（任意）",
    "7.3 自動化・スケジューリング（任意）",
]

# デフォルトカラー（薄いブルー）
DEFAULT_COLOR = "1f77b4"

def main():
    # GitHubに接続
    g = Github(ACCESS_TOKEN)
    repo = g.get_repo(REPO_NAME)

    # 既存ラベル取得
    existing_labels = {label.name for label in repo.get_labels()}

    for label_name in LABELS:
        if label_name in existing_labels:
            print(f"既に存在: {label_name}")
            continue

        try:
            repo.create_label(
                name=label_name,
                color=DEFAULT_COLOR,
                description="プロジェクト進行タスク"
            )
            print(f"作成完了: {label_name}")
        except GithubException as e:
            print(f"エラー: {label_name} -> {e}")

if __name__ == "__main__":
    main()