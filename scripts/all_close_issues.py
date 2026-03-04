from github import Github
from config import ACCESS_TOKEN, REPO_NAME

# GitHub に認証
g = Github(ACCESS_TOKEN)

# リポジトリを取得
repo = g.get_repo(REPO_NAME)

# オープン・クローズ問わず全ての Issue を取得
issues = repo.get_issues(state='all')

# 各 Issue をクローズ
for issue in issues:
    if issue.state != 'closed':
        print(f"Closing issue #{issue.number}: {issue.title}")
        issue.edit(state='closed')
