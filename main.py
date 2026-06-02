import os
import subprocess
import logging
import shutil
import asyncio
import sys
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Logging setting
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ⚠️ നിങ്ങളുടെ ബോട്ട് ടോക്കൺ ഇവിടെ നൽകുക
TOKEN = "8795788808:AAHtVsyYk_GneMf9Ud1ec-VsqXmpMJBD2Ew"

# ഇൻ-മെമ്മറി ഡാറ്റാബേസ്
USER_DATA = {}
RUNNING_BOTS = {} 

# പ്രോജക്റ്റുകൾ സേവ് ചെയ്യാനുള്ള മെയിൻ ഫോൾഡർ
BASE_DIR = "telegram_hosting"
os.makedirs(BASE_DIR, exist_ok=True)

# മാക്സിമം ബോട്ട് ലിമിറ്റ് 10 ആക്കി നിശ്ചയിച്ചിരിക്കുന്നു
MAX_BOTS_PER_USER = 10

# ----------------- RENDER HEALTH CHECK (FLASK) -----------------
# Render വെബ് സർവീസ് പരാജയപ്പെടാതിരിക്കാൻ ഒരു ഡമ്മി പോർട്ട് ബൈൻഡിങ് സിസ്റ്റം
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 Multi-Bot Hosting Server is Online & Running Smoothly!"

def run_flask():
    # Render നൽകുന്ന പോർട്ട് ഓട്ടോമാറ്റിക്കായി എടുക്കും (Default: 8080)
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)
# ---------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start കമാൻഡ് മെയിൻ മെനു കാണിക്കുന്നു"""
    user_id = update.effective_user.id
    if user_id not in USER_DATA:
        USER_DATA[user_id] = {"current_uploading_project": None, "projects": {}}
    await send_main_menu(update.message.reply_text, user_id)

