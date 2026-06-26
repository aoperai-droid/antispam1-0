import os
import json
import asyncio
from datetime import datetime
from typing import Set, Dict, List
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram.constants import ChatMemberStatus

# Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

# Файл для хранения запрещенных слов
BANNED_WORDS_FILE = 'banned_words.json'

class WordModerator:
    def __init__(self):
        self.banned_words: Set[str] = set()
        self.load_words()

    def load_words(self):
        """Загрузка списка запрещенных слов из файла"""
        try:
            with open(BANNED_WORDS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.banned_words = set(data.get('words', []))
        except FileNotFoundError:
            self.banned_words = set()
            self.save_words()

    def save_words(self):
        """Сохранение списка запрещенных слов в файл"""
        with open(BANNED_WORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump({'words': list(self.banned_words)}, f, ensure_ascii=False, indent=2)

    def add_word(self, word: str) -> bool:
        """Добавление слова в список"""
        word = word.lower().strip()
        if word and word not in self.banned_words:
            self.banned_words.add(word)
            self.save_words()
            return True
        return False

    def remove_word(self, word: str) -> bool:
        """Удаление слова из списка"""
        word = word.lower().strip()
        if word in self.banned_words:
            self.banned_words.remove(word)
            self.save_words()
            return True
        return False

    def check_message(self, text: str) -> List[str]:
        """Проверка сообщения на наличие запрещенных слов"""
        if not text:
            return []
        
        text_lower = text.lower()
        found_words = []
        
        for word in self.banned_words:
            if word in text_lower:
                found_words.append(word)
        
        return found_words

# Инициализация модератора
moderator = WordModerator()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Извините, у вас нет доступа к этому боту.")
        return
    
    keyboard = [
        [InlineKeyboardButton("📋 Список запрещенных слов", callback_data='list_words')],
        [InlineKeyboardButton("➕ Добавить слово", callback_data='add_word_menu')],
        [InlineKeyboardButton("➖ Удалить слово", callback_data='remove_word_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🛡 *Модератор сообщений*\n\n"
        "Выберите действие:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("У вас нет доступа к управлению.")
        return
    
    data = query.data
    
    if data == 'list_words':
        await show_words_list(query, context)
    
    elif data == 'add_word_menu':
        context.user_data['action'] = 'add_word'
        await query.edit_message_text(
            "📝 Отправьте слово, которое хотите добавить в список запрещенных.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu')
            ]])
        )
    
    elif data == 'remove_word_menu':
        await show_remove_menu(query, context)
    
    elif data.startswith('remove_'):
        word = data.replace('remove_', '')
        if moderator.remove_word(word):
            await query.edit_message_text(
                f"✅ Слово '*{word}*' удалено из списка.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 К списку", callback_data='list_words'),
                    InlineKeyboardButton("🏠 В меню", callback_data='back_to_menu')
                ]])
            )
    
    elif data == 'back_to_menu':
        await show_main_menu(query)

async def show_main_menu(query):
    """Показ главного меню"""
    keyboard = [
        [InlineKeyboardButton("📋 Список запрещенных слов", callback_data='list_words')],
        [InlineKeyboardButton("➕ Добавить слово", callback_data='add_word_menu')],
        [InlineKeyboardButton("➖ Удалить слово", callback_data='remove_word_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🛡 *Модератор сообщений*\n\nВыберите действие:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_words_list(query, context):
    """Показ списка запрещенных слов"""
    if not moderator.banned_words:
        text = "📋 Список запрещенных слов пуст."
        keyboard = [[InlineKeyboardButton("🏠 В меню", callback_data='back_to_menu')]]
    else:
        text = "📋 *Запрещенные слова:*\n\n"
        for i, word in enumerate(sorted(moderator.banned_words), 1):
            text += f"{i}. `{word}`\n"
        
        keyboard = [[InlineKeyboardButton("🏠 В меню", callback_data='back_to_menu')]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_remove_menu(query, context):
    """Показ меню удаления слов"""
    if not moderator.banned_words:
        await query.edit_message_text(
            "📋 Список запрещенных слов пуст.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 В меню", callback_data='back_to_menu')
            ]])
        )
        return
    
    keyboard = []
    for word in sorted(moderator.banned_words):
        keyboard.append([InlineKeyboardButton(
            f"❌ {word}", 
            callback_data=f'remove_{word}'
        )])
    
    keyboard.append([InlineKeyboardButton("🏠 В меню", callback_data='back_to_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Выберите слово для удаления:",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик сообщений от администратора"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    user_data = context.user_data
    
    if 'action' in user_data and user_data['action'] == 'add_word':
        word = update.message.text.strip()
        
        if moderator.add_word(word):
            await update.message.reply_text(
                f"✅ Слово '*{word}*' добавлено в список запрещенных.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 В меню", callback_data='back_to_menu')
                ]])
            )
        else:
            await update.message.reply_text(
                f"⚠️ Слово '*{word}*' уже есть в списке или некорректно.",
                parse_mode='Markdown'
            )
        
        user_data['action'] = None

