import asyncio
import logging
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from payment_checker import start_payment_verification, load_payment_status

# Se estiver usando dotenv para carregar variáveis de ambiente
import os
from dotenv import load_dotenv

# Carregando variáveis de ambiente do arquivo .env
load_dotenv()

# Configurando logging
#logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
#logger = logging.getLogger(__name__)

# Dicionário para armazenar o status do pagamento e o timestamp do último QR code gerado
user_payments = {}

async def start(update: Update, context):
    user_id = str(update.message.from_user.id)
    now = datetime.now()

    # Permitir gerar um novo QR code
    keyboard = [
        [
            InlineKeyboardButton("Gerar PIX", callback_data='valor1'),
        ],
        [
            InlineKeyboardButton("Botão 2", callback_data='valor2'),
            InlineKeyboardButton("Botão 3", callback_data='valor3')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    image_path = "img/VIRGENZINHAS.png"
    with open(image_path, 'rb') as image_file:
        await update.message.reply_photo(photo=image_file, caption='Escolha uma opção:', reply_markup=reply_markup)
        #logger.info("Mensagem de resposta enviada")

async def button(update: Update, context):
    query = update.callback_query
    await query.answer()
    #logger.info(f"Botão {query.data} pressionado")

    amount_mapping = {
        'valor1': 1.0,  # COLOQUE O VALOR DO PRIMEIRO BOTÃO
        'valor2': 2.0,  # COLOQUE O VALOR DO SEGUNDO  BOTÃO
        'valor3': 3.0   # COLOQUE O VALOR DO TERCEIRO BOTÃO
    }

    if query.data in amount_mapping:
        amount = amount_mapping[query.data]
        user_chat_id = query.message.chat_id
        user_id = str(query.from_user.id)
        #logger.info(f"Iniciando verificação do pagamento para o valor {amount}")

        # Verificar se existe um QR code pendente para o usuário
        payment_status = load_payment_status(user_id)
        if payment_status == "approved":
            user_payments.pop(user_id, None)
        elif payment_status == "pending":
            payment_info = user_payments.get(user_id, {})
            timestamp = payment_info.get("timestamp", datetime.now())
            time_diff = datetime.now() - timestamp
            if time_diff < timedelta(minutes=30):
                await query.message.reply_text(f"Você já possui um pagamento pendente. Por favor, espere {30 - time_diff.seconds // 60} minutos antes de gerar outro QR code.")
                return

        # Iniciar verificação de pagamento e atualizar o status do usuário
        try:
            pix_qr_code_base64, pix_key, payment_id = await start_payment_verification(amount, user_chat_id)
            user_payments[user_id] = {
                "status": "pending",
                "timestamp": datetime.now(),
                "payment_id": payment_id
            }
            #logger.info("Verificação do pagamento iniciada")
        except Exception as e:
            #logger.error(f"Erro ao iniciar verificação de pagamento: {e}")
            await query.message.reply_text("Ocorreu um erro ao processar o pagamento. Tente novamente mais tarde.")

def main():
    # Se estiver usando dotenv para carregar variáveis de ambiente
    token = os.getenv("TELEGRAM_TOKEN")

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button))
    application.run_polling()

if __name__ == '__main__':
    main()
