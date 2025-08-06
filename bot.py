import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from datetime import datetime

# معرفات المدراء
ADMINS = [66249577]  # ← غيّر هذا إلى user_id الخاص بك

# ملفات الحفظ
PENDING_FILE = 'pending_users.json'
APPROVED_FILE = 'approved_users.json'

# تحميل البيانات من الملفات
def load_data(file):
    try:
        with open(file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_data(file, data):
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# تحميل المستخدمين
PENDING_USERS = load_data(PENDING_FILE)
APPROVED_USERS = load_data(APPROVED_FILE)
NAMING = {}
ACTION_STATE = {}

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "بدون معرف"

    if user_id in ADMINS:
        keyboard = [
            [InlineKeyboardButton("📢 إرسال إشعار للجميع", callback_data="notify_all")],
            [InlineKeyboardButton("📨 إرسال إشعار لمستخدم", callback_data="notify_one")],
            [InlineKeyboardButton("👥 عرض المشتركين", callback_data="show_users")],
            [InlineKeyboardButton("❌ حذف مستخدم", callback_data="delete_user")],
            [InlineKeyboardButton("🌴 إجازة", callback_data="vacation")],
            [InlineKeyboardButton("⏳ إجازة زمنية", callback_data="timed")],
        ]
        await update.message.reply_text("🎛️ لوحة التحكم", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if str(user_id) in APPROVED_USERS:
        await update.message.reply_text("✅ أنت مشترك بالفعل.")
        return

    if str(user_id) in PENDING_USERS:
        await update.message.reply_text("⏳ طلبك قيد الانتظار.")
        return

    # طلب جديد
    PENDING_USERS[str(user_id)] = username
    save_data(PENDING_FILE, PENDING_USERS)
    await update.message.reply_text("📩 تم إرسال طلبك للإداري. الرجاء الانتظار.")

    for admin in ADMINS:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ قبول", callback_data=f"accept:{user_id}"),
            InlineKeyboardButton("❌ رفض", callback_data=f"reject:{user_id}")
        ]])
        await context.bot.send_message(chat_id=admin, text=f"🔔 طلب انضمام من @{username}\nID: {user_id}", reply_markup=keyboard)

# رد على الأزرار
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    admin_id = query.from_user.id
    if admin_id not in ADMINS:
        await query.edit_message_text("🚫 ليس لديك صلاحية.")
        return

    data = query.data

    if data.startswith("accept:"):
        user_id = int(data.split(":")[1])
        NAMING[admin_id] = user_id
        await query.edit_message_text("✅ تم القبول. أرسل الآن اسم المستخدم:")
    elif data.startswith("reject:"):
        user_id = int(data.split(":")[1])
        PENDING_USERS.pop(str(user_id), None)
        save_data(PENDING_FILE, PENDING_USERS)
        await context.bot.send_message(chat_id=user_id, text="❌ تم رفض طلبك.")
        await query.edit_message_text("❌ تم رفض المستخدم.")
    elif data == "notify_all":
        ACTION_STATE[admin_id] = "notify_all"
        await query.message.reply_text("✉️ أرسل الرسالة التي تريد إرسالها للجميع:")
    elif data == "notify_one":
        ACTION_STATE[admin_id] = "notify_one_name"
        await query.message.reply_text("👤 أرسل اسم المستخدم:")
    elif data == "show_users":
        if APPROVED_USERS:
            users_list = "\n".join(f"{name} - {uid}" for uid, name in APPROVED_USERS.items())
            await query.message.reply_text(f"📄 قائمة المشتركين:\n{users_list}")
        else:
            await query.message.reply_text("❌ لا يوجد مشتركين حالياً.")
    elif data == "delete_user":
        ACTION_STATE[admin_id] = "delete_user"
        await query.message.reply_text("🗑️ أرسل اسم المستخدم المراد حذفه:")
    elif data == "vacation":
        ACTION_STATE[admin_id] = "vacation"
        await query.message.reply_text("🌴 أرسل اسم المستخدم:")
    elif data == "timed":
        ACTION_STATE[admin_id] = "timed"
        await query.message.reply_text("⏳ أرسل اسم المستخدم:")

# استقبال النصوص للإداري
async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = update.effective_user.id
    if admin_id not in ADMINS:
        return

    text = update.message.text.strip()

    if admin_id in NAMING:
        user_id = NAMING.pop(admin_id)
        APPROVED_USERS[str(user_id)] = text
        PENDING_USERS.pop(str(user_id), None)
        save_data(APPROVED_FILE, APPROVED_USERS)
        save_data(PENDING_FILE, PENDING_USERS)
        await update.message.reply_text(f"✅ تم تسمية المستخدم بـ: {text}")
        await context.bot.send_message(chat_id=user_id, text="✅ تم قبولك! أهلاً بك.")
        return

    if admin_id not in ACTION_STATE:
        return

    action = ACTION_STATE[admin_id]

    if action == "notify_all":
        for uid in APPROVED_USERS:
            try:
                await context.bot.send_message(chat_id=int(uid), text=text)
            except:
                pass
        await update.message.reply_text("📢 تم إرسال الإشعار للجميع.")
        del ACTION_STATE[admin_id]

    elif action == "notify_one_name":
        matched = [uid for uid, name in APPROVED_USERS.items() if name == text]
        if matched:
            ACTION_STATE[admin_id] = f"notify_one_msg:{matched[0]}"
            await update.message.reply_text("✉️ أرسل الرسالة الآن:")
        else:
            await update.message.reply_text("❌ لم يتم العثور على هذا المستخدم.")
    elif action.startswith("notify_one_msg:"):
        uid = action.split(":")[1]
        await context.bot.send_message(chat_id=int(uid), text=text)
        await update.message.reply_text("📨 تم إرسال الإشعار.")
        del ACTION_STATE[admin_id]

    elif action == "delete_user":
        matched = [uid for uid, name in APPROVED_USERS.items() if name == text]
        if matched:
            uid = matched[0]
            APPROVED_USERS.pop(uid)
            save_data(APPROVED_FILE, APPROVED_USERS)
            await update.message.reply_text("🗑️ تم حذف المستخدم.")
        else:
            await update.message.reply_text("❌ لم يتم العثور على هذا المستخدم.")
        del ACTION_STATE[admin_id]

    elif action in ["vacation", "timed"]:
        matched = [uid for uid, name in APPROVED_USERS.items() if name == text]
        if matched:
            uid = matched[0]
            now = datetime.now().strftime("%Y-%m-%d %I:%M %p")
            if action == "vacation":
                await context.bot.send_message(chat_id=int(uid), text=f"✅ تمت الموافقة على منحك إجازة.\n📅 {now}")
                await update.message.reply_text("🌴 تم إرسال إشعار الإجازة.")
            else:
                await context.bot.send_message(chat_id=int(uid), text=f"⏳ تمت الموافقة على منحك إجازة زمنية.\n📅 {now}")
                await update.message.reply_text("⏳ تم إرسال إشعار الإجازة الزمنية.")
        else:
            await update.message.reply_text("❌ لم يتم العثور على هذا المستخدم.")
        del ACTION_STATE[admin_id]

# تشغيل البوت
app = ApplicationBuilder().token("8390870658:AAE-z8JlpHLuQfcuENlUJ5V9Qw8z1MyAajA").build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_buttons))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_input))

print("✅ البوت بدأ ويعمل الآن...")
app.run_polling(allowed_updates=Update.ALL_TYPES)
