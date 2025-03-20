import telebot
import json
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

TOKEN = "7904905429:AAH_fXsUJMcmADRPgJH4x-QMoQo-45TSMzw"
bot = telebot.TeleBot(TOKEN)

# قائمة مع المعرفات الخاصة بالملاك
OWNER_IDS = [7307068365, 6735264173]  # استبدلها بمعرفات الملاك الفعليين

# ملف لتخزين الأزرار
BUTTONS_FILE = "buttons.json"

# تخزين الأزرار مع الملفات
buttons = []

# حالة المستخدم أثناء الإضافة
user_state = {}

# محاولة تحميل الأزرار من ملف JSON إذا كان موجودًا
try:
    with open(BUTTONS_FILE, "r") as f:
        buttons = json.load(f)
except FileNotFoundError:
    buttons = []

def get_keyboard():
    """ هذه الدالة لإرجاع الكيبورد مع الأزرار الحالية """
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    for btn in buttons:
        markup.add(KeyboardButton(btn["name"]))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """ يرسل رسالة الترحيب مع الأزرار أسفل النص عند تشغيل البوت """
    welcome_text = "البوت ينزل لك أي صورة، فيديو، أو ستوري أنزله بحسابي في الإنستا (@x_zk9) حياكم الله 🤍"
    bot.send_message(message.chat.id, welcome_text, reply_markup=get_keyboard())

@bot.message_handler(commands=['addvideo'])
def add_video(message):
    """ يطلب من المالكين إرسال الفيديو """
    if message.chat.id in OWNER_IDS:
        bot.send_message(message.chat.id, "🎥 أرسل الفيديو اللي تبي تضيفه:")
        user_state[message.chat.id] = "waiting_for_video"
    else:
        bot.send_message(message.chat.id, "❌ فقط الملاك يمكنهم إضافة الفيديوهات!")

@bot.message_handler(commands=['addphoto'])
def add_photo(message):
    """ يطلب من المالكين إرسال الصورة """
    if message.chat.id in OWNER_IDS:
        bot.send_message(message.chat.id, "📷 أرسل الصورة اللي تبي تضيفها:")
        user_state[message.chat.id] = "waiting_for_photo"
    else:
        bot.send_message(message.chat.id, "❌ فقط الملاك يمكنهم إضافة الصور!")

@bot.message_handler(commands=['message'])
def add_message(message):
    """ يطلب من المالكين إضافة زر نص """
    if message.chat.id in OWNER_IDS:
        bot.send_message(message.chat.id, "📝 أرسل النص الذي تريده للزر:")
        user_state[message.chat.id] = "waiting_for_message"
    else:
        bot.send_message(message.chat.id, "❌ فقط الملاك يمكنهم إضافة الأزرار النصية!")

@bot.message_handler(commands=['del'])
def delete_button(message):
    """ يطلب من المالكين اختيار الزر الذي يريدون حذفه """
    if message.chat.id in OWNER_IDS:
        if not buttons:
            bot.send_message(message.chat.id, "❌ لا يوجد أزرار لحذفها.")
            return
        
        # عرض الأزرار للمستخدم للاختيار
        button_names = [btn['name'] for btn in buttons]
        bot.send_message(message.chat.id, "🔴 اختر الزر الذي ترغب في حذفه:", reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(btn)] for btn in button_names], resize_keyboard=True, one_time_keyboard=True))
        user_state[message.chat.id] = "waiting_for_delete"
    else:
        bot.send_message(message.chat.id, "❌ فقط الملاك يمكنهم حذف الأزرار!")

@bot.message_handler(content_types=['video'])
def handle_video(message):
    """ يخزن الفيديو ويطلب اسم الزر """
    if user_state.get(message.chat.id) == "waiting_for_video":
        file_id = message.video.file_id
        user_state[message.chat.id] = {"type": "video", "file_id": file_id}
        bot.send_message(message.chat.id, "🎬 وش تبي يكون اسم الزر؟")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    """ يخزن الصورة ويطلب اسم الزر """
    if user_state.get(message.chat.id) == "waiting_for_photo":
        file_id = message.photo[-1].file_id  # يستخدم أعلى جودة للصورة
        user_state[message.chat.id] = {"type": "photo", "file_id": file_id}
        bot.send_message(message.chat.id, "🖼 وش تبي يكون اسم الزر؟")

@bot.message_handler(func=lambda message: message.chat.id in user_state and isinstance(user_state[message.chat.id], dict))
def save_button(message):
    """ يحفظ اسم الزر ويضيفه للقائمة """
    user_data = user_state.pop(message.chat.id)
    buttons.append({
        "name": message.text,  # اسم الزر
        "type": user_data["type"] if 'type' in user_data else "text",  # نوع الملف (صورة أو فيديو أو نص)
        "file_id": user_data.get("file_id", "")  # الملف نفسه (قد يكون فارغًا للنصوص)
    })

    # حفظ الأزرار في ملف JSON
    with open(BUTTONS_FILE, "w") as f:
        json.dump(buttons, f, ensure_ascii=False, indent=4)
    
    # إرسال رسالة تأكيد
    bot.send_message(message.chat.id, f"✅ تم إضافة الزر '{message.text}' بنجاح!")

@bot.message_handler(func=lambda message: message.chat.id in user_state and user_state[message.chat.id] == "waiting_for_delete")
def delete_selected_button(message):
    """ حذف الزر المختار من القائمة """
    button_name = message.text
    btn_to_delete = next((btn for btn in buttons if btn["name"] == button_name), None)
    if btn_to_delete:
        buttons.remove(btn_to_delete)
        # حفظ الأزرار بعد الحذف
        with open(BUTTONS_FILE, "w") as f:
            json.dump(buttons, f, ensure_ascii=False, indent=4)
        
        bot.send_message(message.chat.id, f"✅ تم حذف الزر '{button_name}' بنجاح!")
        user_state[message.chat.id] = None  # إعادة تعيين الحالة
    else:
        bot.send_message(message.chat.id, "❌ الزر المحدد غير موجود!")
        user_state[message.chat.id] = None  # إعادة تعيين الحالة

@bot.message_handler(func=lambda message: message.text in [btn['name'] for btn in buttons])
def send_media_or_text(message):
    """ يرسل الصورة أو الفيديو أو النص عند الضغط على الزر """
    btn = next(btn for btn in buttons if btn['name'] == message.text)  # البحث عن الزر المناسب
    file_id = btn.get("file_id", "")

    if btn["type"] == "video":
        bot.send_video(message.chat.id, file_id, caption="🎥 هذا الفيديو!")
    elif btn["type"] == "photo":
        bot.send_photo(message.chat.id, file_id, caption="📷 هذه الصورة!")
    elif btn["type"] == "text":
        bot.send_message(message.chat.id, file_id)  # إرسال النص

# تشغيل البوت
print("✅ البوت شغال...")
bot.polling()
