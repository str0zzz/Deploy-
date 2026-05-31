import logging
import os
import threading
import subprocess
import sys
from http.server import SimpleHTTPRequestHandler
import socketserver
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ലോഗിംഗ് സെറ്റപ്പ്
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = "8848040312:AAHM4UQTWPdUXPA9cdOJDiiQ8amswBPhXLg"

# അപ്‌ലോഡ് ചെയ്യുന്ന ഫയൽ താല്കാലികമായി സൂക്ഷിക്കാൻ
TARGET_BOT_FILE = "current_bot.py"
bot_process = None # റൺ ചെയ്യുന്ന ബോട്ടിന്റെ പ്രോസസ്സ് സൂക്ഷിക്കാൻ

# Render പോർട്ട് ബൈൻഡിംഗ് എറർ ഒഴിവാക്കാനുള്ള വെബ് സെർവർ
def run_web_server():
    PORT = int(os.environ.get("PORT", 8080))
    Handler = SimpleHTTPRequestHandler
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"Web server running on port {PORT}")
            httpd.serve_forever()
    except Exception as e:
        print(f"Web server error: {e}")

# മെയിൻ മെനു ബട്ടണുകൾ
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add Bot", callback_data='add_bot'),
         InlineKeyboardButton("⚙️ Manage Bot", callback_data='manage_bot')],
        [InlineKeyboardButton("📝 Edit Bot", callback_data='edit_bot'),
         InlineKeyboardButton("📄 View Logs (Edit)", callback_data='edit_file')],
        [InlineKeyboardButton("📁 Select File (.py)", callback_data='select_file'),
         InlineKeyboardButton("🗂️ Manage File", callback_data='manage_file')],
        [InlineKeyboardButton("🚀 Deploy Bot", callback_data='deploy_bot')]
    ]
    return InlineKeyboardMarkup(keyboard)

