"""
商品データモデル

商品情報を構造化して扱うためのデータクラスを定義する。
dataclassを使用することで、型ヒントと初期化を簡潔に書ける。
"""
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class Category(Enum):
    """商品カテゴリ"""
    TOPS = "トップス"
    PANTS = "パンツ"
    SETUP = "セットアップ"


class PricingStrategy(Enum):
    """価格戦略"""
    HIGH_PROFIT = "高利益重視"
    BALANCED = "バランス"
    QUICK_SALE = "回転重視"


@dataclass
class Measurements:
    """
    実寸データ

    トップス用: 着丈、身幅、肩幅、袖丈
    パンツ用: ウエスト、股下、裾幅、股上
    セットアップ用: 両方
    """
    # トップス用
    length: Optional[int] = None       # 着丈
    width: Optional[int] = None        # 身幅
    shoulder: Optional[int] = None     # 肩幅
    sleeve: Optional[int] = None       # 袖丈

    # パンツ用
    waist: Optional[int] = None        # ウエスト
    inseam: Optional[int] = None       # 股下
    hem_width: Optional[int] = None    # 裾幅
    rise: Optional[int] = None         # 股上

    def has_tops_measurements(self) -> bool:
        """トップスの実寸が揃っているか"""
        return all([self.length, self.width, self.shoulder, self.sleeve])

    def has_pants_measurements(self) -> bool:
        """パンツの実寸が揃っているか"""
        return all([self.waist, self.inseam, self.hem_width, self.rise])

    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            "着丈": self.length,
            "身幅": self.width,
            "肩幅": self.shoulder,
            "袖丈": self.sleeve,
            "ウエスト": self.waist,
            "股下": self.inseam,
            "裾幅": self.hem_width,
            "股上": self.rise,
        }


@dataclass
class ProductFeatures:
    """
    AI推定による商品特徴

    画像解析の結果を構造化して保持する。
    不明な項目は "UNKNOWN" または None となる。
    """
    brand: str = "UNKNOWN"                    # ブランド名
    category: Category = Category.TOPS        # カテゴリ
    item_type: str = "UNKNOWN"                # アイテム種別（パーカー、スウェット等）
    gender: str = "UNKNOWN"                   # 性別（メンズ/レディース/ユニセックス）
    size: str = "UNKNOWN"                     # サイズ
    color: str = "UNKNOWN"                    # 色
    design: Optional[str] = None              # デザイン特徴（刺繍/プリント/無地等）
    material: Optional[str] = None            # 素材（タグから読み取れた場合のみ）
    era: Optional[str] = None                 # 年代（90s, 2000年代等）
    condition: str = "目立った傷や汚れなし"    # 状態
    confidence: float = 0.0                   # AI推定の確信度（0.0〜1.0）

    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            "brand": self.brand,
            "category": self.category.value,
            "item_type": self.item_type,
            "gender": self.gender,
            "size": self.size,
            "color": self.color,
            "design": self.design,
            "material": self.material,
            "era": self.era,
            "condition": self.condition,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProductFeatures":
        """辞書からインスタンスを生成"""
        category_str = data.get("category", "トップス")
        category = Category.TOPS
        for cat in Category:
            if cat.value == category_str:
                category = cat
                break

        return cls(
            brand=data.get("brand", "UNKNOWN"),
            category=category,
            item_type=data.get("item_type", "UNKNOWN"),
            gender=data.get("gender", "UNKNOWN"),
            size=data.get("size", "UNKNOWN"),
            color=data.get("color", "UNKNOWN"),
            design=data.get("design"),
            material=data.get("material"),
            era=data.get("era"),
            condition=data.get("condition", "目立った傷や汚れなし"),
            confidence=data.get("confidence", 0.0),
        )


@dataclass
class PriceSuggestion:
    """
    価格提案

    戦略に基づいて計算された3種類の価格を保持する。
    """
    minimum_price: int              # 最低価格（これ以下では売らない）
    start_price: int                # スタート価格（出品時の価格）
    expected_price: int             # 想定販売価格
    lowest_acceptable: int          # 値下げ許容ライン
    strategy: PricingStrategy       # 選択された戦略
    reasoning: str = ""             # 価格設定の理由（AIからのコメント）

    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            "minimum_price": self.minimum_price,
            "start_price": self.start_price,
            "expected_price": self.expected_price,
            "lowest_acceptable": self.lowest_acceptable,
            "strategy": self.strategy.value,
            "reasoning": self.reasoning,
        }


@dataclass
class Product:
    """
    商品データ全体

    LINEから受け取った情報、AI推定結果、生成された出品情報をすべて保持する。
    """
    # ユーザー入力情報
    management_id: str                           # 商品管理番号
    purchase_price: int                          # 仕入れ価格
    measurements: Measurements                   # 実寸

    # AI推定情報
    features: ProductFeatures = field(default_factory=ProductFeatures)

    # 生成された出品情報
    title: str = ""                              # 商品名（40字以内）
    description: str = ""                        # 商品説明
    hashtags: list[str] = field(default_factory=list)  # ハッシュタグ
    price_suggestion: Optional[PriceSuggestion] = None  # 価格提案

    # メタ情報
    image_paths: list[str] = field(default_factory=list)  # 画像パス
    raw_text: str = ""                           # 元のテキスト入力

    def to_dict(self) -> dict:
        """辞書形式に変換（JSON出力用）"""
        return {
            "management_id": self.management_id,
            "purchase_price": self.purchase_price,
            "measurements": self.measurements.to_dict(),
            "features": self.features.to_dict(),
            "title": self.title,
            "description": self.description,
            "hashtags": self.hashtags,
            "price_suggestion": self.price_suggestion.to_dict() if self.price_suggestion else None,
            "image_paths": self.image_paths,
        }

    def get_confirmation_summary(self) -> str:
        """
        確認用サマリーを生成する（LINE返信用）

        Returns:
            str: 番号付きの確認項目リスト
        """
        lines = [
            f"1. ブランド：{self.features.brand}",
            f"2. カテゴリ：{self.features.category.value}",
            f"3. アイテム：{self.features.item_type}",
            f"4. 性別：{self.features.gender}",
            f"5. サイズ：{self.features.size}",
            f"6. 色：{self.features.color}",
            f"7. デザイン：{self.features.design or '特になし'}",
        ]

        if self.features.era:
            lines.append(f"8. 年代：{self.features.era}")

        lines.append("")
        lines.append("戦略を選択してください：")
        lines.append("A. 高利益重視")
        lines.append("B. バランス")
        lines.append("C. 回転重視")

        return "\n".join(lines)
