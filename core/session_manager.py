"""
セッション管理モジュール

ユーザーごとの会話状態を管理する。
1ユーザー＝1商品ずつの処理を前提とする。
"""
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from config import Config
from models.product import Product, ProductFeatures, Measurements, PricingStrategy


class SessionState(Enum):
    """セッションの状態"""
    IDLE = "idle"                    # 待機中（新規入力待ち）
    COLLECTING = "collecting"        # 画像・テキスト収集中
    WAITING_MEASUREMENTS = "waiting_measurements"  # 実寸入力待ち
    CONFIRMING = "confirming"        # 確認待ち（修正・戦略選択待ち）
    GENERATING = "generating"        # 生成中


@dataclass
class UserSession:
    """
    ユーザーセッション

    1ユーザーの現在の処理状態を保持する。
    """
    user_id: str
    state: SessionState = SessionState.IDLE
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # 収集中のデータ
    image_paths: list[str] = field(default_factory=list)
    text_input: str = ""

    # パース済みデータ
    purchase_price: Optional[int] = None
    management_id: Optional[str] = None
    measurements: Optional[Measurements] = None
    gender: Optional[str] = None
    size: Optional[str] = None
    era: Optional[str] = None

    # AI推定結果
    features: Optional[ProductFeatures] = None
    description_text: str = ""  # AI生成の説明文
    detected_category: Optional[str] = None  # AI判定のカテゴリ（トップス/パンツ/セットアップ）

    # 最終生成結果
    product: Optional[Product] = None

    def is_expired(self) -> bool:
        """セッションが期限切れかどうか"""
        timeout_seconds = Config.SESSION_TIMEOUT_MINUTES * 60
        return (time.time() - self.updated_at) > timeout_seconds

    def touch(self) -> None:
        """最終更新時刻を更新"""
        self.updated_at = time.time()

    def reset(self) -> None:
        """セッションをリセット"""
        self.state = SessionState.IDLE
        self.image_paths = []
        self.text_input = ""
        self.purchase_price = None
        self.management_id = None
        self.measurements = None
        self.gender = None
        self.size = None
        self.era = None
        self.features = None
        self.description_text = ""
        self.detected_category = None
        self.product = None
        self.touch()

    def has_required_data(self) -> bool:
        """必須データが揃っているか"""
        return (
            len(self.image_paths) > 0
            and self.purchase_price is not None
            and self.management_id is not None
            and self.measurements is not None
        )

    def get_missing_data(self) -> list[str]:
        """不足しているデータのリスト"""
        missing = []
        if len(self.image_paths) == 0:
            missing.append("画像")
        if self.purchase_price is None:
            missing.append("仕入れ価格")
        if self.management_id is None:
            missing.append("商品管理番号")
        if self.measurements is None or not (
            self.measurements.has_tops_measurements()
            or self.measurements.has_pants_measurements()
        ):
            missing.append("実寸")
        return missing


class SessionManager:
    """
    セッション管理クラス

    全ユーザーのセッションを管理する。
    メモリ上に保持（サーバー再起動でリセット）。
    """

    def __init__(self):
        """セッションマネージャーを初期化"""
        self._sessions: dict[str, UserSession] = {}

    def get_session(self, user_id: str) -> UserSession:
        """
        ユーザーのセッションを取得する。
        存在しない場合は新規作成。

        Args:
            user_id: ユーザーID

        Returns:
            UserSession: ユーザーセッション
        """
        if user_id not in self._sessions:
            self._sessions[user_id] = UserSession(user_id=user_id)

        session = self._sessions[user_id]

        # 期限切れの場合はリセット
        if session.is_expired():
            session.reset()

        return session

    def update_session(self, session: UserSession) -> None:
        """
        セッションを更新する。

        Args:
            session: 更新するセッション
        """
        session.touch()
        self._sessions[session.user_id] = session

    def delete_session(self, user_id: str) -> None:
        """
        セッションを削除する。

        Args:
            user_id: ユーザーID
        """
        if user_id in self._sessions:
            del self._sessions[user_id]

    def cleanup_expired(self) -> int:
        """
        期限切れセッションをクリーンアップする。

        Returns:
            int: 削除したセッション数
        """
        expired_users = [
            user_id
            for user_id, session in self._sessions.items()
            if session.is_expired()
        ]

        for user_id in expired_users:
            del self._sessions[user_id]

        return len(expired_users)


# グローバルインスタンス
session_manager = SessionManager()
