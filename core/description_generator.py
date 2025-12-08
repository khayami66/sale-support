"""
商品説明生成モジュール

テンプレートに商品情報を差し込んで商品説明を生成する。
商品名とハッシュタグの生成も担当する。
"""
from pathlib import Path
from typing import Optional

from models.product import Product, ProductFeatures, Measurements, Category
from integrations.openai_client import OpenAIClient


class DescriptionGenerator:
    """
    商品説明生成クラス

    テンプレートファイルを読み込み、商品情報を差し込んで説明文を生成する。
    """

    # テンプレートディレクトリのパス
    TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

    def __init__(self, openai_client: Optional[OpenAIClient] = None):
        """
        ジェネレーターを初期化する。

        Args:
            openai_client: OpenAIクライアント（商品名・ハッシュタグ生成に使用）
        """
        self.openai_client = openai_client or OpenAIClient()
        self._load_templates()

    def _load_templates(self):
        """テンプレートファイルを読み込む。"""
        self.templates = {}

        template_files = {
            Category.TOPS: "tops.txt",
            Category.PANTS: "pants.txt",
            Category.SETUP: "setup.txt",
        }

        for category, filename in template_files.items():
            template_path = self.TEMPLATE_DIR / filename
            if template_path.exists():
                with open(template_path, "r", encoding="utf-8") as f:
                    self.templates[category] = f.read()
            else:
                raise FileNotFoundError(f"テンプレートが見つかりません: {template_path}")

    def generate_description(
        self,
        features: ProductFeatures,
        measurements: Measurements,
        management_id: str,
        description_text: str = "",
    ) -> str:
        """
        商品説明を生成する。

        Args:
            features: 商品特徴
            measurements: 実寸データ
            management_id: 商品管理番号
            description_text: AI生成の説明文（テンプレートに挿入）

        Returns:
            str: 生成された商品説明
        """
        # テンプレートを取得
        template = self.templates.get(features.category)
        if not template:
            raise ValueError(f"カテゴリに対応するテンプレートがありません: {features.category}")

        # ハッシュタグを生成
        hashtags = self.generate_hashtags(features)
        hashtags_str = " ".join(hashtags)

        # 説明文がない場合はデフォルト
        if not description_text:
            description_text = self._get_default_description_text(features)

        # ブランド名の処理（UNKNOWNの場合は空にしない）
        brand_text = features.brand if features.brand != "UNKNOWN" else ""
        color_text = features.color if features.color != "UNKNOWN" else ""
        item_type_text = features.item_type if features.item_type != "UNKNOWN" else "アイテム"

        # 商品説明の冒頭部分を動的に生成
        # 例: "adidasのネイビージャケット" or "ネイビージャケット" or "ジャケット"
        if brand_text and color_text:
            brand_display = f"{brand_text}の{color_text}"
        elif brand_text:
            brand_display = brand_text + "の"
        elif color_text:
            brand_display = color_text
        else:
            brand_display = ""

        # テンプレートに値を差し込む
        description = template.format(
            brand=brand_display,
            color="",  # brandに統合したので空に
            item_type=item_type_text,
            description_text=description_text,
            # トップス用
            length=measurements.length or "-",
            width=measurements.width or "-",
            shoulder=measurements.shoulder or "-",
            sleeve=measurements.sleeve or "-",
            # パンツ用
            waist=measurements.waist or "-",
            inseam=measurements.inseam or "-",
            hem_width=measurements.hem_width or "-",
            rise=measurements.rise or "-",
            # 共通
            hashtags=hashtags_str,
            management_id=management_id,
        )

        return description

    def _get_default_description_text(self, features: ProductFeatures) -> str:
        """
        デフォルトの説明文を生成する。

        Args:
            features: 商品特徴

        Returns:
            str: デフォルト説明文
        """
        if features.design:
            return f"{features.design}がポイントのアイテムです。"
        else:
            return "シンプルで使いやすいアイテムです。"

    def generate_title(self, features: ProductFeatures) -> str:
        """
        商品名を生成する。

        Args:
            features: 商品特徴

        Returns:
            str: 商品名（40文字以内）
        """
        features_dict = features.to_dict()
        return self.openai_client.generate_title(features_dict)

    def generate_hashtags(self, features: ProductFeatures) -> list[str]:
        """
        ハッシュタグを生成する。

        Args:
            features: 商品特徴

        Returns:
            list[str]: ハッシュタグのリスト
        """
        features_dict = features.to_dict()
        return self.openai_client.generate_hashtags(features_dict)

    def generate_all(self, product: Product) -> Product:
        """
        商品の全情報（商品名、説明、ハッシュタグ）を生成する。

        Args:
            product: 商品データ（features, measurements, management_idが設定済み）

        Returns:
            Product: 生成された情報が追加された商品データ
        """
        # 説明文を取得（ImageAnalyzerで設定された場合）
        description_text = getattr(product.features, "_description_text", "")

        # 商品名を生成
        product.title = self.generate_title(product.features)

        # ハッシュタグを生成
        product.hashtags = self.generate_hashtags(product.features)

        # 商品説明を生成
        product.description = self.generate_description(
            features=product.features,
            measurements=product.measurements,
            management_id=product.management_id,
            description_text=description_text,
        )

        return product


# テスト用
if __name__ == "__main__":
    from models.product import Category

    # テスト用の商品特徴
    features = ProductFeatures(
        brand="adidas",
        category=Category.TOPS,
        item_type="パーカー",
        gender="メンズ",
        size="L",
        color="ネイビー",
        design="刺繍ロゴ",
    )

    # テスト用の実寸
    measurements = Measurements(
        length=66,
        width=55,
        shoulder=48,
        sleeve=60,
    )

    print("=== テンプレート読み込みテスト ===")
    try:
        generator = DescriptionGenerator()
        print("テンプレート読み込み成功")

        # 説明文生成（API呼び出しなし版）
        print("\n=== 説明文生成テスト（デフォルト説明文） ===")
        description = generator.generate_description(
            features=features,
            measurements=measurements,
            management_id="215",
            description_text="スポーツシーンでも普段着でも使えるデザインです。",
        )
        print(description)

    except Exception as e:
        print(f"エラー: {e}")
