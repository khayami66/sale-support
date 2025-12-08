"""
テキストパーサーのテスト

様々なフォーマットのテキスト入力をパースできることを確認する。
"""
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.text_parser import TextParser


def test_parse_measurements_standard():
    """標準フォーマットの実寸パース"""
    text = "実寸 着丈66 身幅55 肩幅48 袖丈60"
    result = TextParser.parse_measurements(text)

    assert result.length == 66
    assert result.width == 55
    assert result.shoulder == 48
    assert result.sleeve == 60


def test_parse_measurements_with_cm():
    """cmが付いている場合の実寸パース"""
    text = "着丈:66cm 身幅:55cm 肩幅:48cm 袖丈:60cm"
    result = TextParser.parse_measurements(text)

    assert result.length == 66
    assert result.width == 55
    assert result.shoulder == 48
    assert result.sleeve == 60


def test_parse_measurements_pants():
    """パンツの実寸パース"""
    text = "ウエスト64 股下64 裾幅13 股上28"
    result = TextParser.parse_measurements(text)

    assert result.waist == 64
    assert result.inseam == 64
    assert result.hem_width == 13
    assert result.rise == 28


def test_parse_measurements_multiline():
    """改行区切りの実寸パース"""
    text = """着丈66
身幅55
肩幅48
袖丈60"""
    result = TextParser.parse_measurements(text)

    assert result.length == 66
    assert result.width == 55
    assert result.shoulder == 48
    assert result.sleeve == 60


def test_parse_purchase_price():
    """仕入れ価格のパース"""
    test_cases = [
        ("仕入れ 814円", 814),
        ("仕入れ814", 814),
        ("仕入1000円", 1000),
        ("仕入 1500", 1500),
    ]

    for text, expected in test_cases:
        result = TextParser.parse_purchase_price(text)
        assert result == expected, f"Failed for '{text}': expected {expected}, got {result}"


def test_parse_management_id():
    """管理番号のパース"""
    test_cases = [
        ("商品管理番号：215", "215"),
        ("管理番号215", "215"),
        ("商品管理番号:100", "100"),
        ("管理No.300", "300"),
    ]

    for text, expected in test_cases:
        result = TextParser.parse_management_id(text)
        assert result == expected, f"Failed for '{text}': expected {expected}, got {result}"


def test_parse_gender():
    """性別のパース"""
    test_cases = [
        ("メンズ L", "メンズ"),
        ("レディース M", "レディース"),
        ("ユニセックス", "ユニセックス"),
        ("男性用", "メンズ"),
        ("女性", "レディース"),
    ]

    for text, expected in test_cases:
        result = TextParser.parse_gender(text)
        assert result == expected, f"Failed for '{text}': expected {expected}, got {result}"


def test_parse_size():
    """サイズのパース"""
    test_cases = [
        ("メンズ L", "L"),
        ("サイズ XL", "XL"),
        ("M サイズ", "M"),
        ("フリーサイズ", "フリー"),
        ("FREE", "フリー"),
    ]

    for text, expected in test_cases:
        result = TextParser.parse_size(text)
        assert result == expected, f"Failed for '{text}': expected {expected}, got {result}"


def test_parse_era():
    """年代のパース"""
    test_cases = [
        ("90s ビンテージ", "90s"),
        ("80s", "80s"),
        ("2000年代", "2000年代"),
        ("90年代", "90s"),
    ]

    for text, expected in test_cases:
        result = TextParser.parse_era(text)
        assert result == expected, f"Failed for '{text}': expected {expected}, got {result}"


def test_parse_all():
    """全項目のパース"""
    text = """仕入れ 814円 メンズ L 90s
実寸 着丈66 身幅55 肩幅48 袖丈60
商品管理番号：215"""

    result = TextParser.parse_all(text)

    assert result['purchase_price'] == 814
    assert result['management_id'] == "215"
    assert result['gender'] == "メンズ"
    assert result['size'] == "L"
    assert result['era'] == "90s"
    assert result['measurements'].length == 66
    assert result['measurements'].width == 55
    assert result['measurements'].shoulder == 48
    assert result['measurements'].sleeve == 60


def run_tests():
    """全テストを実行"""
    tests = [
        test_parse_measurements_standard,
        test_parse_measurements_with_cm,
        test_parse_measurements_pants,
        test_parse_measurements_multiline,
        test_parse_purchase_price,
        test_parse_management_id,
        test_parse_gender,
        test_parse_size,
        test_parse_era,
        test_parse_all,
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