async def send_main_menu(reply_func, user_id, edit_message=False):
    projects = USER_DATA.get(user_id, {}).get("projects", {})
    bot_count = len(projects)
    
    keyboard = []
    if bot_count < MAX_BOTS_PER_USER:
        keyboard.append([InlineKeyboardButton("➕ Create New Project & Upload", callback_data="create_project")])
    else:
        keyboard.append([InlineKeyboardButton(f"⚠️ Max Limit Reached ({bot_count}/{MAX_BOTS_PER_USER})", callback_data="limit_reached")])
        
    keyboard.append([InlineKeyboardButton("🚀 My Projects", callback_data="my_projects")])
    keyboard.append([InlineKeyboardButton("📊 Server Status & Live Monitor", callback_data="server_status")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (f"👋 **ഹലോ! പ്രീമിയം മൾട്ടി-ബോട്ട് ഹോസ്റ്റിംഗ് ബോട്ടിലേക്ക് സ്വാഗതം.**\n\n"
            f"📊 **നിങ്ങളുടെ ബോട്ടുകൾ:** {bot_count} / {MAX_BOTS_PER_USER}\n"
            f"⚡ **Speed Status:** Ultra-Fast Performance Node 🟢\n\n"
            f"താഴെയുള്ള ബട്ടണുകൾ ഉപയോഗിച്ച് പ്രോജക്റ്റുകൾ നിയന്ത്രിക്കാം.")
            
    await reply_func(text, reply_markup=reply_markup)

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "main_menu":
        context.user_data['expecting_project_name'] = False
        USER_DATA[user_id]["current_uploading_project"] = None
        await send_main_menu(query.edit_message_text, user_id)

    elif data == "limit_reached":
        await query.answer(f"നിങ്ങൾക്ക് പരമാവധി {MAX_BOTS_PER_USER} ബോട്ടുകൾ മാത്രമേ ഹോസ്റ്റ് ചെയ്യാൻ സാധിക്കൂ!", show_alert=True)

    elif data == "create_project":
        projects = USER_DATA.get(user_id, {}).get("projects", {})
        if len(projects) >= MAX_BOTS_PER_USER:
            await query.edit_message_text(f"❌ പരമാവധി ബോട്ട് ലിമിറ്റ് കഴിഞ്ഞിരിക്കുന്നു.", 
                                         reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]))
            return
        await query.edit_message_text("💬 **പ്രോജക്റ്റിന് ഒരു പേര് നൽകുക (സ്പേസ് ഒഴിവാക്കുക):**")
        context.user_data['expecting_project_name'] = True

    elif data == "upload_menu":
        proj = USER_DATA[user_id]["current_uploading_project"]
        await query.edit_message_text(
            f"📄 **ഫയലുകൾ അಪ್‌ലോഡ് ചെയ്യുക ({proj}):**\n\n"
            f"നിങ്ങളുടെ പ്രധാന ഫയൽ (`main.py` അല്ലെങ്കിൽ `bot.py`) ഈ ചാറ്റിലേക്ക് അയക്കുക.\n"
            f"തുടർന്ന് **✅ Verify Files** ബട്ടൺ അമർത്തുക.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Verify Files", callback_data=f"verify_{proj}")]])
        )

    elif data.startswith("verify_"):
        proj = data.split("_")[1]
        files = USER_DATA.get(user_id, {}).get("projects", {}).get(proj, {}).get("uploaded_files", [])
        if not files:
            await query.edit_message_text("❌ ഫയലുകളൊന്നും ലഭിച്ചിട്ടില്ല!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="upload_menu")]]))
            return
        
        USER_DATA[user_id]["projects"][proj]["status"] = "Verified ✅"
        USER_DATA[user_id]["current_uploading_project"] = None 
        await query.edit_message_text(f"🎉 **{proj} വെരിഫിക്കേഷൻ പൂർത്തിയായി!**\n\n'My Projects'-ൽ പോയി ബോട്ട് സ്റ്റാർട്ട് ചെയ്യാം.",
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Go to My Projects", callback_data="my_projects")]]))

    elif data == "my_projects":
        projects = USER_DATA.get(user_id, {}).get("projects", {})
        if not projects:
            await query.edit_message_text("❌ പ്രോജക്റ്റുകൾ ഒന്നും തന്നെയില്ല.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]))
            return
        keyboard = [[InlineKeyboardButton(f"📁 {p} ({info['status']})", callback_data=f"manage_{p}")] for p, info in projects.items()]
        keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")])
        await query.edit_message_text("📌 **നിങ്ങളുടെ പ്രോജക്റ്റുകൾ:**", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "server_status":
        total_active = len(RUNNING_BOTS)
        status_text = (
            f"🖥️ **Live Server Dashboard**\n\n"
            f"🚀 **Server Speed:** Optimum & Ultra Fast ⚡\n"
            f"🤖 **Active Sub-Bots:** {total_active} Running\n"
            f"🟢 **Status:** Operational & Stable\n"
        )
        await query.edit_message_text(status_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]))

    elif data.startswith("manage_"):
        proj = data.split("_")[1]
        status = USER_DATA[user_id]["projects"][proj]["status"]
        keyboard = [
            [InlineKeyboardButton("▶️ Start Bot", callback_data=f"start_{proj}"), InlineKeyboardButton("🛑 Stop Bot", callback_data=f"stop_{proj}")],
            [InlineKeyboardButton("📝 View Logs", callback_data=f"logs_{proj}"), InlineKeyboardButton("🗑️ Delete Project", callback_data=f"delete_{proj}")],
            [InlineKeyboardButton("🔙 Back", callback_data="my_projects")]
        ]
        await query.edit_message_text(f"🛠️ **Management: {proj}**\n📊 **സ്റ്റാറ്റസ്:** {status}", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("start_"):
        proj = data.split("_")[1]
        await query.edit_message_text(f"⏳ {proj} റൺ ചെയ്യുകയാണ്...")
        success = await asyncio.to_thread(start_user_bot, user_id, proj)
        status = "Running 🟢" if success else "Error 🔴"
        USER_DATA[user_id]["projects"][proj]["status"] = status
        await query.message.reply_text(f"ബോട്ട് സ്റ്റാറ്റസ്: {status}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"manage_{proj}")]]))

    elif data.startswith("stop_"):
        proj = data.split("_")[1]
        stop_user_bot(user_id, proj)
        USER_DATA[user_id]["projects"][proj]["status"] = "Stopped 🔴"
        await query.edit_message_text(f"🔴 {proj} സ്റ്റോപ്പ് ചെയ്തു.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"manage_{proj}")]]))

    elif data.startswith("logs_"):
        proj = data.split("_")[1]
        log_file_path = os.path.join(BASE_DIR, str(user_id), proj, "bot.log")
        if os.path.exists(log_file_path):
            with open(log_file_path, "r", encoding="utf-8", errors="ignore") as f:
                logs = f.read()[-1000:]
            await query.edit_message_text(f"📋 **Logs:**\n```\n{logs or 'No logs yet.'}\n```", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"manage_{proj}")]]))
        else:
            await query.edit_message_text("❌ ലോഗ് ഫയലുകൾ ലഭ്യമല്ല.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"manage_{proj}")]]))

    elif data.startswith("delete_"):
        proj = data.split("_")[1]
        stop_user_bot(user_id, proj)
        proj_dir = os.path.join(BASE_DIR, str(user_id), proj)
        if os.path.exists(proj_dir):
            shutil.rmtree(proj_dir)
        if proj in USER_DATA[user_id]["projects"]:
            del USER_DATA[user_id]["projects"][proj]
        await query.edit_message_text(f"🗑️ `{proj}` ഡിലീറ്റ് ചെയ്തിരിക്കുന്നു.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if context.user_data.get('expecting_project_name'):
        project_name = update.message.text.strip().replace(" ", "_")
        if project_name in USER_DATA[user_id]["projects"]:
            await update.message.reply_text("❌ ഈ പേരിൽ ഒരു പ്രോജക്റ്റ് നിലവിലുണ്ട്.")
            return
        USER_DATA[user_id]["projects"][project_name] = {"uploaded_files": [], "status": "No Files"}
        USER_DATA[user_id]["current_uploading_project"] = project_name
        context.user_data['expecting_project_name'] = False
        await update.message.reply_text(f"✅ **{project_name}** ക്രിയേറ്റ് ചെയ്തു.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📁 Upload Files Now", callback_data="upload_menu")]]))

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    proj = USER_DATA.get(user_id, {}).get("current_uploading_project")
    if not proj:
        await update.message.reply_text("⚠️ ദയവായി ആദ്യം ഒരു പ്രോജക്റ്റ് നിർമ്മിക്കുക.")
        return
    doc = update.message.document
    file_name = doc.file_name
    proj_dir = os.path.join(BASE_DIR, str(user_id), proj)
    os.makedirs(proj_dir, exist_ok=True)
    telegram_file = await context.bot.get_file(doc.file_id)
    await telegram_file.download_to_drive(custom_path=os.path.join(proj_dir, file_name))
    if file_name not in USER_DATA[user_id]["projects"][proj]["uploaded_files"]:
        USER_DATA[user_id]["projects"][proj]["uploaded_files"].append(file_name)
    await update.message.reply_text(f"📥 `{file_name}` അപ്‌ലോഡ് വിജയകരമായി പൂർത്തിയായി.")

