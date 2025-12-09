# メルカリ出品サポートシステム 開発履歴

## 概要

このドキュメントは、メルカリ出品サポートシステムの開発過程を時系列で記録したものです。
開発中に遭遇したエラーとその解決方法、実装の詳細を含みます。

---

## 開発環境

- **OS**: Windows 11
- **Python**: 3.11
- **IDE**: VS Code
- **デプロイ先**: Render
- **開発期間**: 2025年12月

---

## Step 1: プロジェクト理解と要件確認

### 1.1 プロジェクト構造の把握

**プロンプト**: 「プロジェクトを理解してください。」

Claude Codeがコードベースを探索し、以下の構造を確認:

```
sale_support/
├── app.py                 # Flaskアプリ（エントリーポイント）
├── config.py              # 設定・環境変数
├── core/                  # コアロジック
│   ├── text_parser.py     # テキスト解析
│   ├── image_analyzer.py  # 画像分析
│   ├── description_generator.py  # 説明文生成
│   ├── pricing.py         # 価格計算
│   ├── feature_refiner.py # ユーザー修正反映
│   └── session_manager.py # セッション管理
├── integrations/          # 外部サービス連携
│   ├── openai_client.py   # OpenAI API
│   └── line_handler.py    # LINE Messaging API
├── models/product.py      # データモデル
├── templates/             # 説明文テンプレート
└── tests/                 # ユニットテスト
```

### 1.2 要件定義書の確認

**プロンプト**: 「requirements.mdを確認して、次の手順を教えてください。」

`docs/requirements.md`を確認し、開発ステップの進捗を把握:

| ステップ | 状態 |
|---------|------|
| Step 1: コアロジック | ✅ 完了 |
| Step 2: LINE連携 | ✅ 完了 |
| Step 3: Googleスプレッドシート連携 | ❌ 未実装 |
| Step 4: Renderデプロイ | ❌ 未実装 |

**次のアクション**: Step 3のGoogleスプレッドシート連携を実装

---

## Step 2: Googleスプレッドシート連携の実装

### 2.1 実装開始

**プロンプト**: 「開始します。」

#### 作成したファイル

**`integrations/sheets_client.py`**
- gspreadライブラリを使用したGoogle Sheets API連携
- サービスアカウント認証
- 27カラムのヘッダー自動作成
- `save_product()`: 商品データを1行として保存
- `test_connection()`: 接続テスト機能

**主要なコード構造**:
```python
class SheetsClient:
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    HEADERS = [
        "管理番号", "登録日時", "仕入れ価格", "ブランド",
        "カテゴリ", "アイテム", "性別", "サイズ", "色",
        "デザイン特徴", "年代", "戦略", "商品名", "商品説明",
        "ハッシュタグ", "スタート価格", "想定販売価格",
        "値下げ許容ライン", "最低価格", "実寸_着丈", "実寸_身幅",
        "実寸_肩幅", "実寸_袖丈", "実寸_ウエスト", "実寸_股下",
        "実寸_裾幅", "実寸_股上",
    ]
```

### 2.2 テストスクリプト作成時のエラー

**エラー1: Windowsエンコーディング問題**

```
UnicodeEncodeError: 'cp932' codec can't encode character '\u2713' in position 0
```

**原因**: Windowsのコンソールがcp932エンコーディングを使用しており、チェックマーク（✓）などのUnicode文字を出力できない

**解決策**: テストスクリプトの先頭にエンコーディング設定を追加
```python
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
```

---

**エラー2: 循環インポート**

```
ImportError: cannot import name 'OpenAIClient' from partially initialized module
'integrations.openai_client' (most likely due to a circular import)
```

**原因**: `integrations/__init__.py`が`openai_client`をインポートし、`openai_client`が`core`モジュールをインポート、`core`が再び`integrations`をインポートする循環参照

**解決策**: テストファイルで直接インポートするよう変更
```python
# 循環インポートを避けるため直接インポート
sys.path.insert(0, str(Path(__file__).parent.parent / "integrations"))
from sheets_client import SheetsClient
```

### 2.3 認証情報の設定

**プロンプト**: 「設定が完了しました。」

ユーザーが提供したサービスアカウントのJSONファイルを`.env`に設定:

```env
GOOGLE_SHEETS_CREDENTIALS={"type": "service_account", "project_id": "vital-chiller-456712-u5", ...}
SPREADSHEET_ID=1P0vxpGFqjq11WnkA-hyRveE3sgXuKLYcep6pRbh2DCY
```

### 2.4 接続テスト成功

```
=== 接続テスト ===
✓ 接続成功: シート「シート1」
```

### 2.5 LINEボットでの動作確認

**結果**: スプレッドシートへの保存が正常に動作

---

## Step 3: 画像保存機能の検討と断念

### 3.1 機能要件の確認

**プロンプト**: 「LINEで送信した画像もスプレットシートに保存できるようにしたいです。まず、それは可能ですか？」

**回答**: 可能。2つの表示オプションを提示:
1. URLのみ（クリックで開く）
2. セル内に画像を表示（IMAGE関数）

**ユーザー選択**: 「2. セル内に画像を表示（IMAGE関数）を希望します。」

### 3.2 Google Drive連携の実装

#### 作成したファイル

**`integrations/drive_client.py`**
- Google Drive APIを使用した画像アップロード
- 公開設定の自動適用
- IMAGE関数の生成

**主要な機能**:
```python
class DriveClient:
    def upload_image(self, file_path: str, file_name: str) -> Optional[str]:
        """画像をGoogle Driveにアップロードし、画像IDを返す"""

    def _make_public(self, file_id: str):
        """ファイルを「リンクを知っている全員が閲覧可」に設定"""

    @staticmethod
    def get_image_formula(file_id: str) -> str:
        """IMAGE関数を生成: =IMAGE("https://drive.google.com/uc?id=xxx")"""
```

