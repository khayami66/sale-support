"""
ユーザー修正反映モジュール

ユーザーからの修正入力を解析し、商品特徴に反映する。
"""
import re
from typing import Optional, Tuple

from models.product import ProductFeatures, Category, PricingStrategy


class FeatureRefiner:
    """
    ユーザー修正を反映するクラス

    確認サマリーに対する修正入力（例：「1 adidas」「3 パーカー」）を
    解析して、ProductFeaturesに反映する。
    """

    # 修正パターン: 番号 + 内容
    MODIFICATION_PATTERN = re.compile(r"^(\d+)\s+(.+)$")

    # 戦略パターン
    STRATEGY_PATTERNS = {
        PricingStrategy.HIGH_PROFIT: re.compile(r"^[Aa1]$|高利益"),
        PricingStrategy.BALANCED: re.compile(r"^[Bb2]$|バランス"),
        PricingStrategy.QUICK_SALE: re.compile(r"^[Cc3]$|回転"),
    }

    # フィールド番号とフィールド名のマッピング
    FIELD_MAPPING = {
        1: "brand",
        2: "category",
        3: "item_type",
        4: "gender",
        5: "size",
        6: "color",
        7: "design",
        8: "era",
    }

    # カテゴリ文字列のマッピング
    CATEGORY_MAPPING = {
        "トップス": Category.TOPS,
        "パンツ": Category.PANTS,
        "セットアップ": Category.SETUP,
    }

    @classmethod
    def parse_input(cls, text: str) -> Tuple[Optional[dict], Optional[PricingStrategy]]:
        """
        ユーザー入力を解析する。

        Args:
            text: ユーザー入力テキスト

        Returns:
            Tuple[Optional[dict], Optional[PricingStrategy]]:
                - 修正内容の辞書（フィールド名: 新しい値）
                - 選択された戦略（戦略が選択された場合）
        """
        text = text.strip()
        modifications = {}
        strategy = None

        # 複数行の場合は行ごとに処理
        lines = text.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 戦略のチェック
            for strat, pattern in cls.STRATEGY_PATTERNS.items():
                if pattern.search(line):
                    strategy = strat
                    continue

            # 修正のチェック
            match = cls.MODIFICATION_PATTERN.match(line)
            if match:
                field_num = int(match.group(1))
                value = match.group(2).strip()

                if field_num in cls.FIELD_MAPPING:
                    field_name = cls.FIELD_MAPPING[field_num]
                    modifications[field_name] = value

        return modifications if modifications else None, strategy

    @classmethod
    def apply_modifications(
        cls,
        features: ProductFeatures,
        modifications: dict,
    ) -> ProductFeatures:
        """
        修正をProductFeaturesに反映する。

        Args:
            features: 元の商品特徴
            modifications: 修正内容の辞書

        Returns:
            ProductFeatures: 修正が反映された商品特徴
        """
        for field_name, value in modifications.items():
            if field_name == "category":
                # カテゴリは特別処理
                if value in cls.CATEGORY_MAPPING:
                    features.category = cls.CATEGORY_MAPPING[value]
            elif field_name == "design":
                # デザインは「なし」「特になし」の場合はNoneに
                if value in ["なし", "特になし", "無し", "null", "None"]:
                    features.design = None
                else:
                    features.design = value
            elif hasattr(features, field_name):
                setattr(features, field_name, value)

        return features

    @classmethod
    def is_strategy_only(cls, text: str) -> bool:
        """
        入力が戦略選択のみかどうかを判定する。

        Args:
            text: ユーザー入力テキスト

        Returns:
            bool: 戦略選択のみの場合True
        """
        text = text.strip()

        # 単一行で戦略パターンにマッチするか
        for pattern in cls.STRATEGY_PATTERNS.values():
            if pattern.match(text):
                return True

        return False

    @classmethod
    def get_strategy(cls, text: str) -> Optional[PricingStrategy]:
        """
        テキストから戦略を取得する。

        Args:
            text: ユーザー入力テキスト

        Returns:
            Optional[PricingStrategy]: 戦略（見つからなければNone）
        """
        text = text.strip()

        for strategy, pattern in cls.STRATEGY_PATTERNS.items():
            if pattern.search(text):
                return strategy

        return None


# テスト用
if __name__ == "__main__":
    # テストケース
    test_cases = [
        "A",
        "B",
        "C",
        "1 adidas",
        "3 パーカー",
        "1 NIKE\n3 スウェット\nB",
        "高利益重視",
        "バランス",
        "回転重視",
    ]

    print("=== FeatureRefiner Test ===")
    for text in test_cases:
        print(f"\nInput: '{text}'")
        modifications, strategy = FeatureRefiner.parse_input(text)
        print(f"  Modifications: {modifications}")
        print(f"  Strategy: {strategy}")
        print(f"  Is strategy only: {FeatureRefiner.is_strategy_only(text)}")
