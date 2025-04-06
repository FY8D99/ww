import os
import logging
import datetime
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler
from telegram.ext import ContextTypes, filters
import speech_recognition as sr
import whisper
from pytesseract import pytesseract
from PIL import Image
import io

# تكوين التسجيل
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# متغيرات عامة
BOT_TOKEN = "7833766177:AAGpudJYzcVln3irns7E1CUq1aYxMs4907Y"  # قم باستبدال هذا بالتوكن الخاص بك
OWNER_ID = 6201724109  # قم باستبدال هذا بمعرف المالك الخاص بك
DEVELOPER_USERNAME = "RRLeo"
CHANNEL_URL = "https://t.me/RRLeos"  # قم باستبدال هذا برابط القناة الخاصة بك
BOT_ACTIVE = True  # حالة البوت (نشط أم متوقف)

# إعداد قاعدة البيانات
def setup_database():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()

    # جدول المستخدمين
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        join_date TEXT,
        last_active TEXT,
        message_count INTEGER DEFAULT 0
    )
    ''')

    # جدول الإحصائيات
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stats (
        date TEXT PRIMARY KEY,
        active_users INTEGER DEFAULT 0,
        total_messages INTEGER DEFAULT 0
    )
    ''')

    conn.commit()
    conn.close()

# إضافة أو تحديث مستخدم في قاعدة البيانات
def update_user(user_id, username, first_name, last_name):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()

    # التحقق مما إذا كان المستخدم موجودًا
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if user is None:
        # إضافة مستخدم جديد
        cursor.execute('''
        INSERT INTO users (user_id, username, first_name, last_name, join_date, last_active)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name, current_time, current_time))
    else:
        # تحديث آخر نشاط للمستخدم
        cursor.execute('''
        UPDATE users SET username = ?, first_name = ?, last_name = ?, last_active = ?
        WHERE user_id = ?
        ''', (username, first_name, last_name, current_time, user_id))

    conn.commit()
    conn.close()

# تحديث عدد الرسائل للمستخدم
def increment_message_count(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()

    # زيادة عدد الرسائل
    cursor.execute("UPDATE users SET message_count = message_count + 1 WHERE user_id = ?", (user_id,))

    # تحديث الإحصائيات اليومية
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT * FROM stats WHERE date = ?", (today,))
    stats = cursor.fetchone()

    if stats is None:
        cursor.execute("INSERT INTO stats (date, total_messages, active_users) VALUES (?, 1, 1)", (today,))
    else:
        cursor.execute("UPDATE stats SET total_messages = total_messages + 1 WHERE date = ?", (today,))

    conn.commit()
    conn.close()

# تحديث المستخدمين النشطين
def update_active_users(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()

    today = datetime.datetime.now().strftime("%Y-%m-%d")

    # تحقق مما إذا كان المستخدم نشطًا بالفعل اليوم
    cursor.execute("SELECT last_active FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if result and not result[0].startswith(today):
        # هذا أول نشاط للمستخدم اليوم
        cursor.execute("SELECT * FROM stats WHERE date = ?", (today,))
        stats = cursor.fetchone()

        if stats is None:
            cursor.execute("INSERT INTO stats (date, active_users) VALUES (?, 1)", (today,))
        else:
            cursor.execute("UPDATE stats SET active_users = active_users + 1 WHERE date = ?", (today,))

    conn.commit()
    conn.close()

# الحصول على إحصائيات البوت
def get_bot_stats():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()

    # إجمالي المستخدمين
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    # إجمالي الرسائل
    cursor.execute("SELECT SUM(message_count) FROM users")
    total_messages = cursor.fetchone()[0] or 0

    # المستخدمين النشطين اليوم
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT active_users FROM stats WHERE date = ?", (today,))
    result = cursor.fetchone()
    active_today = result[0] if result else 0

    # الرسائل اليوم
    cursor.execute("SELECT total_messages FROM stats WHERE date = ?", (today,))
    result = cursor.fetchone()
    messages_today = result[0] if result else 0

    conn.close()

    return {
        "total_users": total_users,
        "total_messages": total_messages,
        "active_today": active_today,
        "messages_today": messages_today
    }

# أزرار القائمة الرئيسية
def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("ماذا يمكنني أن أفعل؟", callback_data="what_can_i_do")],
        [InlineKeyboardButton("المطور 👨‍💻", url=f"https://t.me/{DEVELOPER_USERNAME}")],
        [InlineKeyboardButton("قناة البوت 📢", url=CHANNEL_URL)]
    ]
    return InlineKeyboardMarkup(keyboard)

# أزرار قائمة المالك
def get_owner_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("إحصائيات البوت 📊", callback_data="bot_stats")],
        [InlineKeyboardButton("إشعارات دخول الأعضاء 👤", callback_data="toggle_notifications")],
        [InlineKeyboardButton("إضافة زر جديد ➕", callback_data="add_button")]
    ]
    return InlineKeyboardMarkup(keyboard)

# مشغل الأمر start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    # تحديث معلومات المستخدم في قاعدة البيانات
    update_user(user.id, user.username, user.first_name, user.last_name)
    update_active_users(user.id)

    # إشعار المالك بدخول مستخدم جديد
    if context.bot_data.get("notify_new_users", True):
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notification_text = (
            f"🔔 *مستخدم جديد دخل البوت*\n\n"
            f"الاسم: {user.first_name} {user.last_name or ''}\n"
            f"المعرف: @{user.username or 'لا يوجد'}\n"
            f"معرف المستخدم: `{user.id}`\n"
            f"وقت الدخول: {current_time}"
        )
        try:
            await context.bot.send_message(chat_id=OWNER_ID, text=notification_text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"خطأ في إرسال إشعار المستخدم الجديد: {e}")

    # إرسال رسالة الترحيب
        welcome_message = (
        f"👋 مرحبًا {user.first_name}!\n\n"
        "أنا بوت متعدد المهام يمكنني:\n"
        "• تحويل الصور إلى نص (OCR) 📷➡️📝\n"
        "• تحويل الصوت إلى نص ( يوجد صيانه!) 🎤➡️📝\n"
        "• استخراج النص من الفيديو ( يوجد صيانه! )🎬➡️📝\n\n"
        "التعرف يعمل باللغتين العربية والإنجليزية بشكل تلقائي.\n\n"
        "لانشاء بوت مشابه تواصل مع المطور @RRLeo.\n\n"
        "قم بإرسال صورة أو تسجيل صوتي أو فيديو للبدء!"
    )

    # إضافة قائمة المالك إذا كان المستخدم هو المالك
    if user.id == OWNER_ID:
        await update.message.reply_text(
            welcome_message + "\n\n🔐 *قائمة المالك:*",
            reply_markup=get_owner_menu_keyboard(),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            welcome_message,
            reply_markup=get_main_menu_keyboard()
        )

# مشغل أمر الإيقاف المؤقت
async def stop_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    if user.id == OWNER_ID:
        global BOT_ACTIVE
        BOT_ACTIVE = False
        await update.message.reply_text("✋ تم إيقاف البوت مؤقتًا. لن يستجيب لأي مستخدم حتى يتم إعادة تشغيله.")
    else:
        await update.message.reply_text("⛔ عذرًا، هذا الأمر متاح فقط للمالك.")

# مشغل أمر إعادة التشغيل
async def start_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    if user.id == OWNER_ID:
        global BOT_ACTIVE
        BOT_ACTIVE = True
        await update.message.reply_text("✅ تم إعادة تشغيل البوت. يمكن للجميع استخدامه الآن.")
    else:
        await update.message.reply_text("⛔ عذرًا، هذا الأمر متاح فقط للمالك.")

# مشغل معالجة الصور
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    # التحقق من حالة البوت
    if not BOT_ACTIVE and user.id != OWNER_ID:
        await update.message.reply_text("⚠️ البوت متوقف مؤقتًا. يرجى المحاولة لاحقًا.")
        return

    # تحديث إحصائيات المستخدم
    update_user(user.id, user.username, user.first_name, user.last_name)
    update_active_users(user.id)
    increment_message_count(user.id)

    # إرسال رسالة انتظار
    processing_message = await update.message.reply_text("🔄 جاري معالجة الصورة...")

    try:
        # الحصول على أكبر نسخة من الصورة
        photo_file = await update.message.photo[-1].get_file()
        photo_data = await photo_file.download_as_bytearray()

        # تحويل البيانات إلى صورة
        image = Image.open(io.BytesIO(photo_data))

        # استخراج النص باستخدام Tesseract OCR
        extracted_text = pytesseract.image_to_string(image, lang='ara+eng')

        if extracted_text.strip():
            await processing_message.edit_text(
                f"📝 *النص المستخرج من الصورة:*\n\n{extracted_text}",
                parse_mode="Markdown"
            )
        else:
            await processing_message.edit_text("❌ لم يتم العثور على نص في الصورة.")

    except Exception as e:
        logger.error(f"خطأ في معالجة الصورة: {e}")
        await processing_message.edit_text("❌ حدث خطأ أثناء معالجة الصورة. يرجى المحاولة مرة أخرى.")

# مشغل معالجة الصوت
# مشغل معالجة الصوت محسّن
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    # التحقق من حالة البوت
    if not BOT_ACTIVE and user.id != OWNER_ID:
        await update.message.reply_text("⚠️ البوت متوقف مؤقتًا. يرجى المحاولة لاحقًا.")
        return

    # تحديث إحصائيات المستخدم
    update_user(user.id, user.username, user.first_name, user.last_name)
    update_active_users(user.id)
    increment_message_count(user.id)

    # إرسال رسالة انتظار
    processing_message = await update.message.reply_text("🔄 جاري معالجة الصوت...")

    try:
        # الحصول على ملف الصوت
        voice_file = await update.message.voice.get_file()
        voice_data = await voice_file.download_as_bytearray()

        # حفظ ملف الصوت مؤقتًا
        voice_path = f"temp_voice_{user.id}.ogg"
        with open(voice_path, "wb") as f:
            f.write(voice_data)

        # إضافة بعض المعلومات للتشخيص
        await processing_message.edit_text("🔄 جاري تحميل نموذج التعرف على الكلام...")

        # تحميل نموذج Whisper للتعرف على الكلام - استخدام نموذج أكبر للحصول على دقة أعلى
        model = whisper.load_model("medium")  # تغيير من "base" إلى "medium" للحصول على دقة أفضل

        await processing_message.edit_text("🔄 جاري استخراج النص من الصوت...")

        # التعرف على الكلام مع إضافة خيارات متقدمة
        options = {
            "language": None,  # للكشف التلقائي عن اللغة
            "task": "transcribe",
            "beam_size": 5,  # قيمة أعلى تعطي نتائج أكثر دقة على حساب السرعة
            "best_of": 5,     # قيمة أعلى تعطي نتائج أكثر دقة على حساب السرعة
            "fp16": False,    # استخدام دقة كاملة
            "temperature": 0, # قيمة أقل تعطي نتائج أكثر حزمًا
            "compression_ratio_threshold": 2.4,
            "no_speech_threshold": 0.6,
            "condition_on_previous_text": True,
            "initial_prompt": None,  # يمكن استخدامه لإعطاء سياق للنموذج
        }

        result = model.transcribe(voice_path, **options)
        transcribed_text = result["text"]

        # معلومات إضافية مفيدة
        detected_language = result.get("language", "غير معروفة")
        segments = result.get("segments", [])
        total_duration = sum(seg.get("end", 0) - seg.get("start", 0) for seg in segments)
        confidence = sum(seg.get("confidence", 0) for seg in segments) / len(segments) if segments else 0

# حذف الملف المؤقت
        os.remove(voice_path)

        if transcribed_text.strip():
            response_text = (
                f"🎤 *النص المستخرج من الصوت:*\n\n{transcribed_text}\n\n"
                f"📊 *معلومات إضافية:*\n"
                f"• اللغة المكتشفة: {detected_language}\n"
                f"• عدد المقاطع: {len(segments)}\n"
                f"• المدة الإجمالية: {total_duration:.2f} ثانية\n"
                f"• متوسط الثقة: {confidence*100:.1f}%"
            )
            await processing_message.edit_text(response_text, parse_mode="Markdown")
        else:
            await processing_message.edit_text("يوجد صيانه في الاستخراج الصوتي !!")

    except Exception as e:
        logger.error(f"خطأ في معالجة الصوت: {e}")
        await processing_message.edit_text(f"🔄 جاري المحاولة مرة أخرى...")
        
        try:
            # تبسيط عملية المعالجة باستخدام نموذج أصغر
            model = whisper.load_model("tiny")  # استخدام نموذج أصغر
            result = model.transcribe(voice_path)
            transcribed_text = result["text"]
            
            # حذف الملف المؤقت
            os.remove(voice_path)
            
            if transcribed_text.strip():
                await processing_message.edit_text(
                    f"🎤 *النص المستخرج من الصوت:*\n\n{transcribed_text}",
                    parse_mode="Markdown"
                )
            else:
                await processing_message.edit_text("❌ لم يتم التعرف على أي نص في التسجيل الصوتي.")
                
        except Exception as e2:
            logger.error(f"فشل في المحاولة الثانية: {e2}")
            await processing_message.edit_text("❌ تعذر استخراج النص من الصوت. يرجى التأكد من جودة التسجيل وحاول مرة أخرى.")

# مشغل معالجة الفيديو محسّن
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    # التحقق من حالة البوت
    if not BOT_ACTIVE and user.id != OWNER_ID:
        await update.message.reply_text("⚠️ البوت متوقف مؤقتًا. يرجى المحاولة لاحقًا.")
        return

    # تحديث إحصائيات المستخدم
    update_user(user.id, user.username, user.first_name, user.last_name)
    update_active_users(user.id)
    increment_message_count(user.id)

    # إرسال رسالة انتظار
    processing_message = await update.message.reply_text("🔄 جاري معالجة الفيديو (قد يستغرق هذا بعض الوقت)...")

    try:
        # الحصول على ملف الفيديو
        video_file = await update.message.video.get_file()
        video_data = await video_file.download_as_bytearray()

        # حفظ ملف الفيديو مؤقتًا
        video_path = f"temp_video_{user.id}.mp4"
        audio_path = f"temp_audio_{user.id}.wav"

        with open(video_path, "wb") as f:
            f.write(video_data)

        await processing_message.edit_text("🔄 جاري استخراج الصوت من الفيديو...")

        # تأكد من استيراد مكتبة moviepy بشكل صحيح
        import moviepy.editor as mp

        # استخراج الصوت من الفيديو
        video = mp.VideoFileClip(video_path)

        # استخراج الصوت بجودة أعلى
        video.audio.write_audiofile(audio_path, 
                                   fps=44100,  # معدل عينات أعلى
                                   nbytes=4,   # 32-bit للجودة
                                   codec='pcm_s16le')  # ترميز غير مضغوط

        await processing_message.edit_text("🔄 جاري تحميل نموذج التعرف على الكلام...")

        # تحميل نموذج Whisper للتعرف على الكلام - استخدام نموذج أكبر للحصول على دقة أعلى
        model = whisper.load_model("medium")  # تغيير من "base" إلى "medium" للحصول على دقة أفضل

        await processing_message.edit_text("🔄 جاري استخراج النص من الفيديو...")

        # التعرف على الكلام مع إضافة خيارات متقدمة
        options = {
            "language": None,  # للكشف التلقائي عن اللغة
            "task": "transcribe",
            "beam_size": 5,
            "best_of": 5,
            "fp16": False,
            "temperature": 0,
            "compression_ratio_threshold": 2.4,
            "no_speech_threshold": 0.6,
            "condition_on_previous_text": True,
            "word_timestamps": True,  # الحصول على توقيت لكل كلمة
        }

        result = model.transcribe(audio_path, **options)
        transcribed_text = result["text"]

        # معلومات إضافية مفيدة
        detected_language = result.get("language", "غير معروفة")
        segments = result.get("segments", [])

        # إنشاء ملف نصي يحتوي على النص مع الوقت
        subtitle_path = f"subtitle_{user.id}.srt"
        with open(subtitle_path, "w", encoding="utf-8") as srt_file:
            for i, segment in enumerate(segments):
                start_time = segment.get("start", 0)
                end_time = segment.get("end", 0)
                text = segment.get("text", "")

                # تنسيق SRT
                start_formatted = convert_seconds_to_srt_time(start_time)
                end_formatted = convert_seconds_to_srt_time(end_time)

                srt_file.write(f"{i+1}\n")
                srt_file.write(f"{start_formatted} --> {end_formatted}\n")
                srt_file.write(f"{text.strip()}\n\n")

        # حذف الملفات المؤقتة
        os.remove(video_path)
        os.remove(audio_path)

        if transcribed_text.strip():
            response_text = (
                f"🎬 *النص المستخرج من الفيديو:*\n\n{transcribed_text}\n\n"
                f"📊 *معلومات إضافية:*\n"
                f"• اللغة المكتشفة: {detected_language}\n"
                f"• عدد المقاطع: {len(segments)}\n"
                f"• مدة الفيديو: {segments[-1].get('end', 0):.2f} ثانية\n"
            )

            # إرسال ملف الترجمة
            await update.message.reply_document(
                document=open(subtitle_path, "rb"),
                filename=f"ترجمة_{user.id}.srt",
                caption="📝 ملف الترجمة مع التوقيت"
            )

            os.remove(subtitle_path)
            await processing_message.edit_text(response_text, parse_mode="Markdown")
        else:
            await processing_message.edit_text("يوجد صيانه في الاستخراج الصوتي !!")

    except Exception as e:
        logger.error(f"خطأ في معالجة الفيديو: {e}")
        await processing_message.edit_text(f"🔄 جاري المحاولة بطريقة مبسطة...")
        
        try:
            # محاولة مبسطة لمعالجة الفيديو
            import moviepy.editor as mp
            
            # حفظ ملف الفيديو مؤقتًا إذا لم يكن موجودًا بالفعل
            if not os.path.exists(video_path):
                video_file = await update.message.video.get_file()
                video_data = await video_file.download_as_bytearray()
                with open(video_path, "wb") as f:
                    f.write(video_data)
            
            # استخراج الصوت بإعدادات أبسط
            video = mp.VideoFileClip(video_path)
            video.audio.write_audiofile(audio_path)
            
            # استخدام نموذج أصغر
            model = whisper.load_model("tiny")
            result = model.transcribe(audio_path)
            transcribed_text = result["text"]
            
            # حذف الملفات المؤقتة
            if os.path.exists(video_path):
                os.remove(video_path)
            if os.path.exists(audio_path):
                os.remove(audio_path)
            
            if transcribed_text.strip():
                await processing_message.edit_text(
                    f"🎬 *النص المستخرج من الفيديو:*\n\n{transcribed_text}",
                    parse_mode="Markdown"
                )
            else:
                await processing_message.edit_text("❌ لم يتم التعرف على أي نص في الفيديو.")
                
        except Exception as e2:
            logger.error(f"فشل في المحاولة المبسطة: {e2}")
            await processing_message.edit_text("❌ تعذر استخراج النص من الفيديو. يرجى التأكد من جودة الفيديو وحاول مرة أخرى.")
            
# معالج الضغطات على الأزرار
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user
    
    # معالجة الضغطات المختلفة
    if query.data == "what_can_i_do":
        help_text = (
            "*ماذا يمكنني أن أفعل؟* 🤔\n\n"
            "يمكنني مساعدتك في المهام التالية:\n\n"
            "1️⃣ *تحويل الصور إلى نص*:\n"
            "   أرسل صورة تحتوي على نص وسأقوم باستخراجه.\n\n"
            "2️⃣ *تحويل الصوت إلى نص*:\n"
            "   أرسل تسجيلًا صوتيًا وسأقوم بتحويله إلى نص.\n\n"
            "3️⃣ *استخراج النص من الفيديو*:\n"
            "   أرسل مقطع فيديو وسأستخرج النص من الصوت.\n\n"
            "✨ أدعم اللغتين العربية والإنجليزية تلقائيًا!"
        )
        await query.message.reply_text(help_text, parse_mode="Markdown")

    elif query.data == "bot_stats" and user.id == OWNER_ID:
        stats = get_bot_stats()
        stats_text = (
            "📊 *إحصائيات البوت*\n\n"
            f"👥 إجمالي المستخدمين: {stats['total_users']}\n"
            f"💬 إجمالي الرسائل: {stats['total_messages']}\n"
            f"👤 المستخدمون النشطون اليوم: {stats['active_today']}\n"
            f"📝 الرسائل اليوم: {stats['messages_today']}\n\n"
            f"⏱️ آخر تحديث: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        await query.message.reply_text(stats_text, parse_mode="Markdown")

    elif query.data == "toggle_notifications" and user.id == OWNER_ID:
        # تبديل إشعارات المستخدمين الجدد
        current_setting = context.bot_data.get("notify_new_users", True)
        context.bot_data["notify_new_users"] = not current_setting

        status = "تفعيل" if context.bot_data["notify_new_users"] else "تعطيل"
        await query.message.reply_text(f"✅ تم {status} إشعارات دخول الأعضاء الجدد.")

    elif query.data == "add_button" and user.id == OWNER_ID:
        await query.message.reply_text(
            "🔘 لإضافة زر جديد، يرجى إرسال الزر بالتنسيق التالي:\n\n"
            "`اسم_الزر | رابط_الزر`\n\n"
            "مثال: `قناتي | https://t.me/my_channel`"
        )
        # تعيين حالة المحادثة لانتظار البيانات
        context.user_data["waiting_for_button"] = True

    await query.answer()

# مشغل الرسائل النصية
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = update.message.text

    # تحديث إحصائيات المستخدم
    update_user(user.id, user.username, user.first_name, user.last_name)
    update_active_users(user.id)
    increment_message_count(user.id)

    # التحقق مما إذا كان المستخدم يضيف زرًا جديدًا
    if user.id == OWNER_ID and context.user_data.get("waiting_for_button"):
        if "|" in text:
            parts = text.split("|", 1)
            button_name = parts[0].strip()
            button_url = parts[1].strip()

            # إضافة الزر إلى قاعدة البيانات أو إعدادات البوت
            # (يمكن تنفيذ هذا حسب احتياجاتك)

            await update.message.reply_text(f"✅ تم إضافة الزر بنجاح:\n\n"
                                          f"الاسم: {button_name}\n"
                                          f"الرابط: {button_url}")
        else:
            await update.message.reply_text("❌ تنسيق غير صحيح. يرجى استخدام: `اسم_الزر | رابط_الزر`")

        # إعادة تعيين حالة المحادثة
        context.user_data["waiting_for_button"] = False

    # إذا لم يكن البوت في حالة معالجة خاصة، إظهار رسالة المساعدة
    else:
        await start(update, context)

# الدالة الرئيسية
def main() -> None:
    # إعداد قاعدة البيانات
    setup_database()

    # إنشاء التطبيق وإضافة المشغلات
    application = Application.builder().token(BOT_TOKEN).build()

    # مشغلات الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("stop_bot", stop_bot))
    application.add_handler(CommandHandler("start_bot", start_bot))

    # مشغلات الوسائط
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.VIDEO, handle_video))

    # مشغل الضغطات على الأزرار
    application.add_handler(CallbackQueryHandler(button_callback))

    # مشغل الرسائل النصية
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # بدء البوت
    application.run_polling()

if __name__ == "__main__":
    main()
