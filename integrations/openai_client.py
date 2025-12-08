"""
OpenAI APIクライアント

GPT-4 Vision APIを使用して画像解析を行う。
テキスト生成（価格提案、商品名、ハッシュタグ）も担当する。
"""
import base64
import json
import re
from pathlib import Path
from typing import Optional

from openai import OpenAI

from config import Config
from core.prompts import (
    IMAGE_ANALYSIS_PROMPT,
    PRICING_PROMPT,
    TITLE_GENERATION_PROMPT,
    HASHTAG_GENERATION_PROMPT,
)


class OpenAIClient:
    """
    OpenAI APIとの通信を担当するクライアント

    主な機能:
    - 画像解析（Vision API）
    - 価格提案の生成
    - 商品名の生成
    - ハッシュタグの生成
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        クライアントを初期化する。

        Args:
            api_key: OpenAI APIキー（指定しない場合は環境変数から取得）
        """
        self.api_key = api_key or Config.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OpenAI APIキーが設定されていません")

        self.client = OpenAI(api_key=self.api_key)
        self.model = Config.OPENAI_MODEL

    def _encode_image(self, image_path: str) -> str:
        """
        画像ファイルをBase64エンコードする。

        Args:
            image_path: 画像ファイルのパス

        Returns:
            str: Base64エンコードされた画像データ
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"画像ファイルが見つかりません: {image_path}")

        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _get_image_media_type(self, image_path: str) -> str:
        """
        画像ファイルのメディアタイプを取得する。

        Args:
            image_path: 画像ファイルのパス

        Returns:
            str: メディアタイプ（image/jpeg, image/png等）
        """
        suffix = Path(image_path).suffix.lower()
        media_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        return media_types.get(suffix, "image/jpeg")

    def _extract_json(self, text: str) -> dict:
        """
        テキストからJSON部分を抽出してパースする。

        Args:
            text: AIの応答テキスト

        Returns:
            dict: パースされたJSON
        """
        # ```json ... ``` ブロックを探す
        json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # JSONブロックがない場合は全体をJSONとして扱う
            json_str = text.strip()

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSONのパースに失敗しました: {e}\n応答: {text}")

    def analyze_images(
        self,
        image_paths: list[str],
        user_text: str = "",
    ) -> dict:
        """
        画像を解析して商品特徴を抽出する。

        Args:
            image_paths: 画像ファイルパスのリスト（1〜5枚）
            user_text: ユーザーからの補足テキスト

        Returns:
            dict: 商品特徴（brand, category, item_type, color, design, material, description_text, confidence）
        """
        if not image_paths:
            raise ValueError("画像が指定されていません")

        if len(image_paths) > 5:
            raise ValueError("画像は5枚までです")

        # プロンプトを構築
        prompt = IMAGE_ANALYSIS_PROMPT.format(
            user_text=user_text if user_text else "（補足情報なし）"
        )

        # メッセージコンテンツを構築
        content = [{"type": "text", "text": prompt}]

        # 画像を追加
        for image_path in image_paths:
            base64_image = self._encode_image(image_path)
            media_type = self._get_image_media_type(image_path)
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{media_type};base64,{base64_image}",
                    "detail": "high",
                },
            })

        # API呼び出し
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            max_tokens=1000,
        )

        # レスポンスをパース
        result_text = response.choices[0].message.content
        return self._extract_json(result_text)

    def generate_pricing(
        self,
        features: dict,
        purchase_price: int,
        minimum_price: int,
        strategy: str,
    ) -> dict:
        """
        価格提案を生成する。

        Args:
            features: 商品特徴
            purchase_price: 仕入れ価格
            minimum_price: 最低販売価格
            strategy: 価格戦略（高利益重視/バランス/回転重視）

        Returns:
            dict: 価格提案（start_price, expected_price, lowest_acceptable, reasoning）
        """
        prompt = PRICING_PROMPT.format(
            brand=features.get("brand", "UNKNOWN"),
            category=features.get("category", "UNKNOWN"),
            item_type=features.get("item_type", "UNKNOWN"),
            gender=features.get("gender", "UNKNOWN"),
            size=features.get("size", "UNKNOWN"),
            color=features.get("color", "UNKNOWN"),
            design=features.get("design") or "特になし",
            condition=features.get("condition", "目立った傷や汚れなし"),
            purchase_price=purchase_price,
            minimum_price=minimum_price,
            strategy=strategy,
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
        )

        result_text = response.choices[0].message.content
        pricing = self._extract_json(result_text)

        # 価格の整合性チェック
        if pricing["lowest_acceptable"] < minimum_price:
            pricing["lowest_acceptable"] = minimum_price
        if pricing["expected_price"] < pricing["lowest_acceptable"]:
            pricing["expected_price"] = pricing["lowest_acceptable"]
        if pricing["start_price"] < pricing["expected_price"]:
            pricing["start_price"] = pricing["expected_price"]

        return pricing

    def generate_title(self, features: dict) -> str:
        """
        商品名を生成する。

        Args:
            features: 商品特徴

        Returns:
            str: 商品名（40文字以内）
        """
        prompt = TITLE_GENERATION_PROMPT.format(
            brand=features.get("brand", "UNKNOWN"),
            category=features.get("category", "UNKNOWN"),
            item_type=features.get("item_type", "UNKNOWN"),
            gender=features.get("gender", "UNKNOWN"),
            size=features.get("size", "UNKNOWN"),
            color=features.get("color", "UNKNOWN"),
            design=features.get("design") or "なし",
            era=features.get("era") or "不明",
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
        )

        title = response.choices[0].message.content.strip()

        # 40文字を超えている場合は切り詰める
        if len(title) > 40:
            title = title[:40]

        return title

    def generate_hashtags(self, features: dict) -> list[str]:
        """
        ハッシュタグを生成する。

        Args:
            features: 商品特徴

        Returns:
            list[str]: ハッシュタグのリスト
        """
        prompt = HASHTAG_GENERATION_PROMPT.format(
            brand=features.get("brand", "UNKNOWN"),
            category=features.get("category", "UNKNOWN"),
            item_type=features.get("item_type", "UNKNOWN"),
            gender=features.get("gender", "UNKNOWN"),
            color=features.get("color", "UNKNOWN"),
            design=features.get("design") or "なし",
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
        )

        hashtags_text = response.choices[0].message.content.strip()

        # ハッシュタグを分割してリスト化
        hashtags = re.findall(r"#\S+", hashtags_text)

        return hashtags

    def detect_category(self, image_paths: list[str]) -> str:
        """
        画像からカテゴリ（トップス/パンツ/セットアップ）のみを素早く判定する。

        Args:
            image_paths: 画像ファイルパスのリスト

        Returns:
            str: カテゴリ（トップス/パンツ/セットアップ）
        """
        if not image_paths:
            return "トップス"  # デフォルト

        # 最初の1枚だけ使用して高速に判定
        base64_image = self._encode_image(image_paths[0])
        media_type = self._get_image_media_type(image_paths[0])

        prompt = """この画像の衣類のカテゴリを判定してください。
以下の3つから1つだけ答えてください：
- トップス（上半身の服：Tシャツ、パーカー、ジャケット等）
- パンツ（下半身の服：ジーンズ、スラックス等）
- セットアップ（上下セット）

回答は「トップス」「パンツ」「セットアップ」のいずれか1語のみで答えてください。"""

        content = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{media_type};base64,{base64_image}",
                    "detail": "low",  # 高速化のため低解像度
                },
            },
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            max_tokens=20,
        )

        result = response.choices[0].message.content.strip()

        # 結果を正規化
        if "パンツ" in result:
            return "パンツ"
        elif "セットアップ" in result:
            return "セットアップ"
        else:
            return "トップス"
