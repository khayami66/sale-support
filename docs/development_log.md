# メルカリ出品サポートシステム - 開発工程ログ

## 概要
このドキュメントは、メルカリ出品サポートシステムの開発過程で発生したエラーと解決方法を時系列でまとめたものです。

---

## 1. 環境構築フェーズ

### 1.1 ModuleNotFoundError: No module named 'dotenv'
**発生日時**: 2025-12-06
**発生状況**: `core_demo.py`を実行した際に発生

**エラー内容**:
```
Traceback (most recent call last):
  File "c:\Users\admin\Desktop\実践課題\sale_support\core_demo.py", line 20, in <module>
    from dotenv import load_dotenv
ModuleNotFoundError: No module named 'dotenv'
```

**原因**:
- 必要なPythonパッケージがインストールされていなかった

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

**原因**:
- グローバル環境にはパッケージがインストールされていたが、仮想環境（.venv）にはインストールされていなかった
- 仮想環境とグローバル環境は独立しているため、それぞれ個別にパッケージをインストールする必要がある

**解決方法**:
仮想環境をアクティベートした状態で再度インストール：
```powershell
& c:/Users/admin/Desktop/実践課題/sale_support/.venv/Scripts/pip.exe install -r requirements.txt
```

---

## 2. LINE連携フェーズ

### 2.1 LINE自動応答メッセージの干渉
**発生状況**: LINEで画像やテキストを送信した際

**症状**:
- 「メッセージありがとうございます！申し訳ありませんが、このアカウントでは個別のお問い合わせを受け付けておりません。」というメッセージが表示される
- ngrokには「502 Bad Gateway」が返る

**原因**:
- LINE Official Account Managerの「応答メッセージ」が有効になっていた
- Webhookとは別に自動応答が動作していた

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

**原因**:
- LINE Bot SDK v3では`get_message_content`メソッドが`MessagingApi`クラスではなく`MessagingApiBlob`クラスに移動している
- 画像コンテンツの取得方法がSDKのバージョンで異なる

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

**症状**:
- 仕入れ価格を送信しても「不足している情報: 仕入れ価格」と表示され続ける

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

## 3. 対話式入力フロー実装フェーズ

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

4. **新しいフロー**:
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

## 4. 最終的なシステム構成

### 4.1 ファイル構成
```
sale_support/
├── app.py                    # Flaskアプリ（メインエントリーポイント）
├── config.py                 # 設定管理
├── requirements.txt          # 依存パッケージ
├── .env                      # 環境変数
├── core/
│   ├── text_parser.py        # テキスト解析（シンプル入力対応追加）
│   ├── image_analyzer.py     # 画像解析
│   ├── description_generator.py
│   ├── pricing.py
│   ├── feature_refiner.py
│   ├── session_manager.py    # セッション管理（WAITING_MEASUREMENTS追加）
│   └── prompts.py
├── integrations/
│   ├── openai_client.py      # OpenAI API（detect_category追加）
│   └── line_handler.py       # LINE API（MessagingApiBlob対応）
├── models/
│   └── product.py
└── templates/
    ├── tops.txt
    ├── pants.txt
    └── setup.txt
```

### 4.2 対話フロー図
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
```

---

## 5. 学んだ教訓

1. **仮想環境の管理**: グローバル環境と仮想環境は独立しているため、パッケージのインストール先を意識する

2. **SDK バージョンの違い**: LINE Bot SDK v3では一部のメソッドが別クラスに移動している。公式ドキュメントを確認することが重要

3. **正規表現の柔軟性**: 日本語入力では全角スペースや表記揺れを考慮したパターンが必要

4. **型の整合性**: Enum型を使用している場合、文字列との変換を適切に行う必要がある

5. **ユーザビリティ**: 入力負担を減らす対話式フローは、初期実装よりも複雑になるが、ユーザー体験を大きく向上させる

---

## 6. 今後の改善点

- Google Sheets連携による商品データの永続化
- 画像のクラウドストレージ保存
- 複数商品の並列処理
- 管理画面の実装

---

*ドキュメント作成日: 2025-12-06*
