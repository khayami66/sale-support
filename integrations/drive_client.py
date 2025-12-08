"""
Google Drive連携クライアント

商品画像をGoogle Driveにアップロードし、共有リンクを取得する。
"""
import json
import os
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials

from config import Config


class DriveClient:
    """Google Drive連携クライアント"""

    # 認証に必要なスコープ
    SCOPES = [
        "https://www.googleapis.com/auth/drive",
    ]

    def __init__(self):
        """クライアントを初期化する"""
        self._service = None
        self._folder_id = Config.GOOGLE_DRIVE_FOLDER_ID

    def _get_credentials(self) -> Credentials:
        """認証情報を取得する"""
        credentials_json = Config.GOOGLE_SHEETS_CREDENTIALS
        if not credentials_json:
            raise ValueError("GOOGLE_SHEETS_CREDENTIALS環境変数が設定されていません")

        credentials_dict = json.loads(credentials_json)
        return Credentials.from_service_account_info(
            credentials_dict,
            scopes=self.SCOPES,
        )

    def _get_service(self):
        """Drive APIサービスを取得する（遅延初期化）"""
        if self._service is None:
            credentials = self._get_credentials()
            self._service = build("drive", "v3", credentials=credentials)
        return self._service

    def upload_image(self, file_path: str, file_name: Optional[str] = None) -> Optional[str]:
        """
        画像をGoogle Driveにアップロードし、画像IDを返す。

        Args:
            file_path: アップロードする画像のローカルパス
            file_name: Drive上でのファイル名（省略時はローカルファイル名を使用）

        Returns:
            str: アップロードされた画像のID（失敗時はNone）
        """
        if not os.path.exists(file_path):
            print(f"ファイルが見つかりません: {file_path}")
            return None

        if not self._folder_id:
            print("GOOGLE_DRIVE_FOLDER_ID環境変数が設定されていません")
            return None

        try:
            service = self._get_service()

            # ファイル名を決定
            if file_name is None:
                file_name = os.path.basename(file_path)

            # ファイルのメタデータ
            file_metadata = {
                "name": file_name,
                "parents": [self._folder_id],
            }

            # MIMEタイプを判定
            mime_type = self._get_mime_type(file_path)

            # ファイルをアップロード
            media = MediaFileUpload(file_path, mimetype=mime_type)
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id",
            ).execute()

            file_id = file.get("id")

            # ファイルを公開設定にする（IMAGE関数で表示するため）
            self._make_public(file_id)

            return file_id

        except Exception as e:
            print(f"画像のアップロードに失敗しました: {e}")
            return None

    def upload_images(self, file_paths: list[str], management_id: str) -> list[str]:
        """
        複数の画像をGoogle Driveにアップロードする。

        Args:
            file_paths: アップロードする画像のローカルパスのリスト
            management_id: 商品管理番号（ファイル名のプレフィックスに使用）

        Returns:
            list[str]: アップロードされた画像のIDリスト
        """
        image_ids = []
        for i, file_path in enumerate(file_paths, 1):
            # ファイル名を「管理番号_連番.拡張子」形式にする
            ext = os.path.splitext(file_path)[1] or ".jpg"
            file_name = f"{management_id}_{i}{ext}"

            image_id = self.upload_image(file_path, file_name)
            if image_id:
                image_ids.append(image_id)

        return image_ids

    def _make_public(self, file_id: str):
        """
        ファイルを「リンクを知っている全員が閲覧可」に設定する。

        Args:
            file_id: 公開設定にするファイルのID
        """
        try:
            service = self._get_service()
            service.permissions().create(
                fileId=file_id,
                body={
                    "type": "anyone",
                    "role": "reader",
                },
            ).execute()
        except Exception as e:
            print(f"公開設定の変更に失敗しました: {e}")

    def _get_mime_type(self, file_path: str) -> str:
        """ファイルパスからMIMEタイプを判定する"""
        ext = os.path.splitext(file_path)[1].lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        return mime_types.get(ext, "image/jpeg")

    @staticmethod
    def get_image_url(file_id: str) -> str:
        """
        画像IDからIMAGE関数用のURLを生成する。

        Args:
            file_id: 画像のID

        Returns:
            str: IMAGE関数で使用できるURL
        """
        return f"https://drive.google.com/uc?id={file_id}"

    @staticmethod
    def get_image_formula(file_id: str) -> str:
        """
        画像IDからスプレッドシートのIMAGE関数を生成する。

        Args:
            file_id: 画像のID

        Returns:
            str: IMAGE関数の文字列
        """
        url = DriveClient.get_image_url(file_id)
        return f'=IMAGE("{url}")'

    @staticmethod
    def get_images_formula(file_ids: list[str]) -> str:
        """
        複数の画像IDから、最初の画像のIMAGE関数を生成する。
        （スプレッドシートの1セルには1画像のみ表示）

        Args:
            file_ids: 画像IDのリスト

        Returns:
            str: IMAGE関数の文字列（画像がない場合は空文字）
        """
        if not file_ids:
            return ""
        return DriveClient.get_image_formula(file_ids[0])

    def test_connection(self) -> tuple[bool, str]:
        """
        接続テストを行う。

        Returns:
            tuple[bool, str]: (成功/失敗, メッセージ)
        """
        try:
            service = self._get_service()

            # フォルダの存在確認
            if not self._folder_id:
                return False, "GOOGLE_DRIVE_FOLDER_ID環境変数が設定されていません"

            folder = service.files().get(
                fileId=self._folder_id,
                fields="name",
            ).execute()

            folder_name = folder.get("name", "不明")
            return True, f"接続成功: フォルダ「{folder_name}」"

        except json.JSONDecodeError:
            return False, "GOOGLE_SHEETS_CREDENTIALSのJSON形式が不正です"
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg:
                return False, "フォルダが見つかりません。GOOGLE_DRIVE_FOLDER_IDを確認してください"
            return False, f"接続エラー: {e}"


# シングルトンインスタンス
_drive_client: Optional[DriveClient] = None


def get_drive_client() -> DriveClient:
    """DriveClientのシングルトンを取得する"""
    global _drive_client
    if _drive_client is None:
        _drive_client = DriveClient()
    return _drive_client
