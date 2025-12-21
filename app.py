"""
メルカリ出品サポートシステム - Flaskアプリケーション

LINE Messaging APIのWebhookを受け取り、商品情報を生成する。

使用法:
    開発環境: python app.py
    本番環境: gunicorn app:app
"""
import os
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, request, abort, jsonify
from dotenv import load_dotenv

from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent,
)

from config import Config
from core.text_parser import TextParser
from core.image_analyzer import ImageAnalyzer
from core.description_generator import DescriptionGenerator
from core.pricing import PricingCalculator
from core.feature_refiner import FeatureRefiner
from core.session_manager import session_manager, SessionState, UserSession
from core.report_generator import (
    ReportGenerator,
    ReportType,
    format_report_for_sheet,
    get_line_notification_message,
)
from models.product import Product, Measurements, Category
from integrations.line_handler import LineHandler
from integrations.openai_client import OpenAIClient
from integrations.sheets_client import get_sheets_client
from integrations.cloudinary_client import get_cloudinary_client


# 環境変数を読み込む
load_dotenv()

# Flaskアプリケーション
app = Flask(__name__)

# グローバル変数（遅延初期化）
line_handler = None
openai_client = None


def get_line_handler() -> LineHandler:
    """LineHandlerのシングルトンを取得"""
    global line_handler
    if line_handler is None:
        line_handler = LineHandler()
    return line_handler


def get_openai_client() -> OpenAIClient:
    """OpenAIClientのシングルトンを取得"""
    global openai_client
    if openai_client is None:
        openai_client = OpenAIClient()
    return openai_client


@app.route("/")
def index():
    """ヘルスチェック用エンドポイント"""
    return "Mercari Listing Support System is running!"


@app.route("/callback", methods=["POST"])
def callback():
    """LINE Webhookエンドポイント"""
    handler = get_line_handler()

    # 署名検証
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        handler.webhook_handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


@app.route("/api/report/weekly", methods=["POST"])
def generate_weekly_report():
    """週次レポートを生成するAPIエンドポイント"""
    return _generate_report(ReportType.WEEKLY)


@app.route("/api/report/monthly", methods=["POST"])
def generate_monthly_report():
    """月次レポートを生成するAPIエンドポイント"""
    return _generate_report(ReportType.MONTHLY)


