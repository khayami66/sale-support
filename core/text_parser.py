"""
テキストパーサー

LINEから送られてくるテキストメッセージをパースして、
実寸・仕入れ価格・管理番号などを抽出する。

様々なフォーマットに柔軟に対応する。
"""
import re
from typing import Optional
from models.product import Measurements


class TextParser:
    """
    テキスト入力のパーサー

    以下のような様々なフォーマットに対応：
    - 「実寸 着丈66 身幅55 肩幅48 袖丈60」
    - 「着丈:66cm 身幅:55cm」
    - 「着丈66\\n身幅55」（改行区切り）
    """

    # 数値抽出用パターン（数字のみ取り出す）
    NUMBER_PATTERN = re.compile(r"(\d+)")

    # 各項目のキーワードパターン
    MEASUREMENT_PATTERNS = {
        # トップス
        "length": re.compile(r"着丈[:\s：]*(\d+)", re.IGNORECASE),
        "width": re.compile(r"身幅[:\s：]*(\d+)", re.IGNORECASE),
        "shoulder": re.compile(r"肩幅[:\s：]*(\d+)", re.IGNORECASE),
        "sleeve": re.compile(r"袖丈[:\s：]*(\d+)", re.IGNORECASE),
        # パンツ
        "waist": re.compile(r"ウエスト[:\s：]*(\d+)", re.IGNORECASE),
        "inseam": re.compile(r"股下[:\s：]*(\d+)", re.IGNORECASE),
        "hem_width": re.compile(r"裾幅[:\s：]*(\d+)", re.IGNORECASE),
        "rise": re.compile(r"股上[:\s：]*(\d+)", re.IGNORECASE),
    }

    # 仕入れ価格パターン
    PURCHASE_PRICE_PATTERNS = [
        re.compile(r"仕入れ?価格?[:\s：\u3000]*(\d+)円?", re.IGNORECASE),
        re.compile(r"仕入[:\s：\u3000]*(\d+)円?", re.IGNORECASE),
        re.compile(r"購入価格?[:\s：\u3000]*(\d+)円?", re.IGNORECASE),
        re.compile(r"原価[:\s：\u3000]*(\d+)円?", re.IGNORECASE),
    ]

    # 管理番号パターン
    MANAGEMENT_ID_PATTERNS = [
        re.compile(r"(?:商品)?管理番号[:\s：]*(\d+)", re.IGNORECASE),
        re.compile(r"管理No[.:\s：]*(\d+)", re.IGNORECASE),
        re.compile(r"ID[:\s：]*(\d+)", re.IGNORECASE),
    ]

    # 性別パターン
    GENDER_PATTERNS = {
        "メンズ": re.compile(r"メンズ|男性|MEN", re.IGNORECASE),
        "レディース": re.compile(r"レディース|女性|WOMEN|LADIES", re.IGNORECASE),
        "ユニセックス": re.compile(r"ユニセックス|男女兼用|UNISEX", re.IGNORECASE),
    }

    # サイズパターン（日本語の「フリーサイズ」にも対応）
    SIZE_PATTERNS = [
        re.compile(r"フリーサイズ|フリー", re.IGNORECASE),  # フリーサイズを先にチェック
        re.compile(r"\b(XXS|XS|S|M|L|XL|XXL|2XL|3XL|FREE|F)\b", re.IGNORECASE),
    ]

    # 年代パターン
    ERA_PATTERNS = [
        re.compile(r"(\d{2})s", re.IGNORECASE),  # 90s, 80s
        re.compile(r"(\d{4})年代", re.IGNORECASE),  # 2000年代
        re.compile(r"(\d{2})年代", re.IGNORECASE),  # 90年代
    ]

    @classmethod
    def parse_measurements(cls, text: str) -> Measurements:
        """
        テキストから実寸データを抽出する。

        Args:
            text: ユーザー入力テキスト

        Returns:
            Measurements: 抽出された実寸データ
        """
        measurements = Measurements()

        for field_name, pattern in cls.MEASUREMENT_PATTERNS.items():
            match = pattern.search(text)
            if match:
                value = int(match.group(1))
                setattr(measurements, field_name, value)

        return measurements

    @classmethod
    def parse_purchase_price(cls, text: str) -> Optional[int]:
        """
        テキストから仕入れ価格を抽出する。

        Args:
            text: ユーザー入力テキスト

        Returns:
            Optional[int]: 仕入れ価格（見つからなければNone）
        """
        for pattern in cls.PURCHASE_PRICE_PATTERNS:
            match = pattern.search(text)
            if match:
                return int(match.group(1))
        return None

    @classmethod
    def parse_management_id(cls, text: str) -> Optional[str]:
        """
        テキストから商品管理番号を抽出する。

        Args:
            text: ユーザー入力テキスト

        Returns:
            Optional[str]: 管理番号（見つからなければNone）
        """
        for pattern in cls.MANAGEMENT_ID_PATTERNS:
            match = pattern.search(text)
            if match:
                return match.group(1)
        return None

    @classmethod
    def parse_gender(cls, text: str) -> Optional[str]:
        """
        テキストから性別を抽出する。

        Args:
            text: ユーザー入力テキスト

        Returns:
            Optional[str]: 性別（見つからなければNone）
        """
        for gender, pattern in cls.GENDER_PATTERNS.items():
            if pattern.search(text):
                return gender
        return None

    @classmethod
    def parse_size(cls, text: str) -> Optional[str]:
        """
        テキストからサイズを抽出する。

        Args:
            text: ユーザー入力テキスト

        Returns:
            Optional[str]: サイズ（見つからなければNone）
        """
        for pattern in cls.SIZE_PATTERNS:
            match = pattern.search(text)
            if match:
                # グループがある場合はグループを取得
                if match.lastindex:
                    size = match.group(1).upper()
                else:
                    size = match.group(0)

                # フリーサイズの正規化
                if size.upper() in ["FREE", "F"] or "フリー" in size:
                    return "フリー"
                return size.upper()
        return None

    @classmethod
    def parse_era(cls, text: str) -> Optional[str]:
        """
        テキストから年代を抽出する。

        Args:
            text: ユーザー入力テキスト

        Returns:
            Optional[str]: 年代（見つからなければNone）
        """
        for pattern in cls.ERA_PATTERNS:
            match = pattern.search(text)
            if match:
                value = match.group(1)
                # 2桁の場合は「90s」形式に
                if len(value) == 2:
                    return f"{value}s"
                # 4桁の場合は「2000年代」形式に
                elif len(value) == 4:
                    return f"{value}年代"
        return None

    @classmethod
    def parse_all(cls, text: str) -> dict:
        """
        テキストから全ての情報を抽出する。

        Args:
            text: ユーザー入力テキスト

        Returns:
            dict: 抽出された全情報
        """
        return {
            "measurements": cls.parse_measurements(text),
            "purchase_price": cls.parse_purchase_price(text),
            "management_id": cls.parse_management_id(text),
            "gender": cls.parse_gender(text),
            "size": cls.parse_size(text),
            "era": cls.parse_era(text),
            "raw_text": text,
        }


    @classmethod
    def parse_simple_numbers(cls, text: str, count: int) -> list[Optional[int]]:
        """
        スペース区切りの数値を抽出する（シンプル入力用）。

        Args:
            text: ユーザー入力テキスト
            count: 期待する数値の数

        Returns:
            list[Optional[int]]: 抽出された数値のリスト
        """
        # 全角数字を半角に変換
        text = text.translate(str.maketrans('０１２３４５６７８９', '0123456789'))

        # 全角スペースを半角に変換
        text = text.replace('\u3000', ' ')

        # 数値を抽出
        numbers = re.findall(r'\d+', text)

        # 指定された数だけ返す（足りない場合はNone）
        result = []
        for i in range(count):
            if i < len(numbers):
                result.append(int(numbers[i]))
            else:
                result.append(None)

        return result

    @classmethod
    def parse_price_and_id(cls, text: str) -> tuple[Optional[int], Optional[str]]:
        """
        シンプル入力から仕入れ価格と管理番号を抽出する。
        「880 222」のような形式に対応。

        Args:
            text: ユーザー入力テキスト

        Returns:
            tuple: (仕入れ価格, 管理番号)
        """
        numbers = cls.parse_simple_numbers(text, 2)
        purchase_price = numbers[0]
        management_id = str(numbers[1]) if numbers[1] is not None else None
        return purchase_price, management_id

    @classmethod
    def parse_measurements_simple(cls, text: str, category: str) -> Measurements:
        """
        シンプル入力から実寸を抽出する。
        カテゴリに応じて異なる項目を期待する。

        Args:
            text: ユーザー入力テキスト（例: "60 50 42 20"）
            category: カテゴリ（トップス/パンツ/セットアップ）

        Returns:
            Measurements: 抽出された実寸データ
        """
        measurements = Measurements()

        if category == "パンツ":
            # パンツ: ウエスト 股下 裾幅 股上
            numbers = cls.parse_simple_numbers(text, 4)
            measurements.waist = numbers[0]
            measurements.inseam = numbers[1]
            measurements.hem_width = numbers[2]
            measurements.rise = numbers[3]
        elif category == "セットアップ":
            # セットアップ: 着丈 身幅 肩幅 袖丈 ウエスト 股下 裾幅 股上
            numbers = cls.parse_simple_numbers(text, 8)
            measurements.length = numbers[0]
            measurements.width = numbers[1]
            measurements.shoulder = numbers[2]
            measurements.sleeve = numbers[3]
            measurements.waist = numbers[4]
            measurements.inseam = numbers[5]
            measurements.hem_width = numbers[6]
            measurements.rise = numbers[7]
        else:
            # トップス: 着丈 身幅 肩幅 袖丈
            numbers = cls.parse_simple_numbers(text, 4)
            measurements.length = numbers[0]
            measurements.width = numbers[1]
            measurements.shoulder = numbers[2]
            measurements.sleeve = numbers[3]

        return measurements


# テスト用
if __name__ == "__main__":
    # テストケース
    test_cases = [
        "仕入れ 814円 メンズ L\n実寸 着丈66 身幅55 肩幅48 袖丈60\n商品管理番号：215",
        "仕入れ1000 レディース M 90s\n着丈:70cm 身幅:50cm 肩幅:45cm 袖丈:58cm\n管理番号123",
        "仕入1500円 ユニセックス フリー\nウエスト64 股下64 裾幅13 股上28\n商品管理番号：300",
    ]

    for i, text in enumerate(test_cases, 1):
        print(f"\n=== テストケース {i} ===")
        print(f"入力: {text}")
        print("-" * 40)
        result = TextParser.parse_all(text)
        print(f"仕入れ価格: {result['purchase_price']}")
        print(f"管理番号: {result['management_id']}")
        print(f"性別: {result['gender']}")
        print(f"サイズ: {result['size']}")
        print(f"年代: {result['era']}")
        print(f"実寸: {result['measurements'].to_dict()}")
