"""
価格計算ロジックのテスト

最低価格の計算と戦略パースをテストする。
"""
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.pricing import PricingCalculator
from models.product import PricingStrategy


def test_calculate_minimum_price():
    """最低価格の計算テスト"""
    # 計算式: (仕入価格 + 送料500 + 最低利益200) ÷ 0.9
    test_cases = [
        # (仕入れ価格, 期待される最低価格)
        # 800円の場合: (800 + 500 + 200) / 0.9 = 1666.67 → 1670円（10円単位切り上げ）
        (800, 1670),
        # 500円の場合: (500 + 500 + 200) / 0.9 = 1333.33 → 1340円
        (500, 1340),
        # 1000円の場合: (1000 + 500 + 200) / 0.9 = 1888.89 → 1890円
        (1000, 1890),
        # 1500円の場合: (1500 + 500 + 200) / 0.9 = 2444.44 → 2450円
        (1500, 2450),
        # 2000円の場合: (2000 + 500 + 200) / 0.9 = 3000.00 → 3000円
        (2000, 3000),
    ]

    for purchase_price, expected in test_cases:
        result = PricingCalculator.calculate_minimum_price(purchase_price)
        assert result == expected, f"仕入れ{purchase_price}円: 期待値{expected}円, 実際{result}円"


def test_parse_strategy_alphabet():
    """アルファベットでの戦略パース"""
    test_cases = [
        ("A", PricingStrategy.HIGH_PROFIT),
        ("a", PricingStrategy.HIGH_PROFIT),
        ("B", PricingStrategy.BALANCED),
        ("b", PricingStrategy.BALANCED),
        ("C", PricingStrategy.QUICK_SALE),
        ("c", PricingStrategy.QUICK_SALE),
    ]

    for input_str, expected in test_cases:
        result = PricingCalculator.parse_strategy(input_str)
        assert result == expected, f"入力'{input_str}': 期待値{expected}, 実際{result}"


def test_parse_strategy_number():
    """数字での戦略パース"""
    test_cases = [
        ("1", PricingStrategy.HIGH_PROFIT),
        ("2", PricingStrategy.BALANCED),
        ("3", PricingStrategy.QUICK_SALE),
    ]

    for input_str, expected in test_cases:
        result = PricingCalculator.parse_strategy(input_str)
        assert result == expected, f"入力'{input_str}': 期待値{expected}, 実際{result}"


def test_parse_strategy_japanese():
    """日本語での戦略パース"""
    test_cases = [
        ("高利益重視", PricingStrategy.HIGH_PROFIT),
        ("高利益", PricingStrategy.HIGH_PROFIT),
        ("バランス", PricingStrategy.BALANCED),
        ("回転重視", PricingStrategy.QUICK_SALE),
        ("回転", PricingStrategy.QUICK_SALE),
    ]

    for input_str, expected in test_cases:
        result = PricingCalculator.parse_strategy(input_str)
        assert result == expected, f"入力'{input_str}': 期待値{expected}, 実際{result}"


def test_parse_strategy_invalid():
    """無効な入力のテスト"""
    invalid_inputs = ["D", "4", "無効", "xyz", ""]

    for input_str in invalid_inputs:
        try:
            PricingCalculator.parse_strategy(input_str)
            assert False, f"'{input_str}'でValueErrorが発生するべき"
        except ValueError:
            pass  # 期待通り


def run_tests():
    """全テストを実行"""
    tests = [
        test_calculate_minimum_price,
        test_parse_strategy_alphabet,
        test_parse_strategy_number,
        test_parse_strategy_japanese,
        test_parse_strategy_invalid,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            print(f"[PASS] {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: unexpected error - {e}")
            failed += 1

    print(f"\nResult: {passed}/{len(tests)} tests passed")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
