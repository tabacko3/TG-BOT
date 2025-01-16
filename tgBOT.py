import random
import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import ( Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext, Updater)

# ======================
# Данные о задачах
# ======================
# Словарь списков, где ключ — это уровень сложности, а значение — список задач.
# Каждая задача — это словарь: "question", "answer", "hint".
# Можно добавлять свои задачи по вкусу.

tasks_data = {
    "легко": [
        {
            "question": "Сколько будет 2+2?",
            "answer": "4",
            "hint": "Это базовая арифметика."
        },
        {
            "question": "Сколько букв в слове 'кот'?",
            "answer": "3",
            "hint": "К, О и Т."
        }
    ],
    "нормально": [
        {
            "question": "Сколько углов у треугольника?",
            "answer": "3",
            "hint": "Подсказка в самом названии."
        },
        {
            "question": "Что тяжелее: 1 кг ваты или 1 кг железа?",
            "answer": "одинаково",
            "hint": "Килограмм — это килограмм."
        }
    ],
    "сложно": [
        {
            "question": "Реши уравнение: x + 5 = 11. Чему равно x?",
            "answer": "6",
            "hint": "Перенесите 5 в другую сторону."
        },
        {
            "question": (
                "Если у тебя есть 5 яблок, и ты отдашь 2 другу, "
                "то сколько яблок у тебя останется?"
            ),
            "answer": "3",
            "hint": "Простая логика вычитания."
        }
    ],
    "очень сложно": [
        {
            "question": (
                "У Кати в кармане 8 конфет, а у Пети в кармане в 2 раза больше конфет, "
                "чем у Кати. Сколько конфет у Пети?"
            ),
            "answer": "16",
            "hint": "8 * 2 = 16."
        },
        {
            "question": (
                "Найди пропущенное число в последовательности: 1, 2, 4, 8, ...?"
            ),
            "answer": "16",
            "hint": "Каждый элемент в 2 раза больше предыдущего."
        }
    ],
    "невозможно": [
        {
            "question": (
                "На одну чашу весов кладут 2 таблетки А и 1 таблетку Б, "
                "а на другую — 1 таблетку А и 2 таблетки Б. "
                "Что легче, тяжелее или одинаково?"
            ),
            "answer": "одинаково",
            "hint": "2А+1Б vs. 1А+2Б — если считать массу каждой таблетки А и Б одинаковой между собой…"
        },
        {
            "question": (
                "Сколько существует способов выбрать 2 предмета из 5?"
            ),
            "answer": "10",
            "hint": "Комбинации C(n,k) = n! / (k!(n-k)!) = 5!/(2!*3!)=10"
        }
    ]
}

# Карта, определяющая, сколько очков даёт каждая задача в зависимости от сложности
difficulty_points = {
    "easy": 2,
    "normal": 2,
    "hard": 3,
    "very_hard": 4,
    "criminal_hard": 5
}

