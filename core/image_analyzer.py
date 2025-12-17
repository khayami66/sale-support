"""
画像解析モジュール

OpenAI Vision APIを使用して画像から商品特徴を抽出する。
テキストパーサーと組み合わせて、ユーザー入力と画像の両方から情報を統合する。
"""
from typing import Optional

from models.product import ProductFeatures, Category
from core.text_parser import TextParser
from integrations.openai_client import OpenAIClient


class ImageAnalyzer:
    """
    画像解析クラス

    画像とテキストから商品特徴を抽出し、ProductFeaturesオブジェクトを生成する。
    """

    def __init__(self, openai_client: Optional[OpenAIClient] = None):
        """
        アナライザーを初期化する。

        Args:
            openai_client: OpenAIクライアント（指定しない場合は新規作成）
        """
        self.openai_client = openai_client or OpenAIClient()

    def analyze(
        self,
        image_paths: list[str],
        user_text: str = "",
    ) -> ProductFeatures:
        """
        画像とテキストから商品特徴を抽出する。

        Args:
            image_paths: 画像ファイルパスのリスト
            user_text: ユーザーからの補足テキスト

        Returns:
            ProductFeatures: 抽出された商品特徴
        """
        # テキストから抽出できる情報を先に取得
        parsed = TextParser.parse_all(user_text)

        # 画像解析を実行
        ai_result = self.openai_client.analyze_images(
            image_paths=image_paths,
            user_text=user_text,
        )

        # カテゴリをEnumに変換
        category = self._parse_category(ai_result.get("category", "トップス"))

        # ProductFeaturesを構築
        # 性別・サイズはテキストを優先し、なければAI推定を使用
        features = ProductFeatures(
            brand=ai_result.get("brand", "UNKNOWN"),
            category=category,
            item_type=ai_result.get("item_type", "UNKNOWN"),
            gender=parsed["gender"] or ai_result.get("gender", "UNKNOWN"),
            size=parsed["size"] or ai_result.get("size", "UNKNOWN"),
            color=ai_result.get("color", "UNKNOWN"),
            design=ai_result.get("design"),
            material=ai_result.get("material"),
            era=parsed["era"],  # テキストから取得
            confidence=ai_result.get("confidence", 0.5),
        )

        # AI生成の説明文を一時的に保存（description_generatorで使用）
        features._description_text = ai_result.get("description_text", "")

        return features

    def _parse_category(self, category_str: str) -> Category:
        """
        カテゴリ文字列をEnumに変換する。

        Args:
            category_str: カテゴリ文字列

        Returns:
            Category: カテゴリEnum
        """
        category_map = {
            "トップス": Category.TOPS,
            "パンツ": Category.PANTS,
            "セットアップ": Category.SETUP,
        }
        return category_map.get(category_str, Category.TOPS)


# テスト用
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("使用法: python image_analyzer.py <画像パス> [補足テキスト]")
        sys.exit(1)

    image_path = sys.argv[1]
    user_text = sys.argv[2] if len(sys.argv) > 2 else ""

    print(f"画像: {image_path}")
    print(f"テキスト: {user_text}")
    print("-" * 40)

    analyzer = ImageAnalyzer()
    features = analyzer.analyze([image_path], user_text)

    print("=== 解析結果 ===")
    for key, value in features.to_dict().items():
        print(f"{key}: {value}")
