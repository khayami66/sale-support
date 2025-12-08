"""
Google Drive連携のテスト

drive_client.pyの接続テストと基本機能のテストを行う。
"""
import sys
import io
from pathlib import Path

# Windows環境でのUnicode出力対応
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "integrations"))

from config import Config


def test_credentials_configured():
    """認証情報が設定されているかテスト"""
    print("=== 認証情報の確認 ===")

    if Config.GOOGLE_SHEETS_CREDENTIALS:
        print("✓ GOOGLE_SHEETS_CREDENTIALS: 設定済み")
    else:
        print("✗ GOOGLE_SHEETS_CREDENTIALS: 未設定")

    if Config.GOOGLE_DRIVE_FOLDER_ID:
        print(f"✓ GOOGLE_DRIVE_FOLDER_ID: {Config.GOOGLE_DRIVE_FOLDER_ID}")
    else:
        print("✗ GOOGLE_DRIVE_FOLDER_ID: 未設定")

    print()


def test_connection():
    """接続テストを実行"""
    print("=== 接続テスト ===")

    try:
        from drive_client import get_drive_client

        client = get_drive_client()
        success, message = client.test_connection()

        if success:
            print(f"✓ {message}")
        else:
            print(f"✗ {message}")

        return success
    except Exception as e:
        print(f"✗ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_image_formula():
    """IMAGE関数の生成テスト"""
    print("=== IMAGE関数生成テスト ===")

    from drive_client import DriveClient

    test_id = "1ABC123def456"

    url = DriveClient.get_image_url(test_id)
    print(f"URL: {url}")

    formula = DriveClient.get_image_formula(test_id)
    print(f"IMAGE関数: {formula}")

    # 複数画像のテスト
    test_ids = ["1ABC123", "2DEF456", "3GHI789"]
    formula_multi = DriveClient.get_images_formula(test_ids)
    print(f"複数画像（最初の1枚）: {formula_multi}")

    # 空リストのテスト
    formula_empty = DriveClient.get_images_formula([])
    print(f"空リスト: '{formula_empty}'")

    print("✓ IMAGE関数生成テスト完了")
    print()


if __name__ == "__main__":
    print("Google Drive連携テスト\n")

    test_credentials_configured()
    test_image_formula()

    # 認証情報が設定されている場合のみ接続テストを実行
    if Config.GOOGLE_SHEETS_CREDENTIALS and Config.GOOGLE_DRIVE_FOLDER_ID:
        test_connection()
    else:
        print("=== 接続テスト ===")
        print("スキップ: 認証情報が未設定です")
        print("\n.envファイルに以下を設定してください:")
        print("  GOOGLE_DRIVE_FOLDER_ID=your-folder-id")
