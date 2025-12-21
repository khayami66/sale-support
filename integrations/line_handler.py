"""
LINE Messaging API ハンドラー

LINEからのWebhookイベントを処理し、適切なレスポンスを返す。
画像の受信・保存、テキストメッセージの処理を担当する。
"""
import os
import tempfile
from pathlib import Path
from typing import Optional

from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent,
)

from config import Config


class LineHandler:
    """
    LINE Messaging APIとの連携を担当するクラス

    主な機能:
    - Webhookイベントの処理
    - テキスト/画像メッセージの受信
    - 返信メッセージの送信
    - 画像のダウンロード・保存
    """

    def __init__(
        self,
        channel_access_token: Optional[str] = None,
        channel_secret: Optional[str] = None,
    ):
        """
        ハンドラーを初期化する。

        Args:
            channel_access_token: LINEチャンネルアクセストークン
            channel_secret: LINEチャンネルシークレット
        """
        self.channel_access_token = channel_access_token or Config.LINE_CHANNEL_ACCESS_TOKEN
        self.channel_secret = channel_secret or Config.LINE_CHANNEL_SECRET

        if not self.channel_access_token or not self.channel_secret:
            raise ValueError("LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET are required")

        # Webhook Handler
        self.webhook_handler = WebhookHandler(self.channel_secret)

        # Messaging API Client
        configuration = Configuration(access_token=self.channel_access_token)
        self.api_client = ApiClient(configuration)
        self.messaging_api = MessagingApi(self.api_client)
        self.messaging_api_blob = MessagingApiBlob(self.api_client)

        # 画像保存ディレクトリ
        self.image_dir = Path(tempfile.gettempdir()) / "sale_support_images"
        self.image_dir.mkdir(exist_ok=True)

    def reply_text(self, reply_token: str, text: str) -> None:
        """
        テキストメッセージを返信する。

        Args:
            reply_token: 返信トークン
            text: 返信テキスト
        """
        # LINEのメッセージは5000文字まで
        if len(text) > 5000:
            text = text[:4997] + "..."

        self.messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)],
            )
        )

    def reply_multiple(self, reply_token: str, texts: list[str]) -> None:
        """
        複数のテキストメッセージを返信する。

        Args:
            reply_token: 返信トークン
            texts: 返信テキストのリスト（最大5件）
        """
        messages = []
        for text in texts[:5]:  # 最大5件まで
            if len(text) > 5000:
                text = text[:4997] + "..."
            messages.append(TextMessage(text=text))

        self.messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages,
            )
        )

    def push_message(self, user_id: str, text: str) -> bool:
        """
        プッシュメッセージを送信する（返信トークン不要）。

        Args:
            user_id: 送信先ユーザーID
            text: メッセージテキスト

        Returns:
            bool: 送信成功時True、失敗時False
        """
        try:
            if len(text) > 5000:
                text = text[:4997] + "..."

            self.messaging_api.push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text=text)],
                )
            )
            return True
        except Exception as e:
            print(f"[ERROR] プッシュメッセージ送信に失敗しました: {e}")
            return False

    def download_image(self, message_id: str, user_id: str) -> str:
        """
        LINEサーバーから画像をダウンロードして保存する。

        Args:
            message_id: メッセージID
            user_id: ユーザーID

        Returns:
            str: 保存した画像のファイルパス
        """
        # ユーザー別のディレクトリを作成
        user_dir = self.image_dir / user_id
        user_dir.mkdir(exist_ok=True)

        # ファイル名を生成
        image_path = user_dir / f"{message_id}.jpg"

        # 画像コンテンツを取得して保存
        with open(image_path, "wb") as f:
            content = self.messaging_api_blob.get_message_content(message_id)
            f.write(content)

        return str(image_path)

    def get_user_images(self, user_id: str) -> list[str]:
        """
        ユーザーの保存済み画像パスを取得する。

        Args:
            user_id: ユーザーID

        Returns:
            list[str]: 画像パスのリスト
        """
        user_dir = self.image_dir / user_id
        if not user_dir.exists():
            return []

        return [str(p) for p in user_dir.glob("*.jpg")]

    def clear_user_images(self, user_id: str) -> None:
        """
        ユーザーの保存済み画像を削除する。

        Args:
            user_id: ユーザーID
        """
        user_dir = self.image_dir / user_id
        if user_dir.exists():
            for image_path in user_dir.glob("*.jpg"):
                image_path.unlink()

    def format_confirmation_message(self, features: dict, has_images: int) -> str:
        """
        確認用サマリーメッセージをフォーマットする。

        Args:
            features: 商品特徴の辞書
            has_images: 画像枚数

        Returns:
            str: フォーマットされた確認メッセージ
        """
        lines = [
            f"画像 {has_images}枚を解析しました。",
            "",
            "【商品特徴（AI推定）】",
            f"1. ブランド：{features.get('brand', 'UNKNOWN')}",
            f"2. カテゴリ：{features.get('category', 'UNKNOWN')}",
            f"3. アイテム：{features.get('item_type', 'UNKNOWN')}",
            f"4. 性別：{features.get('gender', 'UNKNOWN')}",
            f"5. サイズ：{features.get('size', 'UNKNOWN')}",
            f"6. 色：{features.get('color', 'UNKNOWN')}",
            f"7. デザイン：{features.get('design') or '特になし'}",
        ]

        era = features.get('era')
        if era:
            lines.append(f"8. 年代：{era}")

        lines.extend([
            "",
            "修正がある場合は番号と内容を送信",
            "例：「1 adidas」「3 パーカー」",
            "",
            "修正完了後、戦略を選択してください：",
            "A. 高利益重視",
            "B. バランス",
            "C. 回転重視",
            "",
            "修正なしの場合は「A」「B」「C」のみ送信",
        ])

        return "\n".join(lines)

    def format_result_message(self, product: dict) -> list[str]:
        """
        生成結果をLINE用にフォーマットする。

        Args:
            product: 商品データの辞書

        Returns:
            list[str]: 分割されたメッセージのリスト
        """
        messages = []

        # 1つ目：商品名と価格
        price = product.get("price_suggestion", {})
        msg1_lines = [
            "【生成完了】",
            "",
            "■ 商品名",
            product.get("title", ""),
            "",
            "■ 価格提案",
            f"・スタート価格：{price.get('start_price', 0):,}円",
            f"・想定販売価格：{price.get('expected_price', 0):,}円",
            f"・値下げ許容：{price.get('lowest_acceptable', 0):,}円",
            f"・最低価格：{price.get('minimum_price', 0):,}円",
            "",
            f"戦略：{price.get('strategy', '')}",
            f"理由：{price.get('reasoning', '')}",
        ]
        messages.append("\n".join(msg1_lines))

        # 2つ目：商品説明
        description = product.get("description", "")
        if len(description) > 4500:
            # 長すぎる場合は分割
            messages.append("■ 商品説明\n" + description[:4500])
            messages.append(description[4500:])
        else:
            messages.append("■ 商品説明\n" + description)

        return messages