# മാനേജ് ബോട്ട് സബ് മെനു (ON / OFF ഫീച്ചർ)
def manage_bot_keyboard():
    keyboard = [
        [InlineKeyboardButton("▶️ Turn ON", callback_data='bot_on'),
         InlineKeyboardButton("⏸️ Turn OFF", callback_data='bot_off')],
        [InlineKeyboardButton("« Back to Menu", callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

# /start കമാൻഡ്
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 ഹലോ! ഹോസ്റ്റിംഗ് ബോട്ട് കൺട്രോൾ പാനലിലേക്ക് സ്വാഗതം.\nതാഴെയുള്ള ബട്ടണുകൾ ഉപയോഗിച്ച് നിങ്ങളുടെ ബോട്ടുകൾ മാനേജ് ചെയ്യാം:",
        reply_markup=main_menu_keyboard()
    )

# ബട്ടൺ ക്ലിക്കുകൾ കൈകാര്യം ചെയ്യുന്ന ഫങ്ഷൻ
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_process
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'main_menu':
        await query.edit_message_text("മെയിൻ മെനു:", reply_markup=main_menu_keyboard())
        
    elif data == 'add_bot':
        await query.edit_message_text("🤖 പുതിയ ബോട്ട് ആഡ് ചെയ്യാൻ റെഡിയാണ്. നിങ്ങളുടെ ബോട്ടിന്റെ ടോക്കൺ അല്ലെങ്കിൽ ഫയലുകൾ അയക്കുക.\n\n« മടങ്ങാൻ താഴെ ക്ലിക്ക് ചെയ്യുക.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data='main_menu')]]))
        
    elif data == 'manage_bot':
        await query.edit_message_text("⚙️ **ബോട്ട് മാനേജ്‌മെന്റ്**\nഇവിടെ നിങ്ങൾക്ക് ബോട്ട് ഓണാക്കാനും ഓഫാക്കാനും സാധിക്കും:", reply_markup=manage_bot_keyboard())
        
    elif data == 'edit_bot':
        await query.edit_message_text("📝 ബോട്ടിന്റെ സെറ്റിംഗ്സ് എഡിറ്റ് ചെയ്യാനുള്ള ഓപ്ഷൻ ഉടൻ ലഭ്യമാകും.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data='main_menu')]]))
        
    elif data == 'edit_file':
        # ബോട്ട് ക്രാഷ് ആയാൽ എറർ ലോഗ്സ് കാണിക്കാനുള്ള ഫീച്ചർ
        if os.path.exists("bot_output.log"):
            with open("bot_output.log", "r") as f:
                logs = f.read()[-1000:] # അവസാനത്തെ 1000 അക്ഷരങ്ങൾ മാത്രം എടുക്കുന്നു
            if not logs.strip():
                logs = "ലോഗ് ഫയൽ ശൂന്യമാണ്. ബോട്ട് സുഗമമായി റൺ ചെയ്യുന്നു അല്ലെങ്കിൽ ഇതുവരെ റൺ ചെയ്തിട്ടില്ല."
            await query.edit_message_text(f"📄 **Cyber Bot Logs:**\n\n```\n{logs}\n```", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data='main_menu')]]))
        else:
            await query.edit_message_text("📄 നിലവിൽ ലോഗ് ഫയലുകൾ ഒന്നും ലഭ്യമല്ല. ബോട്ട് ഒരു തവണയെങ്കിലും ഓൺ ചെയ്യുക.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data='main_menu')]]))
        
    elif data == 'select_file':
        await query.edit_message_text("📁 ദയവായി നിങ്ങളുടെ ബോട്ടിന്റെ `.py` ഫയൽ ചാറ്റിലേക്ക് അപ്‌ലോഡ് ചെയ്യുക.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data='main_menu')]]))
        
    elif data == 'manage_file':
        await query.edit_message_text("🗂️ നിലവിലുള്ള ഫയലുകൾ ഡിലീറ്റ് ചെയ്യാനും മാറ്റം വരുത്താനും ഇവിടെ സാധിക്കും.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data='main_menu')]]))
        
    elif data == 'deploy_bot':
        await query.edit_message_text("🚀 റെൻഡർ സൈറ്റിലേക്ക് നിങ്ങളുടെ ബോട്ട് ഡിപ്ലോയ് ചെയ്യാനുള്ള പ്രോസസ്സ് ആരംഭിക്കുന്നു...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data='main_menu')]]))
        
    elif data == 'bot_on':
        if not os.path.exists(TARGET_BOT_FILE):
            await query.edit_message_text("❌ റൺ ചെയ്യാൻ പൈത്തൺ ഫയലുകൾ ഒന്നും കണ്ടെത്തിയില്ല! ദയവായി ആദ്യം ഒരു `.py` ഫയൽ സെലക്ട്/അപ്‌ലോഡ് ചെയ്യുക.", reply_markup=manage_bot_keyboard())
        elif bot_process and bot_process.poll() is None:
            await query.edit_message_text("⚠️ ബോട്ട് നിലവിൽ ബാക്ക്ഗ്രൗണ്ടിൽ റൺ ചെയ്തുകൊണ്ടിരിക്കുകയാണ്!", reply_markup=manage_bot_keyboard())
        else:
            try:
                # എററുകൾ ട്രാക്ക് ചെയ്യാൻ ഔട്ട്പുട്ട് ഫയലിലേക്ക് തിരിച്ചുവിടുന്നു
                log_file = open("bot_output.log", "w")
                bot_process = subprocess.Popen([sys.executable, TARGET_BOT_FILE], stdout=log_file, stderr=log_file)
                await query.edit_message_text("🟢 ബോട്ട് വിജയകരമായി **ON** ആക്കിയിരിക്കുന്നു!\n\n(ശ്രദ്ധിക്കുക: ബോട്ട് റെസ്പോണ്ട് ചെയ്യുന്നില്ലെങ്കിൽ മെയിൻ മെനുവിലെ 'View Logs' പരിശോധിക്കുക)", reply_markup=manage_bot_keyboard())
            except Exception as e:
                await query.edit_message_text(f"❌ ബോട്ട് റൺ ചെയ്യുന്നതിൽ പരാജയപ്പെട്ടു: {str(e)}", reply_markup=manage_bot_keyboard())
        
    elif data == 'bot_off':
        if bot_process and bot_process.poll() is None:
            bot_process.terminate() # പ്രോസസ്സ് സ്റ്റോപ്പ് ചെയ്യുന്നു
            bot_process.wait()
            bot_process = None
            await query.edit_message_text("🔴 ബോട്ട് വിജയകരമായി **OFF** ആക്കിയിരിക്കുന്നു!", reply_markup=manage_bot_keyboard())
        else:
            await query.edit_message_text("⚠️ ബോട്ട് നിലവിൽ ഓഫാണ്!", reply_markup=manage_bot_keyboard())

# ഫയലുകൾ അപ്‌ലോഡ് ചെയ്യുമ്പോൾ കൈകാര്യം ചെയ്യാൻ
async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file_name = update.message.document.file_name
    if file_name.endswith('.py'):
        file = await update.message.document.get_file()
        # ഫയൽ 'current_bot.py' എന്ന പേരിൽ ഇവിടെ സേവ് ചെയ്യും
        await file.download_to_drive(TARGET_BOT_FILE)
        
        # പുതിയ ഫയൽ വരുമ്പോൾ പഴയ ലോഗ്സ് ക്ലിയർ ചെയ്യുക
        if os.path.exists("bot_output.log"):
            try: os.remove("bot_output.log")
            except: pass
            
        await update.message.reply_text(f"✅ വിജയകരമായി സെലക്ട് ചെയ്ത് സേവ് ചെയ്തു: `{file_name}`.\nഇനി **Manage Bot**-ൽ പോയി **Turn ON** ക്ലിക്ക് ചെയ്താൽ ഈ ബോട്ട് പ്രവർത്തിക്കും.", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ ദയവായി ഒരു പൈത്തൺ ഫയൽ (.py) മാത്രം അയക്കുക.")

if __name__ == '__main__':
    # വെബ് സെർവർ ബാക്ക്ഗ്രൗണ്ടിൽ സ്റ്റാർട്ട് ചെയ്യുന്നു (Render-ന് വേണ്ടി)
    threading.Thread(target=run_web_server, daemon=True).start()
    
    # ടെലിഗ്രാം ബോട്ട് സ്റ്റാർട്ട് ചെയ്യുന്നു
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_click))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_docs))
    
    print("Hosting Bot is running perfectly with Subprocess management...")
    application.run_polling()
