import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ConversationHandler, ContextTypes
)
import gspread
import requests
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

# Configuração Google Sheets
gc = gspread.service_account(filename='credencial.json')
sheet_agenda = gc.open('Agendamentos Restaurante').worksheet('Agendamentos')

# Estados da conversa
MENU, NOME, PESSOAS, DATA, HORA = range(5)
FRETE_BAIRRO, FRETE_PRATO, ENDERECO, CONFIRMAR = range(5, 9)

# URLs das APIs
frete_api_url = "http://127.0.0.1:8000/frete"
cardapio_api_url = "http://127.0.0.1:8000/cardapio"

# Função para cancelar reservas atrasadas
def cancelar_atrasos():
    registros = sheet_agenda.get_all_records()
    now = datetime.now()
    for i, row in enumerate(registros, start=2):  # linha 2 em diante (considerando cabeçalho)
        if row['Status'] == 'reservado':
            data_hora_str = f"{row['Data']} {row['Hora']}"
            try:
                data_hora = datetime.strptime(data_hora_str, "%d/%m %Hh")
                if now - data_hora > timedelta(minutes=30):
                    sheet_agenda.update_cell(i, 5, 'cancelado')  # coluna 5 é Status
            except Exception as e:
                print("Erro ao analisar data:", e)

# Iniciando agendador para cancelar atrasos a cada 5 minutos
scheduler = BackgroundScheduler()
scheduler.add_job(cancelar_atrasos, 'interval', minutes=5)
scheduler.start()

# Handlers

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [['/agendar', '/cardapio'], ['/frete', '/info', '/sair']]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "👋 Olá! Bem-vindo ao Restaurante da Suelennn!\n\n"
        "Como posso te ajudar hoje?\n"
        "- /agendar: Reservar uma mesa\n"
        "- /cardapio: Ver nosso cardápio\n"
        "- /frete: Ver o frete\n"
        "- /info: Ver informações do restaurante\n"
        "- /sair: Encerrar atendimento",
        reply_markup=reply_markup
    )
    return MENU

async def cardapio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get(cardapio_api_url)
        if response.status_code == 200:
            data = response.json()
            resposta = "📋 *Cardápio:*\n"
            for categoria, itens in data.items():
                resposta += f"\n🍽️ *{categoria}*\n"
                for item in itens:
                    nome = item["nome"]
                    preco = item["preco"]
                    resposta += f"{nome} - R${preco:.2f}\n"
        else:
            resposta = "❌ Erro ao acessar o cardápio."
    except Exception as e:
        resposta = f"⚠️ Erro ao conectar à API: {e}"
    await update.message.reply_text(resposta, parse_mode='Markdown')
    return MENU

# Fluxo do frete

async def iniciar_frete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📍 Qual o bairro para entrega?")
    return FRETE_BAIRRO







async def receber_bairro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bairro_usuario = update.message.text.strip().lower()
    context.user_data["bairro"] = bairro_usuario
    
    try:
        response = requests.get(frete_api_url)
        if response.status_code == 200:
            fretes = response.json()
            fretes_normalizados = {k.strip().lower(): v for k, v in fretes.items()}
            if bairro_usuario in fretes_normalizados:
                frete = fretes_normalizados[bairro_usuario]
                context.user_data["frete"] = frete
                await update.message.reply_text(
                    f"✅ Entregamos no bairro *{bairro_usuario.title()}*.\nAgora, qual prato você deseja?",
                    parse_mode="Markdown"
                )
                return FRETE_PRATO
            else:
                await update.message.reply_text("❌ Não entregamos nesse bairro. Por favor, informe outro bairro.")
                return FRETE_BAIRRO
        else:
            await update.message.reply_text("⚠️ Erro ao consultar o frete.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Erro ao conectar à API: {e}")
    return ConversationHandler.END