def start_user_bot(user_id, project_name):
    proj_dir = os.path.join(BASE_DIR, str(user_id), project_name)
    files = os.listdir(proj_dir)
    main_file = next((f for f in ["main.py", "bot.py"] if f in files), next((f for f in files if f.endswith(".py")), None))
    
    if not main_file:
        return False
    
    stop_user_bot(user_id, project_name)
    log_file = open(os.path.join(proj_dir, "bot.log"), "w", encoding="utf-8")
    
    # സെർവറുകളിൽ സുരക്ഷിതമായി റൺ ചെയ്യാൻ sys.executable (python3) ഉപയോഗിക്കുന്നു
    process = subprocess.Popen([sys.executable, main_file], cwd=proj_dir, stdout=log_file, stderr=log_file)
    RUNNING_BOTS[f"{user_id}_{project_name}"] = process
    return True

def stop_user_bot(user_id, project_name):
    bot_key = f"{user_id}_{project_name}"
    if bot_key in RUNNING_BOTS:
        process = RUNNING_BOTS[bot_key]
        process.terminate()
        try: process.wait(timeout=2)
        except subprocess.TimeoutExpired: process.kill()
        del RUNNING_BOTS[bot_key]

def main():
    # Render പോർട്ട് ബൈൻഡിങ് പശ്ചാത്തലത്തിൽ സ്റ്റാർട്ട് ചെയ്യുന്നു
    threading.Thread(target=run_flask, daemon=True).start()
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_docs))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("🤖 Premium Multi-Bot Hosting Bot is running smoothly...")
    app.run_polling()

if __name__ == "__main__":
    main()
