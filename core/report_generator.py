"""
レポート生成モジュール

週次・月次の販売レポートを生成する。
スプレッドシートのデータを集計し、レポート用のデータを作成する。
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum


class ReportType(Enum):
    """レポートの種類"""
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class SalesSummary:
    """売上・利益サマリー"""
    sales_count: int = 0              # 売上件数
    total_sales: int = 0              # 総売上高
    total_purchase: int = 0           # 総仕入高
    total_shipping: int = 0           # 総送料
    total_commission: int = 0         # 総手数料
    net_profit: int = 0               # 純利益
    avg_profit_per_item: int = 0      # 平均利益/件


@dataclass
class InventoryStatus:
    """在庫状況"""
    start_inventory: int = 0          # 期初在庫数
    new_registrations: int = 0        # 新規登録数
    sold_count: int = 0               # 売却数
    end_inventory: int = 0            # 期末在庫数
    inventory_value: int = 0          # 在庫金額（仕入れ価格合計）


@dataclass
class CategoryAnalysis:
    """カテゴリ別分析"""
    category: str = ""                # カテゴリ名
    sales_count: int = 0              # 売上件数
    sales_amount: int = 0             # 売上金額
    profit: int = 0                   # 利益
    profit_rate: float = 0.0          # 利益率


@dataclass
class ComparisonData:
    """比較データ"""
    prev_sales_count: int = 0         # 前期売上件数
    prev_net_profit: int = 0          # 前期純利益
    sales_count_diff: int = 0         # 売上件数差分
    profit_diff: int = 0              # 利益差分
    cumulative_sales: int = 0         # 累計売上件数
    cumulative_profit: int = 0        # 累計純利益
    has_prev_data: bool = False       # 前期データがあるか


@dataclass
class Report:
    """レポート全体"""
    report_type: ReportType
    period_start: datetime
    period_end: datetime
    sheet_name: str
    sales_summary: SalesSummary = field(default_factory=SalesSummary)
    inventory: InventoryStatus = field(default_factory=InventoryStatus)
    categories: list[CategoryAnalysis] = field(default_factory=list)
    comparison: ComparisonData = field(default_factory=ComparisonData)
    generated_at: datetime = field(default_factory=datetime.now)


class ReportGenerator:
    """レポート生成クラス"""

    # スプレッドシートのカラムインデックス（0始まり）
    COL_MANAGEMENT_ID = 0       # 管理番号
    COL_REGISTERED_AT = 1       # 登録日時
    COL_IMAGE = 2               # 画像
    COL_PURCHASE_PRICE = 3      # 仕入れ価格
    COL_CATEGORY = 5            # カテゴリ
    COL_STATUS = 28             # ステータス
    COL_SALE_DATE = 29          # 販売日
    COL_SALE_PRICE = 30         # 実際の販売価格
    COL_SHIPPING_COST = 31      # 実際の送料
    COL_COMMISSION = 32         # 手数料
    COL_PROFIT = 33             # 利益

    def __init__(self, all_data: list[list], headers: list[str]):
        """
        初期化

        Args:
            all_data: スプレッドシートの全データ（ヘッダー除く）
            headers: ヘッダー行
        """
        self.all_data = all_data
        self.headers = headers
        self._update_column_indices()

    def _update_column_indices(self):
        """ヘッダーからカラムインデックスを動的に取得"""
        try:
            self.COL_MANAGEMENT_ID = self.headers.index("管理番号")
            self.COL_REGISTERED_AT = self.headers.index("登録日時")
            self.COL_IMAGE = self.headers.index("画像")
            self.COL_PURCHASE_PRICE = self.headers.index("仕入れ価格")
            self.COL_CATEGORY = self.headers.index("カテゴリ")
            self.COL_STATUS = self.headers.index("ステータス")
            self.COL_SALE_DATE = self.headers.index("販売日")
            self.COL_SALE_PRICE = self.headers.index("実際の販売価格")
            self.COL_SHIPPING_COST = self.headers.index("実際の送料")
            self.COL_COMMISSION = self.headers.index("手数料")
            self.COL_PROFIT = self.headers.index("利益")
        except ValueError as e:
            print(f"[WARNING] カラムが見つかりません: {e}")

    def generate_weekly_report(self, target_date: Optional[datetime] = None) -> Report:
        """
        週次レポートを生成する

        Args:
            target_date: 対象日（省略時は前週）

        Returns:
            Report: 週次レポート
        """
        if target_date is None:
            target_date = datetime.now()

        # 前週の月曜日〜日曜日を計算
        days_since_monday = target_date.weekday()
        # 前週の月曜日
        week_start = target_date - timedelta(days=days_since_monday + 7)
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        # 前週の日曜日
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)

        # シート名を生成（例: 週次_12月第3週）
        week_number = self._get_week_number_in_month(week_start)
        sheet_name = f"週次_{week_start.month}月第{week_number}週"

        return self._generate_report(
            report_type=ReportType.WEEKLY,
            period_start=week_start,
            period_end=week_end,
            sheet_name=sheet_name,
        )

    def generate_monthly_report(self, target_date: Optional[datetime] = None) -> Report:
        """
        月次レポートを生成する

        Args:
            target_date: 対象日（省略時は前月）

        Returns:
            Report: 月次レポート
        """
        if target_date is None:
            target_date = datetime.now()

        # 前月の1日〜末日を計算
        first_of_this_month = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = first_of_this_month - timedelta(seconds=1)
        month_start = month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # シート名を生成（例: 月次_2025年12月）
        sheet_name = f"月次_{month_start.year}年{month_start.month}月"

        return self._generate_report(
            report_type=ReportType.MONTHLY,
            period_start=month_start,
            period_end=month_end,
            sheet_name=sheet_name,
        )

    def _generate_report(
        self,
        report_type: ReportType,
        period_start: datetime,
        period_end: datetime,
        sheet_name: str,
    ) -> Report:
        """レポートを生成する共通処理"""
        report = Report(
            report_type=report_type,
            period_start=period_start,
            period_end=period_end,
            sheet_name=sheet_name,
        )

        # 各セクションのデータを計算
        report.sales_summary = self._calculate_sales_summary(period_start, period_end)
        report.inventory = self._calculate_inventory(period_start, period_end)
        report.categories = self._calculate_category_analysis(period_start, period_end)
        report.comparison = self._calculate_comparison(report_type, period_start, period_end, report.sales_summary)

        return report

    def _calculate_sales_summary(self, period_start: datetime, period_end: datetime) -> SalesSummary:
        """売上・利益サマリーを計算"""
        summary = SalesSummary()

        for row in self.all_data:
            sale_date = self._parse_date(self._get_cell(row, self.COL_SALE_DATE))
            if sale_date and period_start <= sale_date <= period_end:
                summary.sales_count += 1
                summary.total_sales += self._get_int(row, self.COL_SALE_PRICE)
                summary.total_purchase += self._get_int(row, self.COL_PURCHASE_PRICE)
                summary.total_shipping += self._get_int(row, self.COL_SHIPPING_COST)
                summary.total_commission += self._get_int(row, self.COL_COMMISSION)
                summary.net_profit += self._get_int(row, self.COL_PROFIT)

        if summary.sales_count > 0:
            summary.avg_profit_per_item = summary.net_profit // summary.sales_count

        return summary

    def _calculate_inventory(self, period_start: datetime, period_end: datetime) -> InventoryStatus:
        """在庫状況を計算"""
        inventory = InventoryStatus()

        for row in self.all_data:
            registered_at = self._parse_datetime(self._get_cell(row, self.COL_REGISTERED_AT))
            sale_date = self._parse_date(self._get_cell(row, self.COL_SALE_DATE))
            status = self._get_cell(row, self.COL_STATUS)
            purchase_price = self._get_int(row, self.COL_PURCHASE_PRICE)

            # 新規登録数（期間内に登録）
            if registered_at and period_start <= registered_at <= period_end:
                inventory.new_registrations += 1

            # 売却数（期間内に売却）
            if sale_date and period_start <= sale_date <= period_end:
                inventory.sold_count += 1

            # 期初在庫数（期間開始前に登録、かつ期間開始時点で未売却）
            if registered_at and registered_at < period_start:
                # 売却日が期間開始前でなければ期初在庫
                if sale_date is None or sale_date >= period_start:
                    inventory.start_inventory += 1

            # 期末在庫数（現在出品中）
            if status == "出品中":
                inventory.end_inventory += 1
                inventory.inventory_value += purchase_price

        return inventory

    def _calculate_category_analysis(self, period_start: datetime, period_end: datetime) -> list[CategoryAnalysis]:
        """カテゴリ別分析を計算"""
        category_data: dict[str, CategoryAnalysis] = {}

        for row in self.all_data:
            sale_date = self._parse_date(self._get_cell(row, self.COL_SALE_DATE))
            if sale_date and period_start <= sale_date <= period_end:
                category = self._get_cell(row, self.COL_CATEGORY) or "その他"
                sale_price = self._get_int(row, self.COL_SALE_PRICE)
                profit = self._get_int(row, self.COL_PROFIT)

                if category not in category_data:
                    category_data[category] = CategoryAnalysis(category=category)

                category_data[category].sales_count += 1
                category_data[category].sales_amount += sale_price
                category_data[category].profit += profit

        # 利益率を計算
        for cat in category_data.values():
            if cat.sales_amount > 0:
                cat.profit_rate = (cat.profit / cat.sales_amount) * 100

        return list(category_data.values())

    def _calculate_comparison(
        self,
        report_type: ReportType,
        period_start: datetime,
        period_end: datetime,
        current_summary: SalesSummary,
    ) -> ComparisonData:
        """比較データを計算"""
        comparison = ComparisonData()

        # 前期の期間を計算
        if report_type == ReportType.WEEKLY:
            prev_start = period_start - timedelta(days=7)
            prev_end = period_end - timedelta(days=7)
        else:
            # 前月
            prev_end = period_start - timedelta(seconds=1)
            prev_start = prev_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # 前期のデータを集計
        prev_summary = self._calculate_sales_summary(prev_start, prev_end)

        if prev_summary.sales_count > 0:
            comparison.has_prev_data = True
            comparison.prev_sales_count = prev_summary.sales_count
            comparison.prev_net_profit = prev_summary.net_profit
            comparison.sales_count_diff = current_summary.sales_count - prev_summary.sales_count
            comparison.profit_diff = current_summary.net_profit - prev_summary.net_profit

        # 累計を計算（システム導入時: 2025年12月から）
        cumulative_start = datetime(2025, 12, 1, 0, 0, 0)
        cumulative_summary = self._calculate_sales_summary(cumulative_start, period_end)
        comparison.cumulative_sales = cumulative_summary.sales_count
        comparison.cumulative_profit = cumulative_summary.net_profit

        return comparison

    def _get_week_number_in_month(self, date: datetime) -> int:
        """月内の週番号を取得（1始まり）"""
        first_day = date.replace(day=1)
        # 月の最初の月曜日を基準に週番号を計算
        first_monday = first_day + timedelta(days=(7 - first_day.weekday()) % 7)
        if date < first_monday:
            return 1
        return ((date - first_monday).days // 7) + 2

    def _get_cell(self, row: list, index: int) -> str:
        """セルの値を安全に取得"""
        if index < len(row):
            return str(row[index]).strip()
        return ""

    def _get_int(self, row: list, index: int) -> int:
        """セルの値を整数として取得"""
        value = self._get_cell(row, index)
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return 0

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """日付文字列をパース（YYYY-MM-DD形式）"""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return None

    def _parse_datetime(self, datetime_str: str) -> Optional[datetime]:
        """日時文字列をパース（YYYY-MM-DD HH:MM:SS形式）"""
        if not datetime_str:
            return None
        try:
            return datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None


def format_report_for_sheet(report: Report) -> list[list]:
    """
    レポートをスプレッドシート用のデータに変換

    Args:
        report: レポートデータ

    Returns:
        list[list]: スプレッドシートに書き込む2次元配列
    """
    rows = []

    # タイトル
    period_str = f"{report.period_start.strftime('%Y/%m/%d')} 〜 {report.period_end.strftime('%Y/%m/%d')}"
    report_type_str = "週次報告書" if report.report_type == ReportType.WEEKLY else "月次報告書"
    rows.append([f"【{report_type_str}】{period_str}"])
    rows.append([f"作成日時: {report.generated_at.strftime('%Y/%m/%d %H:%M')}"])
    rows.append([])

    # A. 売上・利益サマリー
    rows.append(["■ 売上・利益サマリー"])
    rows.append(["項目", "金額"])
    rows.append(["売上件数", f"{report.sales_summary.sales_count}件"])
    rows.append(["総売上高", f"¥{report.sales_summary.total_sales:,}"])
    rows.append(["総仕入高", f"¥{report.sales_summary.total_purchase:,}"])
    rows.append(["総送料", f"¥{report.sales_summary.total_shipping:,}"])
    rows.append(["総手数料", f"¥{report.sales_summary.total_commission:,}"])
    rows.append(["純利益", f"¥{report.sales_summary.net_profit:,}"])
    rows.append(["平均利益/件", f"¥{report.sales_summary.avg_profit_per_item:,}"])
    rows.append([])

    # B. 在庫状況
    rows.append(["■ 在庫状況"])
    rows.append(["項目", "数量"])
    rows.append(["期初在庫数", f"{report.inventory.start_inventory}件"])
    rows.append(["新規登録数", f"{report.inventory.new_registrations}件"])
    rows.append(["売却数", f"{report.inventory.sold_count}件"])
    rows.append(["期末在庫数", f"{report.inventory.end_inventory}件"])
    rows.append(["在庫金額", f"¥{report.inventory.inventory_value:,}"])
    rows.append([])

    # C. カテゴリ別分析
    rows.append(["■ カテゴリ別分析"])
    rows.append(["カテゴリ", "売上件数", "売上金額", "利益", "利益率"])
    for cat in report.categories:
        rows.append([
            cat.category,
            f"{cat.sales_count}件",
            f"¥{cat.sales_amount:,}",
            f"¥{cat.profit:,}",
            f"{cat.profit_rate:.1f}%",
        ])
    if not report.categories:
        rows.append(["（データなし）", "", "", "", ""])
    rows.append([])

    # D. 比較データ
    rows.append(["■ 比較データ"])
    prev_label = "前週" if report.report_type == ReportType.WEEKLY else "前月"

    if report.comparison.has_prev_data:
        diff_sales = report.comparison.sales_count_diff
        diff_profit = report.comparison.profit_diff
        sales_sign = "+" if diff_sales >= 0 else ""
        profit_sign = "+" if diff_profit >= 0 else ""

        rows.append(["項目", "今期", prev_label, "差分"])
        rows.append([
            "売上件数",
            f"{report.sales_summary.sales_count}件",
            f"{report.comparison.prev_sales_count}件",
            f"{sales_sign}{diff_sales}件",
        ])
        rows.append([
            "純利益",
            f"¥{report.sales_summary.net_profit:,}",
            f"¥{report.comparison.prev_net_profit:,}",
            f"{profit_sign}¥{diff_profit:,}",
        ])
    else:
        rows.append([f"{prev_label}比", "-（前期データなし）"])

    rows.append([])
    rows.append(["■ 累計（2025年12月〜）"])
    rows.append(["累計売上件数", f"{report.comparison.cumulative_sales}件"])
    rows.append(["累計純利益", f"¥{report.comparison.cumulative_profit:,}"])

    return rows


def get_line_notification_message(report: Report) -> str:
    """
    LINE通知用のメッセージを生成

    Args:
        report: レポートデータ

    Returns:
        str: LINE通知メッセージ
    """
    period_str = f"{report.period_start.strftime('%m/%d')}〜{report.period_end.strftime('%m/%d')}"

    if report.report_type == ReportType.WEEKLY:
        return f"【週次報告】\n{period_str}の報告書を作成しました。\nスプレッドシートをご確認ください。"
    else:
        month_str = f"{report.period_start.year}年{report.period_start.month}月"
        return f"【月次報告】\n{month_str}の報告書を作成しました。\nスプレッドシートをご確認ください。"
