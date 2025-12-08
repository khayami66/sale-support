"""
価格計算ロジック

仕入れ価格と戦略に基づいて価格提案を生成する。
v1ではAI推測ベース、v2以降で販売データを活用予定。
"""
from typing import Optional

from config import Config
from models.product import PriceSuggestion, PricingStrategy, ProductFeatures
from integrations.openai_client import OpenAIClient


class PricingCalculator:
    """
    価格計算クラス

    最低価格の計算と、戦略に基づく価格提案を行う。
    """

    def __init__(self, openai_client: Optional[OpenAIClient] = None):
        """
        計算機を初期化する。

        Args:
            openai_client: OpenAIクライアント（価格提案の生成に使用）
        """
        self.openai_client = openai_client or OpenAIClient()

    @staticmethod
    def calculate_minimum_price(purchase_price: int) -> int:
        """
        最低販売価格を計算する。

        計算式: (仕入価格 + 送料 + 最低利益) ÷ (1 - 手数料率)
        10円単位で切り上げ。

        Args:
            purchase_price: 仕入れ価格（円）

        Returns:
            int: 最低販売価格
        """
        return Config.calculate_minimum_price(purchase_price)

    def generate_price_suggestion(
        self,
        features: ProductFeatures,
        purchase_price: int,
        strategy: PricingStrategy,
    ) -> PriceSuggestion:
        """
        価格提案を生成する。

        Args:
            features: 商品特徴
            purchase_price: 仕入れ価格
            strategy: 価格戦略

        Returns:
            PriceSuggestion: 価格提案
        """
        # 最低価格を計算
        minimum_price = self.calculate_minimum_price(purchase_price)

        # 特徴を辞書に変換
        features_dict = features.to_dict()

        # AIに価格提案を生成させる
        pricing_result = self.openai_client.generate_pricing(
            features=features_dict,
            purchase_price=purchase_price,
            minimum_price=minimum_price,
            strategy=strategy.value,
        )

        # PriceSuggestionを構築
        return PriceSuggestion(
            minimum_price=minimum_price,
            start_price=pricing_result["start_price"],
            expected_price=pricing_result["expected_price"],
            lowest_acceptable=pricing_result["lowest_acceptable"],
            strategy=strategy,
            reasoning=pricing_result.get("reasoning", ""),
        )

    @staticmethod
    def parse_strategy(strategy_input: str) -> PricingStrategy:
        """
        ユーザー入力から価格戦略を解析する。

        Args:
            strategy_input: ユーザー入力（"A", "B", "C", "高利益重視"など）

        Returns:
            PricingStrategy: 価格戦略

        Raises:
            ValueError: 無効な入力の場合
        """
        strategy_input = strategy_input.strip().upper()

        # アルファベット入力
        if strategy_input in ["A", "1"]:
            return PricingStrategy.HIGH_PROFIT
        elif strategy_input in ["B", "2"]:
            return PricingStrategy.BALANCED
        elif strategy_input in ["C", "3"]:
            return PricingStrategy.QUICK_SALE

        # 日本語入力
        strategy_input_lower = strategy_input.lower()
        if "高利益" in strategy_input_lower:
            return PricingStrategy.HIGH_PROFIT
        elif "バランス" in strategy_input_lower:
            return PricingStrategy.BALANCED
        elif "回転" in strategy_input_lower:
            return PricingStrategy.QUICK_SALE

        raise ValueError(f"無効な戦略: {strategy_input}")


# テスト用
if __name__ == "__main__":
    # 最低価格のテスト
    test_prices = [500, 800, 1000, 1500, 2000]

    print("=== 最低価格計算テスト ===")
    for price in test_prices:
        min_price = PricingCalculator.calculate_minimum_price(price)
        print(f"仕入れ {price}円 → 最低販売価格 {min_price}円")

    print("\n=== 戦略パーステスト ===")
    test_inputs = ["A", "B", "C", "1", "2", "3", "高利益重視", "バランス", "回転重視"]
    for inp in test_inputs:
        try:
            strategy = PricingCalculator.parse_strategy(inp)
            print(f"'{inp}' → {strategy.value}")
        except ValueError as e:
            print(f"'{inp}' → エラー: {e}")
