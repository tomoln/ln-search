# github上にマイルストーンを作成するスクリプト
# 使うときは、config.pyと階層を合わせて、ACCESS_TOKENとREPO_NAMEを設定してください。

from github import Github
from config import ACCESS_TOKEN, REPO_NAME


# 作成したいマイルストーンの一覧
milestones = [
    "最小構成の実装（MVP）",
    "対話ロジックの拡張",
    "検索エンジン連携",
    "保存・ログ・設定管理",
    "テストと改善",
    "運用と拡張"
]

# 認証してリポジトリにアクセス
g = Github(ACCESS_TOKEN)
repo = g.get_repo(REPO_NAME)

# マイルストーンを作成
for title in milestones:
    repo.create_milestone(title=title)
    print(f"マイルストーン「{title}」を作成しました。")
