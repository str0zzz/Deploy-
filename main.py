import os
import subprocess
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes
)

# Render-ൽ നിന്നും അല്ലെങ്കിൽ നേരിട്ട് TOKEN നൽകുക
TOKEN = os.getenv('TOKEN', '7964154308:AAGPy7d8XgrvuPlTWMKRA3vqLlFggp357_4')
ADMIN_ID = 8391392903

# Flask വെബ് സെർവർ (Render-ൽ ബോട്ട് സ്ലീപ്പ് ആകാതിരിക്കാൻ)
app_web = Flask(__name__)
@app_web.route('/')
def home(): return "Bot is Running"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app_web.run(host='0.0.0.0', port=port)

# ബോട്ട് മാനേജ്‌മെന്റ് വേരിയബിളുകൾ
my_bots = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    keyboard = [
        [InlineKeyboardButton("➕ Add Bot", callback_data='add')],
        [InlineKeyboardButton("⚙️ Manage Bots", callback_data='manage')]
    ]
    await update.message.reply_text("Bot Manager Panel:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == 'add':
        context.user_data['state'] = 'waiting_name'
        await query.edit_message_text("ബോട്ടിന്റെ പേര് ടൈപ്പ് ചെയ്യുക:")
    elif data == 'manage':
        if not my_bots:
            await query.edit_message_text("ബോട്ടുകൾ ഒന്നും ഇല്ല!")
            return
        keyboard = [[InlineKeyboardButton(name, callback_data=f"sel_{name}")] for name in my_bots]
        await query.edit_message_text("ഏത് ബോട്ട് മാനേജ് ചെയ്യണം?", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith('sel_'):
        name = data.split('_')[1]
        context.user_data['current_bot'] = name
        keyboard = [
            [InlineKeyboardButton("🟢 ON", callback_data='on'), InlineKeyboardButton("🔴 OFF", callback_data='off')],
            [InlineKeyboardButton("🗑 Delete", callback_data='del')]
        ]
        await query.edit_message_text(f"Manager: {name}", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data in ['on', 'off', 'del']:
        name = context.user_data.get('current_bot')
        if not name: return
        if data == 'on':
            if my_bots[name]['process'] is None:
                my_bots[name]['process'] = subprocess.Popen(["python3", my_bots[name]['file']])
                await query.edit_message_text(f"{name} Started ✅")
        elif data == 'off':
            if my_bots[name]['process']:
                my_bots[name]['process'].terminate()
                my_bots[name]['process'] = None
                await query.edit_message_text(f"{name} Stopped ❌")
        elif data == 'del':
            if my_bots[name]['process']: my_bots[name]['process'].terminate()
            del my_bots[name]
            await query.edit_message_text(f"{name} ഡിലീറ്റ് ചെയ്തു 🗑")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.document and context.user_data.get('state') == 'waiting_file':
        name = context.user_data.get('bot_name')
        path = f"{name}.py"
        await update.message.document.get_file().download_to_drive(path)
        my_bots[name] = {"process": None, "file": path}
        context.user_data['state'] = None
        await update.message.reply_text(f"✅ {name} ആഡ് ചെയ്തു!")
        return

    if context.user_data.get('state') == 'waiting_name':
        context.user_data['bot_name'] = update.message.text
        context.user_data['state'] = 'waiting_file'
        await update.message.reply_text(f"പേര്: '{update.message.text}'. ഇനി ഫയൽ അയക്കൂ.")

if __name__ == '__main__':
    # വെബ് സെർവർ ബാക്ക്ഗ്രൗണ്ടിൽ സ്റ്റാർട്ട് ചെയ്യുന്നു
    threading.Thread(target=run_web, daemon=True).start()
    
    # Telegram ബോട്ട് സ്റ്റാർട്ട് ചെയ്യുന്നു
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT | filters.Document.ALL, handle_message))
    app.run_polling()