async def receber_prato(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prato_escolhido = update.message.text.strip()
    try:
        response = requests.get(cardapio_api_url)
        if response.status_code == 200:
            cardapio = response.json()
            for categoria, itens in cardapio.items():
                for item in itens:
                    if item["nome"].lower() == prato_escolhido.lower():
                        preco_prato = item["preco"]
                        frete = context.user_data.get("frete", 0.0)
                        total = preco_prato + frete
                        context.user_data["prato"] = item["nome"]
                        context.user_data["preco_prato"] = preco_prato
                        context.user_data["total"] = total

                        await update.message.reply_text(
                            f"🍽️ *{item['nome']}* - R${preco_prato:.2f}\n"
                            f"🚚 Frete para *{context.user_data['bairro'].title()}* - R${frete:.2f}\n"
                            f"💰 *Total*: R${total:.2f}\n\n"
                            f"Por favor, envie seu endereço completo para a entrega.",
                            parse_mode="Markdown"
                        )
                        return ENDERECO
            await update.message.reply_text("❌ Prato não encontrado. Por favor, informe um prato válido.")
            return FRETE_PRATO
        else:
            await update.message.reply_text("⚠️ Erro ao consultar o cardápio.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Erro ao conectar à API: {e}")
    return ConversationHandler.END





async def receber_endereco(update: Update, context: ContextTypes.DEFAULT_TYPE):
    endereco = update.message.text.strip()
    context.user_data["endereco"] = endereco

    prato = context.user_data.get("prato")
    total = context.user_data.get("total")

    await update.message.reply_text(
        f"📍 Endereço: {endereco}\n"
        f"🍽️ Pedido: {prato}\n"
        f"💰 Total a pagar: R${total:.2f}\n\n"
        "Confirma o pedido? (sim/não)"
    )
    return CONFIRMAR

async def confirmar_pedido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resposta = update.message.text.strip().lower()
    if resposta in ["sim", "s", "confirmar"]:
        await update.message.reply_text(
            "✅ Pedido confirmado! Seu pedido será preparado e chegará dentro de 50 minutos. Obrigado!"
        )

        # 📋 Salvar dados na aba 'Entrega'
        try:
            sheet_entrega = gc.open('Agendamentos Restaurante').worksheet('Entrega')
            nome = context.user_data.get("nome", "Não informado")
            prato = context.user_data.get("prato", "Desconhecido")
            preco_prato = context.user_data.get("preco_prato", 0.0)
            frete = context.user_data.get("frete", 0.0)
            total = context.user_data.get("total", 0.0)
            endereco = context.user_data.get("endereco", "Não informado")
            bairro = context.user_data.get("bairro", "Desconhecido")
            data_hora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

            sheet_entrega.append_row([
                nome, prato, preco_prato, bairro, frete,
                total, endereco, data_hora, 'pendente'
            ])
        except Exception as e:
            logging.error(f"Erro ao salvar pedido de entrega: {e}")

        return ConversationHandler.END

    elif resposta in ["não", "nao", "n", "cancelar"]:
        await update.message.reply_text("❌ Pedido cancelado.")
        return ConversationHandler.END
    else:
        await update.message.reply_text("Por favor, responda com 'sim' ou 'não'. Confirma o pedido?")
        return CONFIRMAR


# /info
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📍 *Informações do Restaurante:*\n\n"
        "- Horário: 18h às 23h\n"
        "- Endereço: Rua das Flores, 123\n"
        "- Reservas com 30 minutos de tolerância\n"
        "- 5 mesas por horário.",
        parse_mode='Markdown'
    )
    return MENU

# /sair
async def sair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Atendimento encerrado. Obrigado pela visita!")
    return ConversationHandler.END

# Fluxo de /agendar
async def agendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Qual é o seu nome?")
    return NOME

async def nome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['nome'] = update.message.text.strip()
    await update.message.reply_text("Quantas pessoas?")
    return PESSOAS

async def pessoas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['pessoas'] = update.message.text.strip()
    await update.message.reply_text("Qual a data? (formato: 29/05)")
    return DATA

async def data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['data'] = update.message.text.strip()
    await update.message.reply_text("Qual o horário? (ex: 20h)")
    return HORA

async def hora(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data['data']
    hora = update.message.text.strip()
    registros = sheet_agenda.get_all_records()
    count = sum(1 for r in registros if r['Data'] == data and r['Hora'] == hora and r['Status'] == 'reservado')
    if count >= 5:
        await update.message.reply_text("❌ Todas as mesas para esse horário estão reservadas.")
        return ConversationHandler.END

    nome = context.user_data['nome']
    pessoas = context.user_data['pessoas']
    agora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    sheet_agenda.append_row([nome, pessoas, data, hora, 'reservado', agora])
    await update.message.reply_text(f"✅ Reserva confirmada para {nome}, {pessoas} pessoas, dia {data} às {hora}.")
    return ConversationHandler.END

# Fallback para mensagens não reconhecidas
async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Desculpe, não entendi. Use /start para ver as opções.")
    return MENU

def main():
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token("7731379799:AAEhbWVIe1HNIDOlM4zx6QWdEP38pJaWvfQ").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MENU: [
                CommandHandler('start', agendar),
                CommandHandler('agendar', agendar),
                CommandHandler('cardapio', cardapio),
                CommandHandler('frete', iniciar_frete),
                CommandHandler('info', info),
                CommandHandler('sair', sair),
            ],
            NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, nome)],
            PESSOAS: [MessageHandler(filters.TEXT & ~filters.COMMAND, pessoas)],
            DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, data)],
            HORA: [MessageHandler(filters.TEXT & ~filters.COMMAND, hora)],

            FRETE_BAIRRO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_bairro)],
            FRETE_PRATO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_prato)],
            ENDERECO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_endereco)],
            CONFIRMAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_pedido)],
        },
        fallbacks=[MessageHandler(filters.ALL, fallback)]
    )

    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
