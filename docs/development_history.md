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

## Phase 1: 環境構築（2025-12-06）

### 1.1 ModuleNotFoundError: No module named 'dotenv'

**発生状況**: `core_demo.py`を実行した際に発生

**エラー内容**:
```
Traceback (most recent call last):
  File "c:\Users\admin\Desktop\実践課題\sale_support\core_demo.py", line 20, in <module>
    from dotenv import load_dotenv
ModuleNotFoundError: No module named 'dotenv'
```

**原因**: 必要なPythonパッケージがインストールされていなかった

**解決方法**:
```bash
pip install -r requirements.txt
```

---

### 1.2 仮想環境でのパッケージ不足

**発生状況**: 仮想環境（.venv）をアクティベートした状態で`app.py`を実行

**エラー内容**:
```
ModuleNotFoundError: No module named 'flask'
```

**原因**: グローバル環境にはパッケージがインストールされていたが、仮想環境（.venv）にはインストールされていなかった

**解決方法**:
仮想環境をアクティベートした状態で再度インストール：
```powershell
& c:/Users/admin/Desktop/実践課題/sale_support/.venv/Scripts/pip.exe install -r requirements.txt
```

---

## Phase 2: LINE連携（2025-12-06）

### 2.1 LINE自動応答メッセージの干渉

**発生状況**: LINEで画像やテキストを送信した際

**症状**:
- 「メッセージありがとうございます！申し訳ありませんが、このアカウントでは個別のお問い合わせを受け付けておりません。」というメッセージが表示される
- ngrokには「502 Bad Gateway」が返る

**原因**: LINE Official Account Managerの「応答メッセージ」が有効になっていた

