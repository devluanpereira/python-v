import os
from dotenv import load_dotenv
import asyncio
import datetime
import logging
import base64
import json
from datetime import datetime, timedelta
from io import BytesIO
import mercadopago
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, CallbackQueryHandler, CallbackContext, Updater
from PIL import Image
from pix import main as create_payment

# Carregando variáveis de ambiente do arquivo .env
load_dotenv()

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

mp = mercadopago.SDK(ACCESS_TOKEN)
bot = Bot(token=TELEGRAM_TOKEN)

# Configurando logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Armazenamento temporário dos dados do pagamento para cada usuário
user_payment_data = {}

def save_payment_status(user_id, status):
    data = {}
    try:
        with open('payment_status.json', 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        pass

    data[user_id] = status

    with open('payment_status.json', 'w') as file:
        json.dump(data, file)

def load_payment_status(user_id):
    try:
        with open('payment_status.json', 'r') as file:
            data = json.load(file)
            return data.get(user_id, None)
    except FileNotFoundError:
        return None

async def check_payment_status(payment_id):
    payment = mp.payment().get(payment_id)
    if payment["status"] == 200:
        payment_status = payment["response"]["status"]
        return payment_status
    return None

async def start_payment_verification(amount, user_chat_id):
    user_id = str(user_chat_id)
    now = datetime.now()

    # Verifica se o usuário já possui um pagamento pendente
    if user_id in user_payment_data:
        last_payment_time = user_payment_data[user_id].get("timestamp", None)
        if last_payment_time:
            time_diff = now - last_payment_time
            if time_diff < timedelta(hours=24):
                await bot.send_message(chat_id=user_chat_id, text="Você já tem um pagamento pendente. Por favor, aguarde 24 horas antes de gerar outro PIX.")
                return None, None, None

    try:
        pix_qr_code_base64, pix_key, payment_id = create_payment(amount)
        logger.info(f"Pagamento criado com ID {payment_id}")

        # Armazena os dados do pagamento no dicionário
        user_payment_data[user_id] = {
            "pix_qr_code_base64": pix_qr_code_base64,
            "pix_key": pix_key,
            "payment_id": payment_id,
            "timestamp": now  # Armazena o timestamp do pagamento atual
        }

        # Decodifica a imagem base64
        qr_code_data = base64.b64decode(pix_qr_code_base64)
        image = Image.open(BytesIO(qr_code_data))

        # Salva a imagem em um arquivo temporário
        temp_file = BytesIO()
        image.save(temp_file, format='PNG')
        temp_file.seek(0)

        # Função para centralizar a chave PIX
        def centralize_text(text, width=40):
            lines = text.split("\n")
            centered_lines = []
            for line in lines:
                if len(line) < width:
                    spaces = (width - len(line)) // 2
                    centered_line = " " * spaces + line
                else:
                    centered_line = line
                centered_lines.append(centered_line)
            return "\n".join(centered_lines)

        # Centraliza a chave PIX
        centered_pix_key = centralize_text(pix_key)

        # Envia o QR Code e a chave PIX para o usuário
        await bot.send_photo(chat_id=user_chat_id, photo=temp_file, caption=f"Use este QR Code para fazer o pagamento.\n\nChave PIX (copia e cola):\n\n```\n{centered_pix_key}\n```", parse_mode='Markdown')
        logger.info(f"QR Code enviado para o usuário {user_chat_id}")

        # Inicia a verificação do status do pagamento com um atraso inicial
        asyncio.create_task(check_payment_status_loop(payment_id, user_chat_id))
        return pix_qr_code_base64, pix_key, payment_id
    except Exception as e:
        logger.error(f"Erro ao iniciar verificação de pagamento: {e}")
        await bot.send_message(chat_id=user_chat_id, text="Ocorreu um erro ao processar o pagamento. Tente novamente mais tarde.")
        return None, None, None

async def send_photo_with_buttons(user_chat_id, image_path, caption):
    keyboard = [
        [InlineKeyboardButton("Verificar Status", callback_data='check_status')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    with open(image_path, 'rb') as image_file:
        await bot.send_photo(chat_id=user_chat_id, photo=image_file, caption=caption, reply_markup=reply_markup)

async def check_payment_status_loop(payment_id, user_chat_id):
    max_checks = 30  # Limite de 30 verificações (90 minutos)
    checks = 0
    await asyncio.sleep(180)  # Atraso inicial de 3 minutos
    while checks < max_checks:
        try:
            status = await check_payment_status(payment_id)
            if status == "approved":
                await bot.send_message(chat_id=user_chat_id, text="Seu pagamento foi aprovado!")
                logger.info(f"Pagamento {payment_id} aprovado")
                save_payment_status(str(user_chat_id), "approved")
                return "approved"
            elif status == "pending":
                if checks % 1 == 0:  # Notificar a cada 3 verificações (6 minutos)
                    await send_photo_with_buttons(user_chat_id, "img/VIRGENZINHAS.png", "Seu pagamento ainda está pendente. Por favor, aguarde.")
                    logger.info(f"Pagamento {payment_id} ainda pendente")
            else:
                await bot.send_message(chat_id=user_chat_id, text=f"Status do pagamento: {status}")
                logger.info(f"Status do pagamento {payment_id}: {status}")
                break
        except Exception as e:
            logger.error(f"Erro ao verificar status do pagamento: {e}")

        checks += 1
        await asyncio.sleep(180)  # Verifica a cada 3 minutos

def button(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    user_chat_id = query.message.chat_id

    if user_chat_id in user_payment_data:
        payment_data = user_payment_data[user_chat_id]
        pix_qr_code_base64 = payment_data["pix_qr_code_base64"]
        pix_key = payment_data["pix_key"]

        # Decodifica a imagem base64
        qr_code_data = base64.b64decode(pix_qr_code_base64)
        image = Image.open(BytesIO(qr_code_data))

        # Salva a imagem em um arquivo temporário
        temp_file = BytesIO()
        image.save(temp_file, format='PNG')
        temp_file.seek(0)

        # Função para centralizar a chave PIX
        def centralize_text(text, width=40):
            lines = text.split("\n")
            centered_lines = []
            for line in lines:
                if len(line) < width:
                    spaces = (width - len(line)) // 2
                    centered_line = " " * spaces + line
                else:
                    centered_line = line
                centered_lines.append(centered_line)
            return "\n".join(centered_lines)

        # Centraliza a chave PIX
        centered_pix_key = centralize_text(pix_key)

        # Envia o QR Code e a chave PIX novamente para o usuário
        context.bot.send_photo(chat_id=user_chat_id, photo=temp_file, caption=f"Use este QR Code para fazer o pagamento.\n\nChave PIX:\n\n```\n{centered_pix_key}\n```", parse_mode='Markdown')
        logger.info(f"QR Code reenviado para o usuário {user_chat_id}")
    else:
        query.edit_message_text(text="Nenhum pagamento pendente encontrado.")

def main():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start_payment_verification))
    dp.add_handler(CallbackQueryHandler(button))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
