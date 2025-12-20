"""
Cloudinary画像アップロードクライアント

商品画像をCloudinaryにアップロードし、URLを取得する。
"""
from typing import Optional

import cloudinary
import cloudinary.uploader

from config import Config


class CloudinaryClient:
    """Cloudinary画像アップロードクライアント"""

    def __init__(self):
        """クライアントを初期化する"""
        self._configured = False
        self._configure()

    def _configure(self):
        """Cloudinaryの認証情報を設定する"""
        if not Config.CLOUDINARY_CLOUD_NAME:
            print("[WARNING] CLOUDINARY_CLOUD_NAME が設定されていません")
            return

        cloudinary.config(
            cloud_name=Config.CLOUDINARY_CLOUD_NAME,
            api_key=Config.CLOUDINARY_API_KEY,
            api_secret=Config.CLOUDINARY_API_SECRET,
            secure=True
        )
        self._configured = True

    def upload_image(self, file_path: str, public_id: Optional[str] = None) -> Optional[str]:
        """
        画像をCloudinaryにアップロードする。

        Args:
            file_path: アップロードする画像のローカルパス
            public_id: Cloudinary上での識別子（省略時は自動生成）

        Returns:
            Optional[str]: アップロードされた画像のURL（失敗時はNone）
        """
        if not self._configured:
            print("[ERROR] Cloudinaryが設定されていません")
            return None

        try:
            # アップロードオプション
            options = {
                "folder": "mercari_products",  # フォルダにまとめる
                "resource_type": "image",
            }
            if public_id:
                options["public_id"] = public_id

            # アップロード実行
            result = cloudinary.uploader.upload(file_path, **options)

            # URLを取得
            url = result.get("secure_url")
            print(f"[INFO] 画像をアップロードしました: {url}")
            return url

        except Exception as e:
            print(f"[ERROR] 画像アップロードに失敗しました: {e}")
            return None

    def get_image_formula(self, url: str) -> str:
        """
        スプレッドシートのIMAGE関数を生成する。

        Args:
            url: 画像のURL

        Returns:
            str: IMAGE関数の文字列
        """
        return f'=IMAGE("{url}")'


# シングルトンインスタンス
_cloudinary_client: Optional[CloudinaryClient] = None


def get_cloudinary_client() -> CloudinaryClient:
    """CloudinaryClientのシングルトンを取得する"""
    global _cloudinary_client
    if _cloudinary_client is None:
        _cloudinary_client = CloudinaryClient()
    return _cloudinary_client
