import logging
from flask import Flask, request, jsonify
import telegram
import os
import hashlib
import hmac
import base64
from fpdf import FPDF
# Встановлення логування
logging.basicConfig(level=logging.INFO)
# --- Налаштування (використання змінних середовища) ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SECRET_KEY = os.environ.get("WAYFORPAY_SECRET_KEY")
if not TOKEN or not SECRET_KEY:
    logging.error("Не знайдено TELEGRAM_BOT_TOKEN або WAYFORPAY_SECRET_KEY. Застосунок не може запуститися.")
    exit(1)
bot = telegram.Bot(token=TOKEN)
app = Flask(__name__)
# --- Налаштування FPDF для підтримки кирилиці ---
try:
    # Важливо: Файл DejaVuSans.ttf має бути у тій же директорії, що й скрипт.
    FPDF.font_cache.add_font("DejaVuSans", "DejaVuSans.ttf", "DejaVuSans.pkl")
except Exception as e:
    logging.warning(f"Файл шрифту DejaVuSans.ttf не знайдено. PDF може відображати кириличні символи неправильно. Помилка: {e}")
# --- Генерація PDF ---
def generate_pdf(name):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("DejaVuSans", '', 16)
    pdf.cell(0, 10, f"AIShape: Персональний фітнес-план для {name}", ln=True)
    pdf.set_font("DejaVuSans", '', 12)
    pdf.ln(10)
    pdf.multi_cell(0, 10, "🏋️ Тренування на 7 днів:\nПн: Присідання + Віджимання\nВт: Біг + Прес\nСр: Спина + Планка\n...")
    pdf.ln(5)
    pdf.multi_cell(0, 10, "🍽️ Харчування:\nСніданок: Яйця + авокадо\nОбід: Гречка + курка\nВечеря: Риба + овочі\n...")
    file_path = "/tmp/aishape_plan_paid.pdf"
    pdf.output(file_path)
    return file_path
# --- Перевірка підпису WayforPay ---
def verify_signature(data, signature, secret_key):
    keys = sorted(data.keys())
    keys_for_signature = [k for k in keys if k != 'merchantSignature']
    signature_base = ';'.join([str(data[k]) for k in keys_for_signature])
    dig = hmac.new(secret_key.encode(), msg=signature_base.encode(), digestmod=hashlib.md5).digest()
    encoded = base64.b64encode(dig).decode()
    return signature == encoded
# --- Вебхук WayforPay ---
@app.route("/wayforpay_webhook", methods=["POST"])
def wayforpay_webhook():
    payload = request.json
    logging.info(f"Отримано вебхук: {payload}")
    signature = payload.get("merchantSignature")
    if not signature:
        logging.error("Відсутній підпис merchantSignature у вебхуку.")
        return jsonify({"reason": "Missing signature"}), 400
    if not verify_signature(payload, signature, SECRET_KEY):
        logging.error("Недійсний підпис WayforPay.")
        return jsonify({"reason": "Invalid signature"}), 403
    if payload.get("transactionStatus") == "Approved":
        try:
            telegram_id_str = payload.get("clientEmail", "").replace("telegram_", "")
            if not telegram_id_str:
                logging.error("Не знайдено Telegram ID у полі clientEmail.")
                return jsonify({"status": "error", "reason": "No Telegram ID"}), 400
            name = payload.get("customerName", "Клієнт")
            file_path = generate_pdf(name)
            with open(file_path, 'rb') as pdf:
                bot.send_document(chat_id=int(telegram_id_str), document=pdf, filename="AIShape_ProPlan.pdf",
                                  caption="✅ Дякуємо за оплату! Ось ваш персональний план.")
        except Exception as e:
            logging.error(f"Помилка при відправці документа: {e}")
            return jsonify({"status": "error"}), 500
    return jsonify({"status": "accept"}), 200
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 8080)))