# ======================
# Базовые команды
# ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start — первое приветствие."""
    await update.message.reply_text(
        "Привет! Я бот-тренажёр логики и мышления.\n"
        "Для начала можешь /register (зарегистрироваться), затем /play (получить задачу).\n"
        "Все команды смотри в /help."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /help — помощь по командам."""
    text = (
        "Список доступных команд:\n"
        "/start — приветствие\n"
        "/register — зарегистрироваться (имя и фамилия)\n"
        "/play — начать тренировку (выбрать уровень сложности и получить задачу)\n"
        "/skip — пропустить текущую задачу и получить новую\n"
        "/hint — получить подсказку к текущей задаче\n"
        "/stats — вывести краткую статистику\n"
        "/profile — посмотреть свой профиль (имя, фамилия, уровень, очки, время решений)\n"
        "/help — показать это сообщение\n"
    )
    await update.message.reply_text(text)

# ======================
# Регистрация и профиль
# ======================

async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Команда /register.
    Ожидается, что пользователь введёт: /register Имя Фамилия.
    """
    # Парсим аргументы после /register
    args = update.message.text.split(maxsplit=2)
    if len(args) < 3:
        await update.message.reply_text(
            "Пожалуйста, укажи имя и фамилию через пробел. Пример:\n"
            "/register Иван Петров"
        )
        return

    name = args[1]
    surname = args[2]

    context.user_data['name'] = name
    context.user_data['surname'] = surname

    # Инициализируем стату при регистрации, если ещё не была инициализирована
    context.user_data.setdefault('score', 0)           # общее количество очков
    context.user_data.setdefault('level', 1)           # уровень пользователя
    context.user_data.setdefault('tasks_solved', 0)    # сколько задач всего решено
    context.user_data.setdefault('time_spent', 0)      # общее время на решение (секунды)
    context.user_data.setdefault('current_task', None) # текущая задача
    context.user_data.setdefault('task_start_time', None)  # время, когда начали решать текущую задачу

    await update.message.reply_text(
        f"Регистрация прошла успешно!\n"
        f"Привет, {name} {surname}.\n"
        "Теперь ты можешь использовать /play, чтобы получать задачи."
    )

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /profile — показывает профиль пользователя."""
    name = context.user_data.get('name')
    surname = context.user_data.get('surname')
    score = context.user_data.get('score', 0)
    level = context.user_data.get('level', 1)
    tasks_solved = context.user_data.get('tasks_solved', 0)
    time_spent = context.user_data.get('time_spent', 0)

    # Форматируем время (в секундах) в более читаемый вид, например, минуты и секунды
    minutes = time_spent // 60
    seconds = time_spent % 60

    if not name or not surname:
        await update.message.reply_text(
            "Ты ещё не зарегистрирован. Используй /register Имя Фамилия."
        )
        return

    profile_text = (
        f"Имя: {name}\n"
        f"Фамилия: {surname}\n"
        f"Уровень: {level}\n"
        f"Очки: {score}\n"
        f"Решено задач: {tasks_solved}\n"
        f"Общее время на решения: {minutes} мин. {seconds} сек."
    )
    await update.message.reply_text(profile_text)

# ======================
# Игровой процесс
# ======================

async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Команда /play — выбор сложности и выдача задачи.
    Сначала бот спросит, какую сложность выбрать.
    Далее пользователь отправит сообщение (easy, normal, hard и т.п.),
    в обработчике текста мы отреагируем и выдадим задачу.
    """
    # Если пользователь не зарегистрирован — просим зарегистрироваться
    if 'name' not in context.user_data or 'surname' not in context.user_data:
        await update.message.reply_text(
            "Сначала надо зарегистрироваться. Используй /register Имя Фамилия."
        )
        return

    # Предложим выбрать сложность
    text = (
        "Выбери уровень сложности (напиши одним словом в сообщении):\n"
        "1) Легко\n"
        "2) Нормально\n"
        "3) Сложно\n"
        "4) Очень Сложно\n"
        "5) Невозможно\n"
        "Пример: 'легко' или 'невозможно'"
    )
    await update.message.reply_text(text)
    # Укажем в контексте, что мы ждём выбора сложности
    context.user_data['awaiting_difficulty'] = True

async def skip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /skip — пропустить текущую задачу и выдать новую той же сложности."""
    current_task = context.user_data.get('current_task')
    current_difficulty = context.user_data.get('current_difficulty')

    if not current_task or not current_difficulty:
        await update.message.reply_text("У тебя нет активной задачи. Сначала напиши /play.")
        return

    # Выбираем новую задачу той же сложности
    task = random.choice(tasks_data[current_difficulty])
    context.user_data['current_task'] = task
    context.user_data['task_start_time'] = datetime.now()

    await update.message.reply_text(
        f"Задача пропущена. Вот новая ({current_difficulty}):\n\n"
        f"{task['question']}\n\n"
        "Напиши свой ответ или воспользуйся подсказкой: /hint."
    )

async def hint_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /hint — показать подсказку к текущей задаче."""
    current_task = context.user_data.get('current_task')
    if not current_task:
        await update.message.reply_text("У тебя нет активной задачи. Сначала напиши /play.")
        return

    hint_text = current_task.get('hint', "Нет подсказки.")
    await update.message.reply_text(f"Подсказка: {hint_text}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /stats — краткая статистика (очки, решено задач, время)."""
    score = context.user_data.get('score', 0)
    tasks_solved = context.user_data.get('tasks_solved', 0)
    time_spent = context.user_data.get('time_spent', 0)

    minutes = time_spent // 60
    seconds = time_spent % 60

    text = (
        f"Твоя статистика:\n"
        f"Очки: {score}\n"
        f"Решено задач: {tasks_solved}\n"
        f"Общее время на решения: {minutes} мин. {seconds} сек.\n"
        "Чтобы увидеть полный профиль, набери /profile."
    )
    await update.message.reply_text(text)

# ======================
# Обработка сообщений (текст)
# ======================

async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработка произвольных сообщений.
    - Если ждём выбор сложности, берём из сообщения название сложности и выдаём задачу.
    - Если есть текущая задача, проверяем ответ.
    """
    user_text = update.message.text.strip().lower()

    # 1) Проверяем, не ждём ли мы выбора сложности
    if context.user_data.get('awaiting_difficulty'):
        if user_text in tasks_data:
            # Сохраняем выбранную сложность
            context.user_data['current_difficulty'] = user_text
            # Снимаем флаг ожидания
            context.user_data['awaiting_difficulty'] = False

            # Выбираем задачу нужного уровня
            task_list = tasks_data[user_text]
            task = random.choice(task_list)

            context.user_data['current_task'] = task
            context.user_data['task_start_time'] = datetime.now()

            await update.message.reply_text(
                f"Отлично! Твой уровень сложности: {user_text}\n"
                f"Вот твоя задача:\n\n{task['question']}\n\n"
                "Напиши ответ или воспользуйся /hint."
            )
        else:
            await update.message.reply_text(
                "Такого уровня нет. Выбери из: Легко, Нормально, Сложно, Очень Нложно, Невозможно"
            )
        return

    # 2) Если у нас есть активная задача, проверяем ответ
    current_task = context.user_data.get('current_task')
    current_difficulty = context.user_data.get('current_difficulty')

    # Если нет задачи — просто игнорируем или пишем что-нибудь
    if not current_task:
        await update.message.reply_text(
            "Тут нет активной задачи. Используй /play, чтобы получить новую."
        )
        return

    correct_answer = current_task['answer'].lower()
    if user_text == correct_answer:
        # Вычисляем, сколько пользователь потратил времени
        start_time = context.user_data.get('task_start_time')
        if start_time:
            delta = datetime.now() - start_time
            # Время в секундах
            time_seconds = delta.total_seconds()
            context.user_data['time_spent'] = context.user_data.get('time_spent', 0) + int(time_seconds)

        # Начисляем очки за задачу
        points_for_difficulty = difficulty_points.get(current_difficulty, 1)
        context.user_data['score'] = context.user_data.get('score', 0) + points_for_difficulty

        # Увеличиваем счётчик решённых задач
        context.user_data['tasks_solved'] = context.user_data.get('tasks_solved', 0) + 1

        # Сбрасываем текущую задачу
        context.user_data['current_task'] = None
        context.user_data['task_start_time'] = None

        # Проверяем, не пора ли повышать уровень (каждые 5 очков — +1 уровень)
        new_score = context.user_data['score']
        current_level = context.user_data['level']
        # Если очки превышают 5 * level, повышаем уровень
        if new_score >= current_level * 5:
            context.user_data['level'] = current_level + 1
            await update.message.reply_text(
                f"Правильно! Ты получил {points_for_difficulty} очк(а/ов) и повысил(а) уровень до {current_level + 1}.\n"
                "Отличная работа!\n"
                "Чтобы взять следующую задачу, введи /play или /skip."
            )
        else:
            await update.message.reply_text(
                f"Правильно! Ты получил {points_for_difficulty} очк(а/ов). "
                f"Теперь у тебя {new_score} очков.\n"
                "Чтобы взять следующую задачу, введи /play или /skip."
            )
    else:
        # Неправильно
        await update.message.reply_text(
            f"Неправильно. Попробуй ещё раз или используй /hint.\n\n"
            f"Текущая задача: {current_task['question']}"
        )






# Создание и настройка базы данных
def create_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Функция для добавления пользователя в базу данных
def add_user(user_id, username, first_name, last_name):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name))
    conn.commit()
    conn.close()
# ======================
# Основная функция
# ======================

def main() -> None:
    # Замените на свой реальный токен
    TOKEN = "7782923361:AAH6nbHN-QsuwUmPwFWExkc6kQquOqFOZTQ"

    application = Application.builder().token(TOKEN).build()

    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("register", register_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("play", play_command))
    application.add_handler(CommandHandler("hint", hint_command))
    application.add_handler(CommandHandler("skip", skip_command))
    application.add_handler(CommandHandler("stats", stats_command))

    # Обработка произвольных текстовых сообщений (ответы на задачи или выбор сложности)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))

    # Запуск бота
    application.run_polling()

if __name__ == "__main__":
    main()
