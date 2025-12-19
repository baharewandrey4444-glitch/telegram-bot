import os
import time
import logging
from telebot import TeleBot, types
import sys

# ============ НАСТРОЙКИ ============
# Получаем из переменных окружения или используем значения по умолчанию
BOT_TOKEN = os.environ.get('BOT_TOKEN', '7774651689:AAHvbFuyt24EkWrSUWgIASP853LP_GnjA0M')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '6605628273'))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

bot = TeleBot(BOT_TOKEN)

# ============ БАЗА ДАННЫХ (SQLite) ============
import sqlite3
import datetime

DB_NAME = "bot_database.db"


def init_database():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Таблица пользователей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        messages_count INTEGER DEFAULT 0
    )
    ''')

    # Таблица сообщений
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        message_type TEXT,
        content TEXT,
        chat_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''')

    conn.commit()
    conn.close()
    logger.info("✅ База данных инициализирована")


def save_user(user_id, username, first_name, last_name):
    """Сохранение пользователя в БД"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
        VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name))

        # Увеличиваем счетчик сообщений
        cursor.execute('''
        UPDATE users SET messages_count = messages_count + 1 
        WHERE user_id = ?
        ''', (user_id,))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения пользователя: {e}")
        return False


def save_message(user_id, message_type, content, chat_id):
    """Сохранение сообщения в БД"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute('''
        INSERT INTO messages (user_id, message_type, content, chat_id)
        VALUES (?, ?, ?, ?)
        ''', (user_id, message_type, str(content)[:500], chat_id))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения сообщения: {e}")
        return False


def get_user_stats(user_id):
    """Получение статистики пользователя"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute('''
        SELECT u.username, u.first_name, u.messages_count,
               (SELECT COUNT(*) FROM messages WHERE user_id = ?) as total_messages,
               (SELECT created_at FROM messages WHERE user_id = ? 
                ORDER BY created_at DESC LIMIT 1) as last_message
        FROM users u
        WHERE u.user_id = ?
        ''', (user_id, user_id, user_id))

        result = cursor.fetchone()
        conn.close()

        return result
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики: {e}")
        return None


# ============ КОМАНДЫ БОТА ============
@bot.message_handler(commands=['start'])
def start_command(message):
    """Обработка команды /start"""
    user = message.from_user

    # Сохраняем пользователя
    save_user(user.id, user.username, user.first_name, user.last_name)

    if user.id == ADMIN_ID:
        response = (
            "🔒 <b>Привет, Администратор!</b>\n\n"
            "Бот успешно запущен на Render.com 🚀\n"
            f"🆔 Ваш ID: {user.id}\n"
            f"👤 Имя: {user.first_name}\n\n"
            "📊 <b>Доступные команды:</b>\n"
            "/stats - статистика бота\n"
            "/users - список пользователей\n"
            "/id - узнать свой ID"
        )
    else:
        response = (
            f"👋 <b>Привет, {user.first_name}!</b>\n\n"
            "Я бот для связи с администратором.\n"
            "Просто напишите сообщение, и я его перешлю.\n\n"
            "📝 Все сообщения сохраняются в базу данных."
        )

    bot.reply_to(message, response, parse_mode='HTML')
    save_message(user.id, 'command', '/start', message.chat.id)


@bot.message_handler(commands=['stats'])
def stats_command(message):
    """Статистика бота"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Эта команда только для администратора!")
        return

    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Общая статистика
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM messages")
        total_messages = cursor.fetchone()[0]

        # Последние 5 пользователей
        cursor.execute('''
        SELECT user_id, username, first_name, messages_count 
        FROM users 
        ORDER BY created_at DESC 
        LIMIT 5
        ''')
        recent_users = cursor.fetchall()

        conn.close()

        # Формируем ответ
        stats_text = (
            "📊 <b>Статистика бота</b>\n\n"
            f"👥 Всего пользователей: {total_users}\n"
            f"💬 Всего сообщений: {total_messages}\n\n"
            "🆕 <b>Последние пользователи:</b>\n"
        )

        for user in recent_users:
            user_id, username, first_name, msg_count = user
            username_display = f"@{username}" if username else "без username"
            stats_text += f"• {first_name} ({username_display}) - {msg_count} сообщ.\n"

        stats_text += "\n✅ Бот работает стабильно на Render!"

        bot.reply_to(message, stats_text, parse_mode='HTML')

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка получения статистики: {e}")


@bot.message_handler(commands=['id'])
def id_command(message):
    """Показывает ID пользователя"""
    user = message.from_user
    response = (
        f"🆔 <b>Ваши ID:</b>\n"
        f"• User ID: <code>{user.id}</code>\n"
        f"• Chat ID: <code>{message.chat.id}</code>\n\n"
        "Используйте эти ID для настроек."
    )
    bot.reply_to(message, response, parse_mode='HTML')


@bot.message_handler(content_types=['text'])
def handle_text(message):
    """Обработка текстовых сообщений"""
    user = message.from_user
    text = message.text

    # Сохраняем пользователя и сообщение
    save_user(user.id, user.username, user.first_name, user.last_name)
    save_message(user.id, 'text', text, message.chat.id)

    # Если сообщение от админа
    if user.id == ADMIN_ID:
        bot.reply_to(message, "✅ Сообщение сохранено в БД")
        return

    # Пересылаем админу
    try:
        admin_message = (
            f"📩 <b>Новое сообщение</b>\n\n"
            f"👤 От: {user.first_name}\n"
            f"🆔 ID: {user.id}\n"
            f"📝 Текст: {text}"
        )

        bot.send_message(ADMIN_ID, admin_message, parse_mode='HTML')
        bot.reply_to(message, "✅ Ваше сообщение доставлено администратору!")

    except Exception as e:
        logger.error(f"Ошибка отправки админу: {e}")
        bot.reply_to(message, "⚠️ Произошла ошибка при отправке сообщения")


# ============ ЗАПУСК БОТА ============
def main():
    """Основная функция запуска"""
    logger.info("=" * 50)
    logger.info("🤖 ЗАПУСК ТЕЛЕГРАМ БОТА")
    logger.info(f"🔑 Токен: {BOT_TOKEN[:10]}...")
    logger.info(f"👤 Админ ID: {ADMIN_ID}")
    logger.info(f"🌐 Хостинг: Render.com")
    logger.info("=" * 50)

    # Инициализируем БД
    init_database()

    # Проверяем подключение
    try:
        bot_info = bot.get_me()
        logger.info(f"✅ Бот подключен: @{bot_info.username}")
        logger.info(f"✅ Имя бота: {bot_info.first_name}")
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к Telegram: {e}")
        return

    # Запускаем бота с переподключением при ошибках
    while True:
        try:
            logger.info("🔄 Запуск polling...")
            bot.polling(none_stop=True, interval=2, timeout=30)
        except Exception as e:
            logger.error(f"❌ Ошибка в работе бота: {e}")
            logger.info("⏸ Пауза 15 секунд перед переподключением...")
            time.sleep(15)


if __name__ == '__main__':
    main()