"""
Google Sheets連携のテスト

sheets_client.pyの接続テストと基本機能のテストを行う。
"""
import sys
import io
from pathlib import Path

# Windows環境でのUnicode出力対応
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config


def test_credentials_configured():
    """認証情報が設定されているかテスト"""
    print("=== 認証情報の確認 ===")

    if Config.GOOGLE_SHEETS_CREDENTIALS:
        print("✓ GOOGLE_SHEETS_CREDENTIALS: 設定済み")
        # JSON形式かどうかを簡易チェック
        if Config.GOOGLE_SHEETS_CREDENTIALS.strip().startswith("{"):
            print("  → JSON形式: OK")
        else:
            print("  → 警告: JSON形式ではない可能性があります")
    else:
        print("✗ GOOGLE_SHEETS_CREDENTIALS: 未設定")

    if Config.SPREADSHEET_ID:
        print(f"✓ SPREADSHEET_ID: {Config.SPREADSHEET_ID[:20]}...")
    else:
        print("✗ SPREADSHEET_ID: 未設定")

    print()


def test_connection():
    """接続テストを実行"""
    print("=== 接続テスト ===")

    try:
        # 循環インポートを避けるため直接インポート
        sys.path.insert(0, str(Path(__file__).parent.parent / "integrations"))
        from sheets_client import get_sheets_client

        client = get_sheets_client()
        success, message = client.test_connection()

        if success:
            print(f"✓ {message}")
        else:
            print(f"✗ {message}")

        return success
    except Exception as e:
        print(f"✗ エラー: {e}")
        return False


def test_product_to_row():
    """商品データの行変換テスト"""
    print("=== 行データ変換テスト ===")

    from models.product import (
        Product,
        ProductFeatures,
        Measurements,
        PriceSuggestion,
        Category,
        PricingStrategy,
    )
    # 循環インポートを避けるため直接インポート
    sys.path.insert(0, str(Path(__file__).parent.parent / "integrations"))
    from sheets_client import SheetsClient

    # テスト用商品データ
    product = Product(
        management_id="TEST001",
        purchase_price=800,
        measurements=Measurements(
            length=66,
            width=55,
            shoulder=48,
            sleeve=60,
        ),
        features=ProductFeatures(
            brand="adidas",
            category=Category.TOPS,
            item_type="パーカー",
            gender="メンズ",
            size="L",
            color="ネイビー",
            design="ロゴ刺繍",
            era="90s",
        ),
        title="90s adidas パーカー ロゴ刺繍 ネイビー L",
        description="【商品について】\nadidasのネイビーパーカーです。",
        hashtags=["#adidas", "#パーカー", "#古着"],
        price_suggestion=PriceSuggestion(
            minimum_price=1670,
            start_price=3500,
            expected_price=3000,
            lowest_acceptable=2500,
            strategy=PricingStrategy.BALANCED,
            reasoning="テスト用",
        ),
    )

    client = SheetsClient()
    row = client._product_to_row(product)

    print(f"✓ 行データ生成: {len(row)}カラム")
    print(f"  管理番号: {row[0]}")
    print(f"  ブランド: {row[3]}")
    print(f"  商品名: {row[12]}")
    print(f"  スタート価格: {row[15]}")

    # カラム数チェック
    expected_columns = len(SheetsClient.HEADERS)
    if len(row) == expected_columns:
        print(f"✓ カラム数: {len(row)} (期待値: {expected_columns})")
    else:
        print(f"✗ カラム数不一致: {len(row)} (期待値: {expected_columns})")

    print()


if __name__ == "__main__":
    print("Google Sheets連携テスト\n")

    test_credentials_configured()
    test_product_to_row()

    # 認証情報が設定されている場合のみ接続テストを実行
    if Config.GOOGLE_SHEETS_CREDENTIALS and Config.SPREADSHEET_ID:
        test_connection()
    else:
        print("=== 接続テスト ===")
        print("スキップ: 認証情報が未設定です")
        print("\n.envファイルに以下を設定してください:")
        print("  GOOGLE_SHEETS_CREDENTIALS={...}  # サービスアカウントのJSON")
        print("  SPREADSHEET_ID=your-spreadsheet-id")