### 3.3 Drive API接続エラー

**エラー**: フォルダが見つからない

```
✗ フォルダが見つかりません。GOOGLE_DRIVE_FOLDER_IDを確認してください
```

**原因**: スコープが`drive.file`では、アプリが作成したファイルにしかアクセスできない

**解決策**: スコープを`drive`に変更
```python
# 変更前
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# 変更後
SCOPES = ["https://www.googleapis.com/auth/drive"]
```

### 3.4 画像アップロードエラー（致命的）

**エラー**: サービスアカウントのストレージ制限

```
HttpError 403: Service Accounts do not have storage quota.
Leverage shared drives or use OAuth delegation instead.
```

**原因**: Googleのサービスアカウントは単独でストレージを持てない。共有ドライブまたはOAuth委任が必要。

**ユーザーへの選択肢提示**:
| 選択肢 | 説明 |
|--------|------|
| A. 画像保存を省略 | 一旦無効化、後で別サービスを使う |
| B. Cloudinaryを使う | 別途アカウント作成が必要 |

**ユーザー選択**: 「A. 画像保存を省略」

### 3.5 画像保存機能の無効化

コードをコメントアウトして無効化:

```python
# TODO: 画像保存機能は将来実装（サービスアカウントのストレージ制限のため一旦無効化）
# Google Driveに画像をアップロード
# image_formula = ""
# try:
#     drive_client = get_drive_client()
#     ...
```

---

## Step 4: Renderデプロイ

### 4.1 デプロイ用ファイルの作成

**プロンプト**: 「Renderデプロイを開始してください。」

#### 作成したファイル

**`render.yaml`**
```yaml
services:
  - type: web
    name: sale-support
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app --bind 0.0.0.0:$PORT
```

**`Procfile`**
```
web: gunicorn app:app --bind 0.0.0.0:$PORT
```

**`runtime.txt`**
```
python-3.11.0
```

**`.gitignore`への追加**
```gitignore
# Google Service Account credentials
*.json
!package.json
```

### 4.2 GitHubへのプッシュ

**プロンプト**: 「GitHubにプッシュしてください。」（リポジトリURL: https://github.com/khayami66/sale-support）

**エラー**: Windowsの予約語によるgit addエラー

```
error: short read while indexing nul
error: nul: failed to insert into database
fatal: adding files failed
```

**原因**: プロジェクト内に`nul`という名前のファイルが存在（Windowsの予約語）

**解決策**: ファイルを個別にステージング
```bash
git add .gitignore Procfile app.py config.py requirements.txt runtime.txt render.yaml
git add core/ integrations/ models/ templates/ tests/ docs/
```

**コミットとプッシュ**:
```bash
git commit -m "Initial commit: Mercari listing support system"
git branch -M main
git remote add origin https://github.com/khayami66/sale-support.git
git push -u origin main
```

### 4.3 Renderでのデプロイ設定

ユーザーがRender Dashboard上で以下を設定:

1. GitHubリポジトリを連携
2. 環境変数を設定:
   - `OPENAI_API_KEY`
   - `LINE_CHANNEL_ACCESS_TOKEN`
   - `LINE_CHANNEL_SECRET`
   - `GOOGLE_SHEETS_CREDENTIALS`
   - `SPREADSHEET_ID`
   - `SHIPPING_COST`
   - `MINIMUM_PROFIT`
   - `SESSION_TIMEOUT_MINUTES`

**デプロイ成功**:
```
==> Your service is live 🎉
==> Available at your primary URL https://sale-support.onrender.com
```

### 4.4 LINE Webhook URL設定

LINE Developers Consoleで設定:
- **Webhook URL**: `https://sale-support.onrender.com/callback`
- **Webhookの利用**: ON

**検証結果**: 「成功」

### 4.5 本番環境での動作確認

**プロンプト**: 「LINEボットで実際にテストして、本番環境で正常に動作することを確認しました。」

---

## 完成したシステム構成

```
┌─────────────┐     ┌─────────────────────────────┐     ┌─────────────┐
│    LINE     │────▶│  Render (Flask/Gunicorn)    │────▶│  OpenAI API │
│  (ユーザー)  │◀────│  sale-support.onrender.com  │◀────│  (GPT-4o)   │
└─────────────┘     └──────────────┬──────────────┘     └─────────────┘
                                   │
                                   ▼
                           ┌─────────────┐
                           │   Google    │
                           │ Spreadsheet │
                           └─────────────┘
```

---

## 技術的な学び

### 1. Windowsでの開発における注意点
- コンソール出力のエンコーディング問題（cp932 vs UTF-8）
- 予約語（nul, con, aux等）を含むファイル名の回避

### 2. Google APIの認証
- サービスアカウントのスコープ設定が重要
- `drive.file`スコープでは共有フォルダ内のファイルにアクセス不可
- サービスアカウントはストレージを持てない（共有ドライブが必要）

### 3. 循環インポートの回避
- パッケージ構造を慎重に設計する
- テスト時は直接インポートで回避可能

### 4. Renderデプロイ
- 無料プランではスリープ機能あり（初回リクエストに約50秒）
- 環境変数はダッシュボードから設定

---

## 今後の拡張予定

1. **画像保存機能**: Cloudinaryなど別サービスの検討
2. **販売データ活用**: 価格提案の高度化
3. **複数商品の並行処理**: 同時登録対応

---

## 参考リンク

- [Render Dashboard](https://dashboard.render.com/)
- [LINE Developers Console](https://developers.line.biz/console/)
- [Google Cloud Console](https://console.cloud.google.com/)
- [GitHub Repository](https://github.com/khayami66/sale-support)