**解決方法**:
1. [LINE Official Account Manager](https://manager.line.biz/) にログイン
2. 対象アカウントの「設定」→「応答設定」を開く
3. 以下のように設定：
   - **応答モード**: 「Bot」に変更
   - **応答メッセージ**: オフ
   - **Webhook**: オン

---

### 2.2 画像ダウンロードエラー（MessagingApiBlob）

**発生状況**: LINEで画像を送信した際

**エラー内容**:
```
画像の保存に失敗しました: a bytes-like object is required, not 'int'
```

**原因**: LINE Bot SDK v3では`get_message_content`メソッドが`MessagingApi`クラスではなく`MessagingApiBlob`クラスに移動している

**解決方法**:
`integrations/line_handler.py`を修正：

```python
# 修正前
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)

# 修正後（MessagingApiBlobを追加）
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    MessagingApiBlob,  # 追加
    ReplyMessageRequest,
    TextMessage,
)
```

```python
# 修正前
self.messaging_api = MessagingApi(self.api_client)

# 修正後（MessagingApiBlobインスタンスを追加）
self.messaging_api = MessagingApi(self.api_client)
self.messaging_api_blob = MessagingApiBlob(self.api_client)
```

```python
# 修正前
content = self.messaging_api.get_message_content(message_id)

# 修正後
content = self.messaging_api_blob.get_message_content(message_id)
```

さらに、画像保存処理も修正：
```python
# 修正前（イテレータとして処理）
with open(image_path, "wb") as f:
    for chunk in content:
        f.write(chunk)

# 修正後（バイトデータとして直接書き込み）
with open(image_path, "wb") as f:
    content = self.messaging_api_blob.get_message_content(message_id)
    f.write(content)
```

---

### 2.3 仕入れ価格が認識されない問題

**発生状況**: 「仕入れ価格　880円」と送信しても認識されない

**症状**: 仕入れ価格を送信しても「不足している情報: 仕入れ価格」と表示され続ける

**原因**:
- 正規表現パターンが「仕入れ価格」という表記に対応していなかった
- 全角スペース（\u3000）に対応していなかった

**解決方法**:
`core/text_parser.py`の正規表現パターンを修正：

```python
# 修正前
PURCHASE_PRICE_PATTERNS = [
    re.compile(r"仕入れ?[:\s：]*(\d+)円?", re.IGNORECASE),
    re.compile(r"仕入[:\s：]*(\d+)円?", re.IGNORECASE),
    re.compile(r"購入[:\s：]*(\d+)円?", re.IGNORECASE),
]

# 修正後（「価格」と全角スペースに対応）
PURCHASE_PRICE_PATTERNS = [
    re.compile(r"仕入れ?価格?[:\s：\u3000]*(\d+)円?", re.IGNORECASE),
    re.compile(r"仕入[:\s：\u3000]*(\d+)円?", re.IGNORECASE),
    re.compile(r"購入価格?[:\s：\u3000]*(\d+)円?", re.IGNORECASE),
    re.compile(r"原価[:\s：\u3000]*(\d+)円?", re.IGNORECASE),
]
```

---

## Phase 3: 対話式入力フロー実装（2025-12-06）

### 3.1 ユーザー入力負担の改善

**発生状況**: 初期実装では、ユーザーが項目名を含めて入力する必要があった

**課題**:
- 「仕入れ価格 880円」「商品管理番号 222」「着丈60cm 身幅50cm...」のように項目名も入力が必要
- 入力に時間がかかる

**解決方法**:
「最小限必須 + 対話式補完」方式を採用：

1. **新しいセッション状態の追加** (`core/session_manager.py`):
```python
class SessionState(Enum):
    IDLE = "idle"
    COLLECTING = "collecting"
    WAITING_MEASUREMENTS = "waiting_measurements"  # 新規追加
    CONFIRMING = "confirming"
    GENERATING = "generating"
```

2. **シンプル入力パーサーの実装** (`core/text_parser.py`):
```python
@classmethod
def parse_price_and_id(cls, text: str) -> tuple[Optional[int], Optional[str]]:
    """「880 222」のような形式から価格と管理番号を抽出"""
    numbers = cls.parse_simple_numbers(text, 2)
    purchase_price = numbers[0]
    management_id = str(numbers[1]) if numbers[1] is not None else None
    return purchase_price, management_id

@classmethod
def parse_measurements_simple(cls, text: str, category: str) -> Measurements:
    """「60 50 42 20」のような形式から実寸を抽出"""
    # カテゴリに応じて異なる項目を期待
```

3. **カテゴリ自動判定機能の追加** (`integrations/openai_client.py`):
```python
def detect_category(self, image_paths: list[str]) -> str:
    """画像からカテゴリ（トップス/パンツ/セットアップ）を判定"""
```

4. **新しい対話フロー**:
```
1. [ユーザー] 画像送信
2. [システム] 「仕入れ価格 管理番号」を送信してください。例: 「880 222」
3. [ユーザー] 880 222
4. [システム] カテゴリ: トップス
              実寸を入力してください（着丈 身幅 肩幅 袖丈の順）例: 「60 50 42 20」
5. [ユーザー] 60 50 42 20
6. [システム] 【商品特徴（AI推定）】確認メッセージ
7. [ユーザー] B（戦略選択）
8. [システム] 生成結果
```

---

### 3.2 Category Enum型エラー

**発生状況**: 実寸入力後の画像解析で発生

**エラー内容**:
```
エラーが発生しました: 'str' object has no attribute 'value'
```

**原因**:
- `ProductFeatures.category`は`Category` Enum型を期待
- `session.detected_category`は文字列（"トップス"等）
- 文字列を直接代入したため、`to_dict()`メソッドで`self.category.value`を呼び出す際にエラー

**解決方法**:
`app.py`で文字列をEnum型に変換：

```python
# 修正前
if session.detected_category:
    features.category = session.detected_category

# 修正後
from models.product import Product, Measurements, Category

if session.detected_category:
    category_map = {
        "トップス": Category.TOPS,
        "パンツ": Category.PANTS,
        "セットアップ": Category.SETUP,
    }
    features.category = category_map.get(session.detected_category, Category.TOPS)
```

---

## Phase 4: Googleスプレッドシート連携（2025-12-10）

### 4.1 プロジェクト理解と要件確認

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

**プロンプト**: 「requirements.mdを確認して、次の手順を教えてください。」

`docs/requirements.md`を確認し、開発ステップの進捗を把握:

| ステップ | 状態 |
|---------|------|
| Step 1: コアロジック | ✅ 完了 |
| Step 2: LINE連携 | ✅ 完了 |
| Step 3: Googleスプレッドシート連携 | ❌ 未実装 |
| Step 4: Renderデプロイ | ❌ 未実装 |

---

### 4.2 実装開始

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

---

### 4.3 テストスクリプト作成時のエラー

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

---

### 4.4 認証情報の設定

**プロンプト**: 「設定が完了しました。」

ユーザーが提供したサービスアカウントのJSONファイルを`.env`に設定:

```env
GOOGLE_SHEETS_CREDENTIALS={"type": "service_account", "project_id": "vital-chiller-456712-u5", ...}
SPREADSHEET_ID=1P0vxpGFqjq11WnkA-hyRveE3sgXuKLYcep6pRbh2DCY
```

---

### 4.5 接続テスト成功

```
=== 接続テスト ===
✓ 接続成功: シート「シート1」
```

### 4.6 LINEボットでの動作確認

**結果**: スプレッドシートへの保存が正常に動作

---

## Phase 5: 画像保存機能の検討と断念（2025-12-10）

### 5.1 機能要件の確認

**プロンプト**: 「LINEで送信した画像もスプレットシートに保存できるようにしたいです。まず、それは可能ですか？」

**回答**: 可能。2つの表示オプションを提示:
1. URLのみ（クリックで開く）
2. セル内に画像を表示（IMAGE関数）

**ユーザー選択**: 「2. セル内に画像を表示（IMAGE関数）を希望します。」

---

### 5.2 Google Drive連携の実装

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

---

### 5.3 Drive API接続エラー

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

---

### 5.4 画像アップロードエラー（致命的）

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

---

### 5.5 画像保存機能の無効化

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

## Phase 6: Renderデプロイ（2025-12-10）

### 6.1 デプロイ用ファイルの作成

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

---

### 6.2 GitHubへのプッシュ

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

---

### 6.3 Renderでのデプロイ設定

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

---

### 6.4 LINE Webhook URL設定

LINE Developers Consoleで設定:
- **Webhook URL**: `https://sale-support.onrender.com/callback`
- **Webhookの利用**: ON

**検証結果**: 「成功」

---

### 6.5 本番環境での動作確認

**プロンプト**: 「LINEボットで実際にテストして、本番環境で正常に動作することを確認しました。」

---

## 完成したシステム構成

### アーキテクチャ図

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

### ファイル構成

```
sale_support/
├── app.py                    # Flaskアプリ（メインエントリーポイント）
├── config.py                 # 設定管理
├── requirements.txt          # 依存パッケージ
├── Procfile                  # Render用起動コマンド
├── runtime.txt               # Pythonバージョン指定
├── render.yaml               # Render設定ファイル
├── .env                      # 環境変数（Git管理外）
├── .gitignore                # Git除外設定
├── core/
│   ├── text_parser.py        # テキスト解析（シンプル入力対応）
│   ├── image_analyzer.py     # 画像解析
│   ├── description_generator.py  # 説明文生成
│   ├── pricing.py            # 価格計算
│   ├── feature_refiner.py    # ユーザー修正反映
│   ├── session_manager.py    # セッション管理
│   └── prompts.py            # AIプロンプト定義
├── integrations/
│   ├── openai_client.py      # OpenAI API
│   ├── line_handler.py       # LINE API（MessagingApiBlob対応）
│   ├── sheets_client.py      # Google Sheets API
│   └── drive_client.py       # Google Drive API（無効化中）
├── models/
│   └── product.py            # データモデル
├── templates/
│   ├── tops.txt              # トップス用テンプレート
│   ├── pants.txt             # パンツ用テンプレート
│   └── setup.txt             # セットアップ用テンプレート
├── tests/
│   ├── test_text_parser.py
│   ├── test_pricing.py
│   ├── test_sheets_client.py
│   └── test_drive_client.py
└── docs/
    ├── requirements.md       # 要件定義書
    └── development_history.md  # このドキュメント
```

### 対話フロー図

```
[画像送信]
    ↓
[価格・管理番号入力] ← シンプル入力「880 222」
    ↓
[AIカテゴリ判定]
    ↓
[実寸入力] ← シンプル入力「60 50 42 20」
    ↓
[AI画像解析]
    ↓
[確認・修正]
    ↓
[戦略選択 A/B/C]
    ↓
[商品情報生成・出力]
    ↓
[Googleスプレッドシート保存]
```

---

## Phase 7: 複数画像対応（2025-12-18）

### 7.1 課題の特定

**発生状況**: LINEで複数画像を送信した際

**症状**:
- 画像を3枚送ると、3回返信が来る
- 「画像を受け付けました（1枚目）」「（2枚目）」「（3枚目）」と個別に返信

**原因**: `process_image_message`関数が画像1枚ごとに`handler.reply_text()`を呼び出していた

---

### 7.2 改善方針の検討

3つの方式を検討:

| 方式 | 説明 | メリット | デメリット |
|------|------|---------|-----------|
| A. 明示的な完了コマンド | 画像送信後「完了」と送信 | シンプル、確実 | 1回多く入力が必要 |
| B. 価格・管理番号で確定 | 「880 222」を送ったら画像受付終了 | 現在のフローに近い | 追加画像を後から送れない |
| C. タイムアウト方式 | 画像送信後5秒待って自動確定 | 入力不要 | 実装が複雑 |

**採用**: B方式（価格・管理番号で確定）

---

### 7.3 実装内容

**`app.py`の修正**:

```python
# 修正前: 画像ごとに返信
else:
    handler.reply_text(
        reply_token,
        f"画像を受け付けました（{len(session.image_paths)}枚目）\n\n「仕入れ価格 管理番号」を送信してください。"
    )

# 修正後: 返信を抑制（静かに蓄積）
else:
    # 複数画像対応: 画像受信時は返信せず、静かに蓄積する
    # 価格・管理番号を受信した時にまとめて処理する
    pass
```

**`start_category_detection`関数の修正**:

```python
# 修正前
handler.reply_text(
    reply_token,
    f"カテゴリ: {category}\n\n{prompt}"
)

# 修正後: 画像枚数を含めたメッセージ
image_count = len(session.image_paths)
handler.reply_text(
    reply_token,
    f"画像{image_count}枚を受け付けました。\n\nカテゴリ: {category}\n\n{prompt}"
)
```

---

### 7.4 改善後のフロー

```
[変更前]
1. [ユーザー] 画像3枚を送信
2. [システム] 「画像を受け付けました（1枚目）」
3. [システム] 「画像を受け付けました（2枚目）」
4. [システム] 「画像を受け付けました（3枚目）」
5. [ユーザー] 880 222
6. [システム] カテゴリ判定...

[変更後]
1. [ユーザー] 画像3枚を送信
2. （返信なし - 静かに蓄積）
3. [ユーザー] 880 222
4. [システム] 「画像3枚を受け付けました。カテゴリ: トップス...」
```

---

## Phase 8: サイズ正規化・性別推定機能（2025-12-18）

### 8.1 課題の特定

**発生状況**: AI推定の段階で「性別」と「サイズ」が常にUNKNOWNで返ってくる

**原因**:
- `IMAGE_ANALYSIS_PROMPT`にサイズと性別の出力指示がなかった
- `image_analyzer.py`でAI結果からサイズ・性別を取得していなかった

---

### 8.2 サイズ正規化ルールの追加

`core/prompts.py`の`IMAGE_ANALYSIS_PROMPT`に以下を追加:

**出力フォーマットに追加**:
```json
{
  "size": "正規化されたサイズ（XS/S/M/L/XL/XXL/3XL/4XLのいずれか）",
  "gender": "性別（メンズ/レディース/ユニセックスのいずれか）"
}
```

**サイズ変換ルール**:
| 入力 | 出力 |
|------|------|
| FREE / F / ONE SIZE | M |
| レディース 7号 | S |
| レディース 9号 | M |
| レディース 11号 | L |
| メンズ 46 | M |
| メンズ 48 | L |
| US S / US M / US L | そのまま |
| 身幅 〜48cm | S |
| 身幅 49-54cm | M |
| 身幅 55-60cm | L |
| 身幅 61-66cm | XL |
| 身幅 67cm〜 | XXL |

---

### 8.3 性別推測ルールの追加

**実寸による判定基準（トップス・身幅）**:
- 〜45cm → レディース
- 46-52cm → ユニセックス
- 53cm〜 → メンズ

**実寸による判定基準（パンツ・ウエスト）**:
- 〜66cm → レディース
- 67-76cm → ユニセックス
- 77cm〜 → メンズ

**その他の判断材料**:
- 花柄・パステルカラー・フリル → レディース寄り
- 大きめシルエット・ダークカラー・スポーツブランド → メンズ寄り
- 判断に迷う場合 → ユニセックス

---

### 8.4 image_analyzer.pyの修正

```python
# 修正前: テキストからのみ取得、なければUNKNOWN
gender=parsed["gender"] or "UNKNOWN",
size=parsed["size"] or "UNKNOWN",

# 修正後: テキスト優先、なければAI推定を使用
gender=parsed["gender"] or ai_result.get("gender", "UNKNOWN"),
size=parsed["size"] or ai_result.get("size", "UNKNOWN"),
```

---

## 技術的な学び

### 1. Windowsでの開発における注意点
- コンソール出力のエンコーディング問題（cp932 vs UTF-8）
- 予約語（nul, con, aux等）を含むファイル名の回避
- 仮想環境とグローバル環境は独立しているため、パッケージのインストール先を意識する

### 2. LINE Bot SDK v3
- 一部のメソッドが別クラスに移動している（`MessagingApiBlob`等）
- 公式ドキュメントを確認することが重要

### 3. 正規表現の柔軟性
- 日本語入力では全角スペース（\u3000）や表記揺れを考慮したパターンが必要

### 4. 型の整合性
- Enum型を使用している場合、文字列との変換を適切に行う必要がある

### 5. Google APIの認証
- サービスアカウントのスコープ設定が重要
- `drive.file`スコープでは共有フォルダ内のファイルにアクセス不可
- サービスアカウントはストレージを持てない（共有ドライブが必要）

### 6. 循環インポートの回避
- パッケージ構造を慎重に設計する
- テスト時は直接インポートで回避可能

### 7. Renderデプロイ
- 無料プランではスリープ機能あり（初回リクエストに約50秒）
- 環境変数はダッシュボードから設定

### 8. ユーザビリティ
- 入力負担を減らす対話式フローは、初期実装よりも複雑になるが、ユーザー体験を大きく向上させる

---

## 今後の拡張予定

詳細は `docs/future_enhancements.md` を参照。

| 機能 | 状態 | 説明 |
|------|------|------|
| 複数画像対応 | ✅ 完了 | 画像を静かに蓄積、返信は1回のみ |
| サイズ正規化・性別推定 | ✅ 完了 | AIがサイズと性別を自動推定 |
| スプレッドシートへの画像保存 | 未着手 | Cloudinaryなど別サービスの検討 |
| 販売管理機能 | 未着手 | 販売価格・利益の管理 |
| 販売完了時のLINE入力 | 未着手 | 「売れた 215 3000 700」形式 |

---

## 参考リンク

- [GitHub Repository](https://github.com/khayami66/sale-support)
- [Render Dashboard](https://dashboard.render.com/)
- [LINE Developers Console](https://developers.line.biz/console/)
- [Google Cloud Console](https://console.cloud.google.com/)

---

*最終更新日: 2025-12-18*