async def group_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик сообщений в группах"""
    # Проверяем, что сообщение из группы
    if not update.effective_chat or update.effective_chat.type == 'private':
        return
    
    message = update.effective_message
    if not message or not message.text:
        return
    
    # Проверяем сообщение на запрещенные слова
    found_words = moderator.check_message(message.text)
    
    if found_words:
        try:
            user_id = message.from_user.id
            chat_id = update.effective_chat.id
            user_name = message.from_user.full_name
            user_mention = f"@{message.from_user.username}" if message.from_user.username else user_name
            
            # Удаляем сообщение
            await message.delete()
            
            # Пытаемся удалить последние сообщения пользователя
            try:
                # Получаем историю сообщений (последние 10)
                deleted_count = 1
                async for msg in context.bot.get_chat_history(chat_id, limit=10):
                    if msg.from_user and msg.from_user.id == user_id and msg.message_id != message.message_id:
                        try:
                            await msg.delete()
                            deleted_count += 1
                            await asyncio.sleep(0.5)  # Небольшая задержка между удалениями
                        except:
                            break
            except:
                pass
            
            # Ограничиваем пользователя (временно блокируем возможность писать)
            try:
                # Блокируем на 1 минуту
                until_date = datetime.now().timestamp() + 60
                await context.bot.ban_chat_member(
                    chat_id=chat_id,
                    user_id=user_id,
                    until_date=until_date
                )
                
                # Разбаниваем чтобы применить временное ограничение
                await context.bot.unban_chat_member(
                    chat_id=chat_id,
                    user_id=user_id
                )
            except Exception as e:
                print(f"Не удалось ограничить пользователя: {e}")
            
            # Отправляем уведомление администратору
            admin_message = (
                f"🚫 *Обнаружено нарушение*\n\n"
                f"👤 Пользователь: {user_mention}\n"
                f"🆔 ID: `{user_id}`\n"
                f"💬 Чат: {update.effective_chat.title}\n"
                f"🔍 Запрещенные слова: {', '.join(f'`{word}`' for word in found_words)}\n\n"
                f"📝 Текст сообщения:\n"
                f"```\n{message.text[:500]}\n```\n\n"
                f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"🗑 Удалено сообщений: {deleted_count}"
            )
            
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            print(f"Ошибка при обработке нарушения: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    print(f"Ошибка: {context.error}")

def main():
    """Запуск бота"""
    if not BOT_TOKEN or not ADMIN_ID:
        print("Ошибка: Необходимо указать BOT_TOKEN и ADMIN_ID в файле .env")
        return
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Обработчик личных сообщений от админа
    application.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & filters.User(user_id=ADMIN_ID),
        handle_message
    ))
    
    # Обработчик групповых сообщений
    application.add_handler(MessageHandler(
        filters.TEXT & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
        group_message_handler
    ))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    print("🤖 Бот запущен и готов к работе...")
    print(f"📋 Загружено запрещенных слов: {len(moderator.banned_words)}")
    
    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
