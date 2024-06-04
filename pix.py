import os
from dotenv import load_dotenv
load_dotenv()

import mercadopago

class MercadoPagoIntegration:
    def __init__(self, access_token):
        self.mp = mercadopago.SDK(access_token)
    
    def create_pix_payment(self, transaction_amount, description, payer_email):
        payment_data = {
            "transaction_amount": transaction_amount,
            "description": description,
            "payment_method_id": "pix",
            "payer": {
                "email": payer_email
            }
        }

        payment_response = self.mp.payment().create(payment_data)
        return payment_response

def main(amount):
    ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
    
    mp_integration = MercadoPagoIntegration(ACCESS_TOKEN)
    
    transaction_amount = amount  # Valor da transação
    description = "Pagamento de Teste"
    payer_email = "email@example.com"
    
    payment_response = mp_integration.create_pix_payment(transaction_amount, description, payer_email)
    
    if payment_response["status"] == 201:
        payment_info = payment_response["response"]
        pix_key = payment_info["point_of_interaction"]["transaction_data"]["qr_code"]
        pix_qr_code_base64 = payment_info["point_of_interaction"]["transaction_data"]["qr_code_base64"]
        payment_id = payment_info["id"]

        return pix_qr_code_base64, pix_key, payment_id
    else:
        raise Exception(f"Erro ao criar pagamento: {payment_response['response']}")

# Garantir que a função main esteja disponível para importação
__all__ = ['main']
