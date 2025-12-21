"""
設定・環境変数管理

このファイルは環境変数を読み込み、アプリケーション全体で使う設定値を提供する。
他のモジュールから `from config import Config` でインポートして使用する。
"""
import os
from dotenv import load_dotenv

# .envファイルを読み込む
load_dotenv()


class Config:
    """アプリケーション設定クラス"""

    # OpenAI API設定
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")  # 画像解析にはgpt-4oを使用

    # LINE Messaging API設定
    LINE_CHANNEL_ACCESS_TOKEN: str = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    LINE_CHANNEL_SECRET: str = os.getenv("LINE_CHANNEL_SECRET", "")
    LINE_ADMIN_USER_ID: str = os.getenv("LINE_ADMIN_USER_ID", "")  # 報告書通知先のユーザーID

    # Google Sheets設定
    GOOGLE_SHEETS_CREDENTIALS: str = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "")
    SPREADSHEET_ID: str = os.getenv("SPREADSHEET_ID", "")

    # Google Drive設定
    GOOGLE_DRIVE_FOLDER_ID: str = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")

    # Cloudinary設定
    CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY: str = os.getenv("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET: str = os.getenv("CLOUDINARY_API_SECRET", "")

    # 価格計算設定
    SHIPPING_COST: int = int(os.getenv("SHIPPING_COST", "500"))  # 送料（円）
    MINIMUM_PROFIT: int = int(os.getenv("MINIMUM_PROFIT", "200"))  # 最低利益（円）
    MERCARI_FEE_RATE: float = 0.10  # メルカリ手数料率（10%）

    # セッション設定
    SESSION_TIMEOUT_MINUTES: int = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))

    @classmethod
    def validate(cls) -> list[str]:
        """
        必須の環境変数が設定されているかチェックする。

        Returns:
            list[str]: 未設定の環境変数名のリスト（空なら問題なし）
        """
        errors = []
        if not cls.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY")
        return errors

    @classmethod
    def calculate_minimum_price(cls, purchase_price: int) -> int:
        """
        最低販売価格を計算する。

        計算式: (仕入価格 + 送料 + 最低利益) ÷ (1 - 手数料率)

        Args:
            purchase_price: 仕入れ価格（円）

        Returns:
            int: 最低販売価格（切り上げ、10円単位）
        """
        import math
        raw_price = (purchase_price + cls.SHIPPING_COST + cls.MINIMUM_PROFIT) / (1 - cls.MERCARI_FEE_RATE)
        # 10円単位で切り上げ
        return int(math.ceil(raw_price / 10) * 10)
