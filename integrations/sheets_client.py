"""
Google Sheets連携クライアント

商品情報をGoogleスプレッドシートに保存する。
gspreadライブラリを使用してGoogle Sheets APIと連携する。
"""
import json
from datetime import datetime
from typing import Optional

import gspread
from gspread.utils import rowcol_to_a1
from gspread_formatting import CellFormat, Color, format_cell_range
from google.oauth2.service_account import Credentials

from config import Config
from models.product import Product


class SheetsClient:
    """Google Sheets連携クライアント"""

    # 認証に必要なスコープ
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    # スプレッドシートのヘッダー（カラム順序）
    HEADERS = [
        "管理番号",
        "登録日時",
        "画像",            # Cloudinaryにアップロードした画像
        "仕入れ価格",
        "ブランド",
        "カテゴリ",
        "アイテム",
        "性別",
        "サイズ",
        "色",
        "デザイン特徴",
        "年代",
        "戦略",
        "商品名",
        "ハッシュタグ",
        "スタート価格",
        "想定販売価格",
        "値下げ許容ライン",
        "最低価格",
        "実寸_着丈",
        "実寸_身幅",
        "実寸_肩幅",
        "実寸_袖丈",
        "実寸_ウエスト",
        "実寸_股下",
        "実寸_裾幅",
        "実寸_股上",
        # 販売管理カラム
        "ステータス",
        "販売日",
        "実際の販売価格",
        "実際の送料",
        "手数料",
        "利益",
    ]

    def __init__(self):
        """クライアントを初期化する"""
        self._client: Optional[gspread.Client] = None
        self._spreadsheet: Optional[gspread.Spreadsheet] = None
        self._worksheet: Optional[gspread.Worksheet] = None

    def _get_credentials(self) -> Credentials:
        """認証情報を取得する"""
        credentials_json = Config.GOOGLE_SHEETS_CREDENTIALS
        if not credentials_json:
            raise ValueError("GOOGLE_SHEETS_CREDENTIALS環境変数が設定されていません")

        credentials_dict = json.loads(credentials_json)
        return Credentials.from_service_account_info(
            credentials_dict,
            scopes=self.SCOPES,
        )

    def _get_client(self) -> gspread.Client:
        """gspreadクライアントを取得する（遅延初期化）"""
        if self._client is None:
            credentials = self._get_credentials()
            self._client = gspread.authorize(credentials)
        return self._client

    def _get_spreadsheet(self) -> gspread.Spreadsheet:
        """スプレッドシートを取得する（遅延初期化）"""
        if self._spreadsheet is None:
            spreadsheet_id = Config.SPREADSHEET_ID
            if not spreadsheet_id:
                raise ValueError("SPREADSHEET_ID環境変数が設定されていません")

            client = self._get_client()
            self._spreadsheet = client.open_by_key(spreadsheet_id)
        return self._spreadsheet

    def _get_worksheet(self) -> gspread.Worksheet:
        """ワークシートを取得する（最初のシートを使用）"""
        if self._worksheet is None:
            spreadsheet = self._get_spreadsheet()
            self._worksheet = spreadsheet.sheet1
            self._ensure_headers()
        return self._worksheet

    def _ensure_headers(self):
        """ヘッダー行が存在しない場合は追加する。不足カラムがあれば追加する。"""
        worksheet = self._worksheet
        if worksheet is None:
            return

        # 1行目を取得
        first_row = worksheet.row_values(1)

        # ヘッダーがなければ追加
        if not first_row or first_row[0] != self.HEADERS[0]:
            worksheet.insert_row(self.HEADERS, 1)
        elif len(first_row) < len(self.HEADERS):
            # グリッドのカラム数を確認し、必要なら拡張
            current_cols = worksheet.col_count
            required_cols = len(self.HEADERS)
            if current_cols < required_cols:
                cols_to_add = required_cols - current_cols
                worksheet.add_cols(cols_to_add)
                print(f"[INFO] グリッドを拡張: {current_cols}列 → {required_cols}列")

            # 不足しているヘッダーを追加
            missing_headers = self.HEADERS[len(first_row):]
            start_col = len(first_row) + 1
            for i, header in enumerate(missing_headers):
                worksheet.update_cell(1, start_col + i, header)
            print(f"[INFO] 不足カラムを追加しました: {missing_headers}")

    def save_product(self, product: Product) -> bool:
        """
        商品データをスプレッドシートに保存する。

        Args:
            product: 保存する商品データ

        Returns:
            bool: 保存成功時はTrue、失敗時はFalse
        """
        try:
            worksheet = self._get_worksheet()
            row_data = self._product_to_row(product)
            worksheet.append_row(row_data, value_input_option="USER_ENTERED")

            # 画像がある場合は行の高さを調整
            if product.image_url:
                self._set_row_height_for_image(worksheet)

            return True
        except Exception as e:
            print(f"スプレッドシートへの保存に失敗しました: {e}")
            return False

    def _set_row_height_for_image(self, worksheet: gspread.Worksheet, height_px: int = 110):
        """
        最後の行の高さを画像サイズに合わせて調整する。

        Args:
            worksheet: ワークシート
            height_px: 行の高さ（ピクセル）
        """
        try:
            # 最後の行番号を取得
            last_row = len(worksheet.get_all_values())

            # Sheets APIで行の高さを設定
            spreadsheet = self._get_spreadsheet()
            spreadsheet.batch_update({
                "requests": [{
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": worksheet.id,
                            "dimension": "ROWS",
                            "startIndex": last_row - 1,  # 0-based index
                            "endIndex": last_row
                        },
                        "properties": {
                            "pixelSize": height_px
                        },
                        "fields": "pixelSize"
                    }
                }]
            })
            print(f"[INFO] 行 {last_row} の高さを {height_px}px に設定しました")
        except Exception as e:
            print(f"[WARNING] 行の高さ調整に失敗しました: {e}")

    def _product_to_row(self, product: Product) -> list:
        """
        商品データを行データに変換する。

        Args:
            product: 変換する商品データ

        Returns:
            list: スプレッドシートの行データ
        """
        features = product.features
        measurements = product.measurements
        price = product.price_suggestion

        # ハッシュタグをスペース区切りの文字列に変換
        hashtags_str = " ".join(product.hashtags) if product.hashtags else ""

        # 画像URLがあればIMAGE関数を使用（モード4: 幅100px、高さ100pxで表示）
        image_formula = ""
        if product.image_url:
            image_formula = f'=IMAGE("{product.image_url}", 4, 100, 100)'

        return [
            product.management_id,                                    # 管理番号
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),            # 登録日時
            image_formula,                                            # 画像（IMAGE関数）
            product.purchase_price,                                   # 仕入れ価格
            features.brand,                                           # ブランド
            features.category.value,                                  # カテゴリ
            features.item_type,                                       # アイテム
            features.gender,                                          # 性別
            features.size,                                            # サイズ
            features.color,                                           # 色
            features.design or "",                                    # デザイン特徴
            features.era or "",                                       # 年代
            price.strategy.value if price else "",                    # 戦略
            product.title,                                            # 商品名
            hashtags_str,                                             # ハッシュタグ
            price.start_price if price else "",                       # スタート価格
            price.expected_price if price else "",                    # 想定販売価格
            price.lowest_acceptable if price else "",                 # 値下げ許容ライン
            price.minimum_price if price else "",                     # 最低価格
            measurements.length or "",                                # 実寸_着丈
            measurements.width or "",                                 # 実寸_身幅
            measurements.shoulder or "",                              # 実寸_肩幅
            measurements.sleeve or "",                                # 実寸_袖丈
            measurements.waist or "",                                 # 実寸_ウエスト
            measurements.inseam or "",                                # 実寸_股下
            measurements.hem_width or "",                             # 実寸_裾幅
            measurements.rise or "",                                  # 実寸_股上
            # 販売管理カラム
            "出品中",                                                  # ステータス
            "",                                                        # 販売日
            "",                                                        # 実際の販売価格
            "",                                                        # 実際の送料
            "",                                                        # 手数料
            "",                                                        # 利益
        ]

    def test_connection(self) -> tuple[bool, str]:
        """
        接続テストを行う。

        Returns:
            tuple[bool, str]: (成功/失敗, メッセージ)
        """
        try:
            worksheet = self._get_worksheet()
            title = worksheet.title
            return True, f"接続成功: シート「{title}」"
        except json.JSONDecodeError:
            return False, "GOOGLE_SHEETS_CREDENTIALSのJSON形式が不正です"
        except ValueError as e:
            return False, str(e)
        except gspread.exceptions.SpreadsheetNotFound:
            return False, "スプレッドシートが見つかりません。SPREADSHEET_IDを確認してください"
        except gspread.exceptions.APIError as e:
            return False, f"API Error: {e}"
        except Exception as e:
            return False, f"接続エラー: {e}"

    def update_sale_info(
        self,
        management_id: str,
        sale_price: int,
        shipping_cost: int,
    ) -> tuple[bool, Optional[dict]]:
        """
        売却情報を更新する。

        Args:
            management_id: 管理番号
            sale_price: 実際の販売価格
            shipping_cost: 実際の送料

        Returns:
            tuple[bool, Optional[dict]]: (成功/失敗, 売却情報または None)
                売却情報: {"purchase_price": 仕入れ価格, "sale_price": 販売価格,
                          "shipping_cost": 送料, "commission": 手数料, "profit": 利益}
        """
        try:
            # キャッシュをクリアして最新のデータを取得
            self._worksheet = None  # キャッシュをクリア
            worksheet = self._get_worksheet()  # ヘッダー確認も行われる

            # A列（管理番号）の全データを取得して検索
            col_a_values = worksheet.col_values(1)  # A列の全値を取得
            row_num = None

            # 検索対象の管理番号を正規化（整数に変換可能なら整数として比較）
            try:
                target_id = int(float(management_id))
            except (ValueError, TypeError):
                target_id = str(management_id).strip()

            print(f"[DEBUG] 検索対象の管理番号: {target_id} (type: {type(target_id)})")
            print(f"[DEBUG] A列の値: {col_a_values[:10]}...")  # 最初の10件をログ出力

            for i, value in enumerate(col_a_values):
                if i == 0:  # ヘッダー行をスキップ
                    continue

                # セルの値を正規化して比較
                try:
                    # 数値として比較を試みる（"215.0" → 215）
                    cell_value = int(float(value))
                except (ValueError, TypeError):
                    cell_value = str(value).strip()

                if cell_value == target_id:
                    row_num = i + 1  # gspreadは1始まり
                    print(f"[DEBUG] 管理番号 {target_id} を行 {row_num} で発見")
                    break

            if row_num is None:
                print(f"[DEBUG] 管理番号 {target_id} が見つかりませんでした")
                return False, None

            # 仕入れ価格を取得（HEADERSから動的に取得）
            purchase_price_col = self.HEADERS.index("仕入れ価格") + 1
            purchase_price_str = worksheet.cell(row_num, purchase_price_col).value
            purchase_price = int(purchase_price_str) if purchase_price_str else 0

            # 手数料を計算（販売価格の10%）
            commission = int(sale_price * 0.1)

            # 利益を計算（販売価格 - 仕入れ価格 - 送料 - 手数料）
            profit = sale_price - purchase_price - shipping_cost - commission

            # 販売日
            sale_date = datetime.now().strftime("%Y-%m-%d")

            # カラムのインデックスを取得
            status_col = self.HEADERS.index("ステータス") + 1
            sale_date_col = self.HEADERS.index("販売日") + 1
            sale_price_col = self.HEADERS.index("実際の販売価格") + 1
            shipping_col = self.HEADERS.index("実際の送料") + 1
            commission_col = self.HEADERS.index("手数料") + 1
            profit_col = self.HEADERS.index("利益") + 1

            # 更新するセルの範囲を一括更新
            worksheet.update_cell(row_num, status_col, "売却済み")
            worksheet.update_cell(row_num, sale_date_col, sale_date)
            worksheet.update_cell(row_num, sale_price_col, sale_price)
            worksheet.update_cell(row_num, shipping_col, shipping_cost)
            worksheet.update_cell(row_num, commission_col, commission)
            worksheet.update_cell(row_num, profit_col, profit)

            # 売却済みの行を薄いグレーに変更
            last_col = len(self.HEADERS)
            start_cell = rowcol_to_a1(row_num, 1)  # A列
            end_cell = rowcol_to_a1(row_num, last_col)  # 最終列
            gray_format = CellFormat(backgroundColor=Color(0.9, 0.9, 0.9))
            format_cell_range(worksheet, f"{start_cell}:{end_cell}", gray_format)
            print(f"[INFO] 行 {row_num} の背景色をグレーに変更しました")

            return True, {
                "purchase_price": purchase_price,
                "sale_price": sale_price,
                "shipping_cost": shipping_cost,
                "commission": commission,
                "profit": profit,
            }

        except Exception as e:
            print(f"売却情報の更新に失敗しました: {e}")
            return False, None


    def get_all_data(self) -> tuple[list[str], list[list]]:
        """
        メインシートの全データを取得する。

        Returns:
            tuple[list[str], list[list]]: (ヘッダー行, データ行のリスト)
        """
        try:
            self._worksheet = None  # キャッシュをクリア
            worksheet = self._get_worksheet()
            all_values = worksheet.get_all_values()

            if len(all_values) < 1:
                return [], []

            headers = all_values[0]
            data = all_values[1:] if len(all_values) > 1 else []

            return headers, data
        except Exception as e:
            print(f"[ERROR] データ取得に失敗しました: {e}")
            return [], []

    def create_report_sheet(self, sheet_name: str, report_data: list[list]) -> bool:
        """
        レポート用の新しいシートを作成し、データを書き込む。

        Args:
            sheet_name: シート名（例: 週次_12月第3週）
            report_data: レポートデータ（2次元配列）

        Returns:
            bool: 成功時True、失敗時False
        """
        try:
            spreadsheet = self._get_spreadsheet()

            # 同名のシートが存在するか確認
            existing_sheets = [ws.title for ws in spreadsheet.worksheets()]
            if sheet_name in existing_sheets:
                # 既存シートを削除して再作成
                old_sheet = spreadsheet.worksheet(sheet_name)
                spreadsheet.del_worksheet(old_sheet)
                print(f"[INFO] 既存のシート「{sheet_name}」を削除しました")

            # 新しいシートを作成（最後の位置に追加）
            rows = len(report_data) + 10  # 余裕を持たせる
            cols = max(len(row) for row in report_data) if report_data else 5
            new_sheet = spreadsheet.add_worksheet(
                title=sheet_name,
                rows=rows,
                cols=cols,
            )
            print(f"[INFO] 新しいシート「{sheet_name}」を作成しました")

            # データを書き込み
            if report_data:
                # A1から開始してデータを書き込む
                new_sheet.update(
                    range_name="A1",
                    values=report_data,
                    value_input_option="USER_ENTERED",
                )

            # ヘッダー行のフォーマット（セクションタイトルを太字に）
            self._format_report_sheet(new_sheet, report_data)

            return True

        except Exception as e:
            print(f"[ERROR] レポートシート作成に失敗しました: {e}")
            return False

    def _format_report_sheet(self, worksheet: gspread.Worksheet, report_data: list[list]):
        """
        レポートシートのフォーマットを設定する。

        Args:
            worksheet: ワークシート
            report_data: レポートデータ
        """
        try:
            spreadsheet = self._get_spreadsheet()
            requests = []

            # セクションタイトル（■で始まる行）を太字に
            for i, row in enumerate(report_data):
                if row and len(row) > 0 and str(row[0]).startswith("■"):
                    requests.append({
                        "repeatCell": {
                            "range": {
                                "sheetId": worksheet.id,
                                "startRowIndex": i,
                                "endRowIndex": i + 1,
                                "startColumnIndex": 0,
                                "endColumnIndex": 1,
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "textFormat": {"bold": True},
                                    "backgroundColor": {
                                        "red": 0.9,
                                        "green": 0.9,
                                        "blue": 0.95,
                                    },
                                }
                            },
                            "fields": "userEnteredFormat(textFormat,backgroundColor)",
                        }
                    })

            # タイトル行（1行目）のフォーマット
            if report_data:
                requests.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": worksheet.id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": 5,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": True, "fontSize": 12},
                            }
                        },
                        "fields": "userEnteredFormat(textFormat)",
                    }
                })

            # 列幅を調整
            requests.append({
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": worksheet.id,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": 1,
                    },
                    "properties": {"pixelSize": 180},
                    "fields": "pixelSize",
                }
            })
            requests.append({
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": worksheet.id,
                        "dimension": "COLUMNS",
                        "startIndex": 1,
                        "endIndex": 5,
                    },
                    "properties": {"pixelSize": 120},
                    "fields": "pixelSize",
                }
            })

            if requests:
                spreadsheet.batch_update({"requests": requests})

        except Exception as e:
            print(f"[WARNING] レポートシートのフォーマットに失敗しました: {e}")


# シングルトンインスタンス
_sheets_client: Optional[SheetsClient] = None


def get_sheets_client() -> SheetsClient:
    """SheetsClientのシングルトンを取得する"""
    global _sheets_client
    if _sheets_client is None:
        _sheets_client = SheetsClient()
    return _sheets_client
