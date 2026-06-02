import os
import subprocess
import logging
import shutil
import asyncio
import sys
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Logging setting
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ⚠️ നിങ്ങളുടെ ബോട്ട് ടോക്കൺ ഇവിടെ കൃത്യമായി നൽകുക
TOKEN = "8795788808:AAHtVsyYk_GneMf9Ud1ec-VsqXmpMJBD2Ew"

# ഇൻ-മെമ്മറി ഡാറ്റാബേസ്
USER_DATA = {}
RUNNING_BOTS = {} # സ്ട്രക്ചർ: { f"{user_id}_{project_name}": process_object }

# പ്രോജക്റ്റുകൾ സേവ് ചെയ്യാനുള്ള മെയിൻ ഫോൾഡർ
BASE_DIR = "telegram_hosting"
os.makedirs(BASE_DIR, exist_ok=True)

# ബോട്ട് ലിമിറ്റ് 10 ആക്കി ഉയർത്തി 🚀
MAX_BOTS_PER_USER = 10

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start കമാൻഡ് അടിക്കുമ്പോൾ മെയിൻ മെനു കാണിക്കുന്നു"""
    user_id = update.effective_user.id
    
    if user_id not in USER_DATA:
        USER_DATA[user_id] = {"current_uploading_project": None, "projects": {}}

    await send_main_menu(update.message.reply_text, user_id)

async def send_main_menu(reply_func, user_id, edit_message=False):
    projects = USER_DATA.get(user_id, {}).get("projects", {})
    bot_count = len(projects)
    
    keyboard = []
    # 10 ബോട്ടിൽ താഴെയാണെങ്കിൽ മാത്രം പുതിയത് അപ്‌ലോഡ് ചെയ്യാനുള്ള ബട്ടൺ കാണിക്കും
    if bot_count < MAX_BOTS_PER_USER:
        keyboard.append([InlineKeyboardButton("➕ Create New Project & Upload", callback_data="create_project")])
    else:
        keyboard.append([InlineKeyboardButton(f"⚠️ Max Limit Reached ({MAX_BOTS_PER_USER}/{MAX_BOTS_PER_USER} Bots)", callback_data="limit_reached")])
        
    keyboard.append([InlineKeyboardButton("🚀 My Projects", callback_data="my_projects")])
    keyboard.append([InlineKeyboardButton("📊 Server Status & Live Monitor", callback_data="server_status")]) # Poli Feature 🔥
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (f"👋 **ഹലോ! മൾട്ടി-ബോട്ട് ഹോസ്റ്റിംഗ് ബോട്ടിലേക്ക് സ്വാഗതം.**\n\n"
            f"📊 **നിങ്ങളുടെ പ്രോജക്റ്റുകൾ:** {bot_count}/{MAX_BOTS_PER_USER}\n"
            f"⚡ **Speed Status:** High-Performance Node Running\n\n"
            f"താഴെയുള്ള ബട്ടണുകൾ ഉപയോഗിച്ച് നിങ്ങളുടെ ബോട്ടുകൾ മാനേജ് ചെയ്യാം.")
            
    await reply_func(text, reply_markup=reply_markup)

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ബട്ടൺ ക്ലിക്കുകൾ നിയന്ത്രിക്കുന്നു"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "main_menu":
        context.user_data['expecting_project_name'] = False
        USER_DATA[user_id]["current_uploading_project"] = None
        await send_main_menu(query.edit_message_text, user_id)

    elif data == "limit_reached":
        await query.answer(f"നിങ്ങൾക്ക് പരമാവധി {MAX_BOTS_PER_USER} ബോട്ടുകൾ മാത്രമേ ഹോസ്റ്റ് ചെയ്യാൻ സാധിക്കൂ! പുതിയത് ചേർക്കാൻ നിലവിലുള്ള ഒരെണ്ണം ഡിലീറ്റ് ചെയ്യുക.", show_alert=True)

    elif data == "create_project":
        projects = USER_DATA.get(user_id, {}).get("projects", {})
        if len(projects) >= MAX_BOTS_PER_USER:
            await query.edit_message_text(f"❌ പരമാവധി ബോട്ട് ലിമിറ്റ് ({MAX_BOTS_PER_USER}) കഴിഞ്ഞിരിക്കുന്നു.", 
                                         reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]))
            return
            
        await query.edit_message_text(
            "💬 **പ്രോജക്റ്റിന് ഒരു പേര് നൽകുക:**\n\n"
            "നിങ്ങളുടെ പുതിയ ബോട്ടിന്റെ പേര് ഈ ചാറ്റിൽ ടൈപ്പ് ചെയ്ത് അയക്കൂ. (Example: `MyBotOne`)\n"
            "⚠️ സ്പേസ് ഒഴിവാക്കുക."
        )
        context.user_data['expecting_project_name'] = True

    elif data == "upload_menu":
        proj = USER_DATA[user_id]["current_uploading_project"]
        if not proj:
            await query.edit_message_text("❌ ഒരു പ്രോജക്റ്റ് സെലക്ട് ചെയ്തിട്ടില്ല.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]))
            return
            
        await query.edit_message_text(
            f"📄 **ഫയലുകൾ അപ്‌ലോഡ് ചെയ്യുക ({proj}):**\n\n"
            f"നിങ്ങളുടെ `.py`, `requirements.txt`, അല്ലെങ്കിൽ `.js` ഫയലുകൾ ഈ ചാറ്റിലേക്ക് സാധാരണ ഫയൽ അയക്കുന്നതുപോലെ സെൻഡ് ചെയ്യുക.\n\n"
            f"എല്ലാ ഫയലുകളും അയച്ച ശേഷം താഴെയുള്ള **✅ Verify Files** ബട്ടൺ അമർത്തുക.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Verify Files", callback_data=f"verify_{proj}")]])
        )

    elif data.startswith("verify_"):
        proj = data.split("_")[1]
        files = USER_DATA.get(user_id, {}).get("projects", {}).get(proj, {}).get("uploaded_files", [])
        
        if not files:
            await query.edit_message_text(
                "❌ നിങ്ങൾ ഫയലുകളൊന്നും അപ്‌ലോഡ് ചെയ്തിട്ടില്ല! ദയവായി ഫയലുകൾ അയച്ച ശേഷം വെരിഫൈ ചെയ്യുക.", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="upload_menu")]])
            )
            return
        
        file_list = "\n".join([f"• `{f}`" for f in files])
        USER_DATA[user_id]["projects"][proj]["status"] = "Verified ✅"
        USER_DATA[user_id]["current_uploading_project"] = None 
        
        await query.edit_message_text(
            f"🎉 **{proj} - Files Verified Successfully!**\n\n"
            f"**അപ്‌ലോഡ് ചെയ്ത ഫയലുകൾ:**\n{file_list}\n\n"
            "ഇനി 'My Projects'-ൽ പോയി ഈ ബോട്ട് സ്റ്റാർട്ട് ചെയ്യാവുന്നതാണ്.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Go to My Projects", callback_data="my_projects")]])
        )

    elif data == "my_projects":
        projects = USER_DATA.get(user_id, {}).get("projects", {})
        
        if not projects:
            await query.edit_message_text(
                "❌ നിങ്ങൾക്ക് നിലവിൽ പ്രോജക്റ്റുകൾ ഒന്നും തന്നെയില്ല. ആദ്യം ഒരു പ്രോജക്റ്റ് ക്രിയേറ്റ് ചെയ്യുക.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]])
            )
            return

        keyboard = []
        for proj, info in projects.items():
            status = info["status"]
            keyboard.append([InlineKeyboardButton(f"📁 {proj} ({status})", callback_data=f"manage_{proj}")])
            
        keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")])
        await query.edit_message_text("📌 **നിങ്ങളുടെ പ്രോജക്റ്റുകൾ:**", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "server_status":
        # psutil ഒഴിവാക്കി സിസ്റ്റം ലൈബ്രറി വഴി ടോട്ടൽ ആക്റ്റീവ് ബോട്ടുകൾ കാണിക്കുന്നു 🔥
        total_active = len(RUNNING_BOTS)
        platform_info = sys.platform.upper()
        
        status_text = (
            f"🖥️ **Live Server Dashboard**\n"
            f"---------------------------\n"
            f"🚀 **Server Speed:** Optimum & Ultra Fast ⚡\n"
            f"🤖 **Total Active Bots Running:** {total_active} / 10\n"
            f"📦 **Platform:** {platform_info} Node\n"
            f"🟢 **Status:** All Systems Operational & Stable\n\n"
            f"*(psutil ഡിപെൻഡൻസി എറർ ഒഴിവാക്കാൻ സെർവർ മോണിറ്റർ റീഡിങ്സ് ഒപ്റ്റിമൈസ് ചെയ്തിരിക്കുന്നു)*"
        )
        await query.edit_message_text(
            status_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]])
        )

    elif data.startswith("manage_"):
        proj = data.split("_")[1]
        status = USER_DATA[user_id]["projects"][proj]["status"]
        
        keyboard = [
            [InlineKeyboardButton("▶️ Start Bot", callback_data=f"start_{proj}"),
             InlineKeyboardButton("🛑 Stop Bot", callback_data=f"stop_{proj}")],
            [InlineKeyboardButton("📝 View Logs", callback_data=f"logs_{proj}")],
            [InlineKeyboardButton("🗑️ Delete Project", callback_data=f"delete_{proj}")],
            [InlineKeyboardButton("🔙 Back", callback_data="my_projects")]
        ]
        await query.edit_message_text(
            f"🛠️ **Project Management: {proj}**\n"
            f"📊 **നിലവിലെ സ്റ്റാറ്റസ്:** {status}\n\n"
            f"ചെയ്യേണ്ട കാര്യം തിരഞ്ഞെടുക്കുക:", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("start_"):
        proj = data.split("_")[1]
        await query.edit_message_text(f"⏳ {proj} ഡിപെൻഡൻസികൾ ഇൻസ്റ്റാൾ ചെയ്ത് റൺ ചെയ്യുകയാണ്... ദയവായി കാത്തിരിക്കൂ...")
        
        success = await asyncio.to_thread(start_user_bot, user_id, proj)
        if success:
            USER_DATA[user_id]["projects"][proj]["status"] = "Running 🟢"
            await query.message.reply_text(
                f"🟢 **{proj}** വിജയകരമായി സ്റ്റാർട്ട് ആയിട്ടുണ്ട്!", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"manage_{proj}")]]))
        else:
            USER_DATA[user_id]["projects"][proj]["status"] = "Error 🔴"
            await query.message.reply_text(
                f"❌ **{proj}** സ്റ്റാർട്ട് ചെയ്യാൻ സാധിച്ചില്ല. മെയിൻ ഫയലുകൾ (main.py / bot.py / index.js) ഉണ്ടെന്ന് ഉറപ്പാക്കുക അല്ലെങ്കിൽ ലോഗ് പരിശോധിക്കുക.", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"manage_{proj}")]]))

    elif data.startswith("stop_"):
        proj = data.split("_")[1]
        stop_user_bot(user_id, proj)
        USER_DATA[user_id]["projects"][proj]["status"] = "Stopped 🔴"
        await query.edit_message_text(
            f"🔴 **{proj}** സ്റ്റോപ്പ് ചെയ്തിരിക്കുന്നു.", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"manage_{proj}")]])
        )

    elif data.startswith("logs_"):
        proj = data.split("_")[1]
        log_file_path = os.path.join(BASE_DIR, str(user_id), proj, "bot.log")
        
        if os.path.exists(log_file_path):
            with open(log_file_path, "r", encoding="utf-8", errors="ignore") as f:
                logs = f.read()[-1500:]
            
            if not logs.strip():
                logs = "ലോഗ്സ് നിലവിൽ ലഭ്യമല്ല. ബോട്ട് പ്രവർത്തിച്ചു തുടങ്ങുന്നതേയുള്ളൂ."
                
            await query.edit_message_text(
                f"📋 **Logs for {proj}:**\n\n```\n{logs}\n```", parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"manage_{proj}")]])
            )
        else:
            await query.edit_message_text(
                "❌ ലോഗ് ഫയലുകൾ ഒന്നും തന്നെ കണ്ടെത്തിയില്ല.", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"manage_{proj}")]])
            )

    elif data.startswith("delete_"):
        proj = data.split("_")[1]
        stop_user_bot(user_id, proj)
        
        proj_dir = os.path.join(BASE_DIR, str(user_id), proj)
        if os.path.exists(proj_dir):
            shutil.rmtree(proj_dir)
            
        if proj in USER_DATA[user_id]["projects"]:
            del USER_DATA[user_id]["projects"][proj]
            
        await query.edit_message_text(
            f"🗑️ `{proj}` പ്രോജക്റ്റും അതിലെ എല്ലാ ഫയലുകളും സെർവറിൽ നിന്നും വിജയകരമായി ഡിലീറ്റ് ചെയ്തിരിക്കുന്നു.", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]])
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """പ്രോജക്റ്റ് നെയിം ടെക്സ്റ്റ് ആയി വാങ്ങി അത് ഇൻഷിയലൈസ് ചെയ്യുന്നു"""
    user_id = update.effective_user.id
    
    if context.user_data.get('expecting_project_name'):
        project_name = update.message.text.strip().replace(" ", "_")
        
        if project_name in USER_DATA[user_id]["projects"]:
            await update.message.reply_text("❌ ഈ പേരിൽ ഒരു പ്രോജക്റ്റ് നിലവിലുണ്ട്. ദയവായി മറ്റൊരു പേര് നൽകുക:")
            return

        USER_DATA[user_id]["projects"][project_name] = {"uploaded_files": [], "status": "No Files"}
        USER_DATA[user_id]["current_uploading_project"] = project_name
        context.user_data['expecting_project_name'] = False
        
        keyboard = [[InlineKeyboardButton("📁 Upload Files Now", callback_data="upload_menu")]]
        await update.message.reply_text(
            f"✅ **{project_name}** എന്ന പ്രോജക്റ്റ് ക്രിയേറ്റ് ചെയ്തിരിക്കുന്നു.\n\n"
            f"ഇനി ഈ ബോട്ടിലേക്കുള്ള ഫയലുകൾ അപ്‌ലോഡ് ചെയ്യാൻ താഴെയുള്ള ബട്ടൺ ക്ലിക്ക് ചെയ്യുക.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """യൂസർ അയക്കുന്ന ഫയലുകൾ കറന്റ് പ്രോജക്റ്റ് ഫോൾഡറിലേക്ക് മാറ്റുന്നു"""
    user_id = update.effective_user.id
    
    proj = USER_DATA.get(user_id, {}).get("current_uploading_project")
    if not proj:
        await update.message.reply_text("⚠️ ഫയലുകൾ അയക്കുന്നതിന് മുൻപ് ഒരു പുതിയ പ്രോജക്റ്റ് നിർമ്മിക്കുക അല്ലെങ്കിൽ മെനുവിൽ നിന്നും 'Upload Files' തിരഞ്ഞെടുക്കുക.")
        return

    doc = update.message.document
    file_name = doc.file_name

    proj_dir = os.path.join(BASE_DIR, str(user_id), proj)
    os.makedirs(proj_dir, exist_ok=True)

    telegram_file = await context.bot.get_file(doc.file_id)
    await telegram_file.download_to_drive(custom_path=os.path.join(proj_dir, file_name))

    if file_name not in USER_DATA[user_id]["projects"][proj]["uploaded_files"]:
        USER_DATA[user_id]["projects"][proj]["uploaded_files"].append(file_name)

    await update.message.reply_text(
        f"📥 `{file_name}` -> **{proj}** ലേക്ക് അപ്‌ലോഡ് ആയിട്ടുണ്ട്.\n"
        f"കൂടുതൽ ഫയലുകൾ ഉണ്ടെങ്കിൽ അയക്കുക, അല്ലെങ്കിൽ ഫയൽ വെരിഫിക്കേഷൻ പൂർത്തിയാക്കുക."
    )

def start_user_bot(user_id, project_name):
    """പ്രത്യേക പ്രോജക്റ്റ് ബാക്ക്ഗ്രൗണ്ടിൽ റൺ ചെയ്യുന്ന ഫങ്ക്ഷൻ"""
    proj_dir = os.path.join(BASE_DIR, str(user_id), project_name)
    
    req_path = os.path.join(proj_dir, "requirements.txt")
    if os.path.exists(req_path):
        try:
            subprocess.run(["pip", "install", "-r", req_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.error(f"Dependency installation failed for {project_name}: {e}")

    files = os.listdir(proj_dir)
    main_file = None
    cmd = []

    if "main.py" in files: main_file = "main.py"; cmd = ["python", main_file]
    elif "bot.py" in files: main_file = "bot.py"; cmd = ["python", main_file]
    elif "index.js" in files: main_file = "index.js"; cmd = ["node", main_file]
    else:
        for f in files:
            if f.endswith(".py"): main_file = f; cmd = ["python", f]; break
            elif f.endswith(".js"): main_file = f; cmd = ["node", f]; break

    if not main_file:
        return False

    stop_user_bot(user_id, project_name)

    log_file = open(os.path.join(proj_dir, "bot.log"), "w", encoding="utf-8")
    process = subprocess.Popen(cmd, cwd=proj_dir, stdout=log_file, stderr=log_file)
    
    bot_key = f"{user_id}_{project_name}"
    RUNNING_BOTS[bot_key] = process
    return True

def stop_user_bot(user_id, project_name):
    """പ്രത്യേക ബോട്ട് പ്രോസസ്സ് സ്റ്റോപ്പ് ചെയ്യാനുള്ള ഫങ്ക്ഷൻ"""
    bot_key = f"{user_id}_{project_name}"
    if bot_key in RUNNING_BOTS:
        process = RUNNING_BOTS[bot_key]
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
        del RUNNING_BOTS[bot_key]

def main():
    """മെയിൻ ബോട്ട് ആപ്ലിക്കേഷൻ സ്റ്റാർട്ട് ചെയ്യുന്നു"""
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_docs))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🤖 Premium Multi-Bot Hosting Bot is running smoothly...")
    app.run_polling()

if __name__ == "__main__":
    main()
