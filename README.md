
# GPUser

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

GPUサーバーの利用状況を確認するためのWebアプリケーションです。
このリポジトリでは、バックエンドのAPIサーバーを提供します。

## 使用技術

- Python 3.12
- Flask

その他のライブラリについては、requirements.txtを参照してください。

## 初期設定

### 1. リポジトリをクローン

```bash
git clone git@github.com:EhimeNLP/gpuser-v3-backend.git
```

### 2. .envファイルを作成

```bash
cd gpuser-v3-backend
cp .env.example .env
```

コピーした.envファイルを編集し、環境変数を設定してください。

## 設定ファイル

現在は使用していませんが，以下のファイルを作成することで、設定を変更できます。

- instance/config/development.py # 開発環境の設定ファイル
- instance/config/production.py # 本番環境の設定ファイル

instanceフォルダは、.gitignoreに登録されているため、リポジトリには含まれません。

## Author

- 大塚 琢生（<ohtsuka@ai.cs.ehime-u.ac.jp>）
- 山内洋輝
- 樽本空宙
- 宮田莉奈