def _generate_report(report_type: ReportType):
    """
    レポートを生成する共通処理

    Args:
        report_type: レポートの種類（週次/月次）

    Returns:
        JSON response
    """
    try:
        # スプレッドシートから全データを取得
        sheets_client = get_sheets_client()
        headers, data = sheets_client.get_all_data()

        if not headers:
            return jsonify({"success": False, "error": "データが取得できませんでした"}), 500

        # レポートを生成
        generator = ReportGenerator(data, headers)
        if report_type == ReportType.WEEKLY:
            report = generator.generate_weekly_report()
        else:
            report = generator.generate_monthly_report()

        # レポートをスプレッドシート用データに変換
        report_data = format_report_for_sheet(report)

        # 新しいシートを作成
        success = sheets_client.create_report_sheet(report.sheet_name, report_data)
        if not success:
            return jsonify({"success": False, "error": "シート作成に失敗しました"}), 500

        # LINE通知を送信
        admin_user_id = Config.LINE_ADMIN_USER_ID
        if admin_user_id:
            try:
                handler = get_line_handler()
                message = get_line_notification_message(report)
                handler.push_message(admin_user_id, message)
                print(f"[INFO] LINE通知を送信しました: {admin_user_id}")
            except Exception as e:
                print(f"[WARNING] LINE通知送信に失敗しました: {e}")

        return jsonify({
            "success": True,
            "sheet_name": report.sheet_name,
            "period": f"{report.period_start.strftime('%Y-%m-%d')} ~ {report.period_end.strftime('%Y-%m-%d')}",
            "sales_count": report.sales_summary.sales_count,
            "net_profit": report.sales_summary.net_profit,
        })

    except Exception as e:
        print(f"[ERROR] レポート生成に失敗しました: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# イベントハンドラーの登録
def setup_handlers():
    """Webhookイベントハンドラーを設定"""
    handler = get_line_handler()

    @handler.webhook_handler.add(MessageEvent, message=TextMessageContent)
    def handle_text_message(event: MessageEvent):
        """テキストメッセージの処理"""
        user_id = event.source.user_id
        text = event.message.text
        reply_token = event.reply_token

        process_text_message(user_id, text, reply_token)

    @handler.webhook_handler.add(MessageEvent, message=ImageMessageContent)
    def handle_image_message(event: MessageEvent):
        """画像メッセージの処理"""
        user_id = event.source.user_id
        message_id = event.message.id
        reply_token = event.reply_token

        process_image_message(user_id, message_id, reply_token)


def process_text_message(user_id: str, text: str, reply_token: str):
    """
    テキストメッセージを処理する。

    新しい対話式フロー:
    - IDLE: 画像と一緒に送られた「仕入れ価格 管理番号」を処理
    - COLLECTING: 仕入れ価格・管理番号を待機中
    - WAITING_MEASUREMENTS: 実寸入力待ち
    - CONFIRMING: 修正または戦略選択として処理
    """
    handler = get_line_handler()
    session = session_manager.get_session(user_id)

    # リセットコマンド
    if text.strip().lower() in ["リセット", "reset", "キャンセル", "cancel"]:
        session.reset()
        handler.clear_user_images(user_id)
        session_manager.update_session(session)
        handler.reply_text(reply_token, "セッションをリセットしました。\n商品画像と「仕入れ価格 管理番号」を送信してください。\n例: 「880 222」または「880 222 90s」")
        return

    # 売却コマンド
    if text.strip() in ["売却", "売れた", "販売完了"]:
        session.reset()
        handler.clear_user_images(user_id)
        session.state = SessionState.WAITING_SALE_INFO
        session_manager.update_session(session)
        handler.reply_text(
            reply_token,
            "売却情報を入力してください。\n「管理番号 販売価格 送料」\n例: 「215 3000 700」"
        )
        return

    # 売却情報入力待ち状態の場合
    if session.state == SessionState.WAITING_SALE_INFO:
        process_sale_info_input(user_id, text, reply_token, session)
        return

    # 確認待ち状態の場合
    if session.state == SessionState.CONFIRMING:
        process_confirmation_response(user_id, text, reply_token, session)
        return

    # 実寸入力待ち状態の場合
    if session.state == SessionState.WAITING_MEASUREMENTS:
        process_measurements_input(user_id, text, reply_token, session)
        return

    # IDLE または COLLECTING 状態の場合
    # シンプル入力から価格、管理番号、年代（オプション）を抽出
    price, mgmt_id, era = TextParser.parse_price_and_id(text)

    if price is not None:
        session.purchase_price = price
    if mgmt_id is not None:
        session.management_id = mgmt_id
    if era is not None:
        session.era = era

    # 従来形式のパースも試す（性別、サイズ、年代、実寸）
    parsed = TextParser.parse_all(text)
    if parsed["gender"]:
        session.gender = parsed["gender"]
    if parsed["size"]:
        session.size = parsed["size"]
    if parsed["era"] and session.era is None:  # シンプル入力で年代がなければ従来形式から取得
        session.era = parsed["era"]
    if parsed["measurements"] and (parsed["measurements"].has_tops_measurements() or parsed["measurements"].has_pants_measurements()):
        session.measurements = parsed["measurements"]

    session.text_input = text
    session.state = SessionState.COLLECTING
    session_manager.update_session(session)

    # 画像があり、価格と管理番号が揃っている場合
    if len(session.image_paths) > 0 and session.purchase_price and session.management_id:
        # 実寸も既に入力済みの場合は解析開始
        if session.measurements and (session.measurements.has_tops_measurements() or session.measurements.has_pants_measurements()):
            try:
                start_analysis(user_id, reply_token, session)
            except Exception as e:
                handler.reply_text(reply_token, f"エラーが発生しました: {str(e)}\n「リセット」と送信して最初からやり直してください。")
        else:
            # カテゴリ判定して実寸入力を促す
            try:
                start_category_detection(user_id, reply_token, session)
            except Exception as e:
                handler.reply_text(reply_token, f"エラーが発生しました: {str(e)}\n「リセット」と送信して最初からやり直してください。")
    else:
        # 不足データを通知
        missing = []
        if len(session.image_paths) == 0:
            missing.append("画像")
        if session.purchase_price is None:
            missing.append("仕入れ価格")
        if session.management_id is None:
            missing.append("管理番号")

        if missing:
            handler.reply_text(
                reply_token,
                f"受け付けました。\n\n不足している情報:\n・" + "\n・".join(missing) +
                "\n\n画像と「仕入れ価格 管理番号」を送信してください。\n例: 「880 222」または「880 222 90s」"
            )
        else:
            handler.reply_text(reply_token, "受け付けました。")


def process_image_message(user_id: str, message_id: str, reply_token: str):
    """
    画像メッセージを処理する。

    新しい対話式フロー:
    画像をダウンロードして保存し、価格・管理番号の入力を待つ。
    """
    handler = get_line_handler()
    session = session_manager.get_session(user_id)

    # 確認待ち状態または実寸入力待ち状態では画像を受け付けない
    if session.state in [SessionState.CONFIRMING, SessionState.WAITING_MEASUREMENTS]:
        handler.reply_text(
            reply_token,
            "現在、入力待ち状態です。\n新しい商品を登録する場合は「リセット」と送信してください。"
        )
        return

    # 画像をダウンロード
    try:
        image_path = handler.download_image(message_id, user_id)
        session.image_paths.append(image_path)
        session.state = SessionState.COLLECTING
        session_manager.update_session(session)
    except Exception as e:
        handler.reply_text(reply_token, f"画像の保存に失敗しました: {str(e)}")
        return

    # 価格と管理番号が既に揃っている場合
    if session.purchase_price and session.management_id:
        # 実寸も入力済みの場合は解析開始
        if session.measurements and (session.measurements.has_tops_measurements() or session.measurements.has_pants_measurements()):
            try:
                start_analysis(user_id, reply_token, session)
            except Exception as e:
                handler.reply_text(reply_token, f"エラーが発生しました: {str(e)}\n「リセット」と送信して最初からやり直してください。")
        else:
            # カテゴリ判定して実寸入力を促す
            try:
                start_category_detection(user_id, reply_token, session)
            except Exception as e:
                handler.reply_text(reply_token, f"エラーが発生しました: {str(e)}\n「リセット」と送信して最初からやり直してください。")
    else:
        # 複数画像対応: 画像受信時は返信せず、静かに蓄積する
        # 価格・管理番号を受信した時にまとめて処理する
        pass


def start_category_detection(user_id: str, reply_token: str, session: UserSession):
    """
    画像からカテゴリを判定し、実寸入力を促すメッセージを送信する。
    """
    handler = get_line_handler()
    client = get_openai_client()

    # AIでカテゴリを判定
    category = client.detect_category(session.image_paths)
    session.detected_category = category
    session.state = SessionState.WAITING_MEASUREMENTS
    session_manager.update_session(session)

    # カテゴリに応じた実寸入力の案内
    if category == "パンツ":
        prompt = "実寸を入力してください（ウエスト 股下 裾幅 股上の順）\n例: 「80 75 20 30」"
    elif category == "セットアップ":
        prompt = "実寸を入力してください\n（着丈 身幅 肩幅 袖丈 ウエスト 股下 裾幅 股上の順）\n例: 「70 55 45 60 80 75 20 30」"
    else:
        prompt = "実寸を入力してください（着丈 身幅 肩幅 袖丈の順）\n例: 「60 50 42 20」"

    # 画像枚数を含めたメッセージを送信
    image_count = len(session.image_paths)
    handler.reply_text(
        reply_token,
        f"画像{image_count}枚を受け付けました。\n\nカテゴリ: {category}\n\n{prompt}"
    )


def process_measurements_input(user_id: str, text: str, reply_token: str, session: UserSession):
    """
    実寸入力を処理する。
    """
    handler = get_line_handler()

    # カテゴリに応じて実寸をパース
    category = session.detected_category or "トップス"
    measurements = TextParser.parse_measurements_simple(text, category)

    # 必要な項目が揃っているかチェック
    if category == "パンツ":
        if not measurements.has_pants_measurements():
            handler.reply_text(
                reply_token,
                "実寸が正しく入力されていません。\nウエスト 股下 裾幅 股上の順で数値を入力してください。\n例: 「80 75 20 30」"
            )
            return
    elif category == "セットアップ":
        if not (measurements.has_tops_measurements() and measurements.has_pants_measurements()):
            handler.reply_text(
                reply_token,
                "実寸が正しく入力されていません。\n着丈 身幅 肩幅 袖丈 ウエスト 股下 裾幅 股上の順で数値を入力してください。\n例: 「70 55 45 60 80 75 20 30」"
            )
            return
    else:
        if not measurements.has_tops_measurements():
            handler.reply_text(
                reply_token,
                "実寸が正しく入力されていません。\n着丈 身幅 肩幅 袖丈の順で数値を入力してください。\n例: 「60 50 42 20」"
            )
            return

    session.measurements = measurements
    session_manager.update_session(session)

    # 画像解析を開始
    try:
        start_analysis(user_id, reply_token, session)
    except Exception as e:
        handler.reply_text(reply_token, f"エラーが発生しました: {str(e)}\n「リセット」と送信して最初からやり直してください。")


def process_sale_info_input(user_id: str, text: str, reply_token: str, session: UserSession):
    """
    売却情報入力を処理する。
    「管理番号 販売価格 送料」形式を期待。
    """
    handler = get_line_handler()

    # 売却情報をパース
    management_id, sale_price, shipping_cost = TextParser.parse_sale_info(text)

    # 必要な情報が揃っているかチェック
    if management_id is None or sale_price is None or shipping_cost is None:
        handler.reply_text(
            reply_token,
            "入力形式が正しくありません。\n「管理番号 販売価格 送料」の順で入力してください。\n例: 「215 3000 700」"
        )
        return

    # スプレッドシートを更新
    try:
        sheets_client = get_sheets_client()
        success, sale_info = sheets_client.update_sale_info(
            management_id=management_id,
            sale_price=sale_price,
            shipping_cost=shipping_cost,
        )

        if success and sale_info:
            # 成功メッセージを返信
            handler.reply_text(
                reply_token,
                f"売却を記録しました。\n\n"
                f"管理番号: {management_id}\n"
                f"販売価格: {sale_info['sale_price']:,}円\n"
                f"送料: {sale_info['shipping_cost']:,}円\n"
                f"手数料: {sale_info['commission']:,}円\n"
                f"利益: {sale_info['profit']:,}円\n\n"
                f"※スプレッドシートを更新しました"
            )
        else:
            handler.reply_text(
                reply_token,
                f"管理番号「{management_id}」の商品が見つかりませんでした。\n"
                f"管理番号を確認して再度入力してください。"
            )
    except Exception as e:
        handler.reply_text(
            reply_token,
            f"エラーが発生しました: {str(e)}\n再度お試しください。"
        )

    # セッションをリセット
    session.reset()
    session_manager.update_session(session)


def start_analysis(user_id: str, reply_token: str, session: UserSession):
    """
    画像解析を開始し、確認サマリーを返信する。
    """
    handler = get_line_handler()
    client = get_openai_client()

    # 画像解析
    analyzer = ImageAnalyzer(client)
    features = analyzer.analyze(session.image_paths, session.text_input)

    # 既に判定したカテゴリがあれば使用（文字列をEnum型に変換）
    if session.detected_category:
        category_map = {
            "トップス": Category.TOPS,
            "パンツ": Category.PANTS,
            "セットアップ": Category.SETUP,
        }
        features.category = category_map.get(session.detected_category, Category.TOPS)

    # テキストから取得した情報で上書き
    if session.gender:
        features.gender = session.gender
    if session.size:
        features.size = session.size
    if session.era:
        features.era = session.era

    # セッションに保存
    session.features = features
    session.description_text = getattr(features, "_description_text", "")
    session.state = SessionState.CONFIRMING
    session_manager.update_session(session)

    # 確認メッセージを送信
    confirmation = handler.format_confirmation_message(
        features.to_dict(),
        len(session.image_paths),
    )
    handler.reply_text(reply_token, confirmation)


def process_confirmation_response(
    user_id: str,
    text: str,
    reply_token: str,
    session: UserSession,
):
    """
    確認状態でのユーザー入力を処理する。

    修正内容を反映し、戦略が選択されたら生成を開始する。
    """
    handler = get_line_handler()

    # 入力を解析
    modifications, strategy = FeatureRefiner.parse_input(text)

    # 修正を反映
    if modifications and session.features:
        session.features = FeatureRefiner.apply_modifications(
            session.features,
            modifications,
        )
        session_manager.update_session(session)

    # 戦略が選択された場合は生成開始
    if strategy:
        try:
            generate_product_info(user_id, reply_token, session, strategy)
        except Exception as e:
            handler.reply_text(reply_token, f"生成中にエラーが発生しました: {str(e)}\n「リセット」と送信して最初からやり直してください。")
    elif modifications:
        # 修正のみの場合は確認メッセージを再送
        confirmation = handler.format_confirmation_message(
            session.features.to_dict(),
            len(session.image_paths),
        )
        handler.reply_text(
            reply_token,
            f"修正を反映しました。\n\n{confirmation}"
        )
    else:
        # 不明な入力
        handler.reply_text(
            reply_token,
            "入力を認識できませんでした。\n\n修正する場合：「1 adidas」のように番号と内容を送信\n確定する場合：戦略（A/B/C）を送信"
        )


def generate_product_info(
    user_id: str,
    reply_token: str,
    session: UserSession,
    strategy,
):
    """
    商品情報を生成し、結果を返信する。
    """
    handler = get_line_handler()
    client = get_openai_client()

    session.state = SessionState.GENERATING
    session_manager.update_session(session)

    # 商品データを構築
    product = Product(
        management_id=session.management_id,
        purchase_price=session.purchase_price,
        measurements=session.measurements,
        features=session.features,
        image_paths=session.image_paths,
        raw_text=session.text_input,
    )

    # 説明文を設定
    if session.description_text:
        product.features._description_text = session.description_text

    # 商品説明を生成
    generator = DescriptionGenerator(client)
    product = generator.generate_all(product)

    # 価格提案を生成
    pricing_calc = PricingCalculator(client)
    product.price_suggestion = pricing_calc.generate_price_suggestion(
        features=session.features,
        purchase_price=session.purchase_price,
        strategy=strategy,
    )

    # セッションに保存
    session.product = product
    session_manager.update_session(session)

    # 結果を返信
    messages = handler.format_result_message(product.to_dict())
    handler.reply_multiple(reply_token, messages)

    # Cloudinaryに1枚目の画像をアップロード
    if session.image_paths:
        try:
            cloudinary_client = get_cloudinary_client()
            first_image_path = session.image_paths[0]
            # 管理番号をpublic_idとして使用
            image_url = cloudinary_client.upload_image(
                first_image_path,
                public_id=product.management_id,
            )
            if image_url:
                product.image_url = image_url
                print(f"画像をCloudinaryにアップロードしました: {image_url}")
        except Exception as e:
            print(f"Cloudinaryアップロードエラー: {e}")

    # Googleスプレッドシートに保存
    try:
        sheets_client = get_sheets_client()
        if sheets_client.save_product(product):
            print(f"商品データをスプレッドシートに保存しました: {product.management_id}")
        else:
            print(f"商品データの保存に失敗しました: {product.management_id}")
    except Exception as e:
        print(f"スプレッドシート保存エラー: {e}")

    # セッションをリセット
    session.reset()
    handler.clear_user_images(user_id)
    session_manager.update_session(session)


# ハンドラーを設定
try:
    setup_handlers()
except Exception as e:
    print(f"Warning: Could not setup LINE handlers: {e}")
    print("LINE integration will not work until credentials are configured.")


if __name__ == "__main__":
    # 設定をチェック
    errors = Config.validate()
    if errors:
        print(f"Warning: Missing environment variables: {', '.join(errors)}")

    # 開発サーバーを起動
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
