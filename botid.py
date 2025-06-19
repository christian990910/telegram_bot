from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("===== 群组信息 =====")
    print(f"群组名: {update.effective_chat.title}")
    print(f"chat_id: {update.effective_chat.id}")
    print("====================")

app = ApplicationBuilder().token("7925148285:AAEARkb-2OSo1OsYK73aqA0y_fi_KVEtiyg").build()
app.add_handler(MessageHandler(filters.ALL, get_chat_id))
app.run_polling()
