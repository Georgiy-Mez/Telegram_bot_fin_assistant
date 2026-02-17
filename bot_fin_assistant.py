import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import sqlite3
from datetime import datetime, timedelta
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import datetime as dt

sqlite3.register_adapter(dt.date, lambda d: d.isoformat())
sqlite3.register_adapter(dt.datetime, lambda dt_: dt_.isoformat(" "))
sqlite3.register_converter("DATE", lambda s: dt.date.fromisoformat(s.decode()))
sqlite3.register_converter("TIMESTAMP", lambda s: dt.datetime.fromisoformat(s.decode()))

bot = Bot('TOKEN')
dp = Dispatcher(storage=MemoryStorage())



class AddProfit(StatesGroup):
    waiting_for_amount = State()

class AddExpenditure(StatesGroup):
    waiting_for_amount = State()

class AddStatistics(StatesGroup):
    waiting_for_period = State()

    
class AddSettings(StatesGroup):
    waiting_for_currency = State()


# ========== Вспомогательные функции ==========
def get_main_keyboard():
    """Клавиатура главного меню"""
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [
                types.KeyboardButton(text='➕ Добавить доход'),
                types.KeyboardButton(text='➖ Добавить расход'),
                types.KeyboardButton(text='📊 Статистика'),
                types.KeyboardButton(text='⚙ Настройки')
            ]
        ],
        resize_keyboard=True,
    )


def get_currency_keyboard():
    """Клавиатура выбора валюты"""
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [
                types.KeyboardButton(text='₸ Тенге'),
                types.KeyboardButton(text='₽ Рубль'),
                types.KeyboardButton(text='💲 Доллар'),
                types.KeyboardButton(text='€ Евро')
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_statistics_keyboard():
    """Клавиатура выбора периода статистики"""
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [
                types.KeyboardButton(text='🌞 Сегодня'),
                types.KeyboardButton(text='📅 Неделя'),
                types.KeyboardButton(text='🗓️ Месяц'),
            ],
            [
                types.KeyboardButton(text='📆 Год'),
                types.KeyboardButton(text='⏳ Всё время'),
                types.KeyboardButton(text='⬅ Главное меню')
            ]
        ],
        resize_keyboard=True
    )


currency_map = {
    '₸ Тенге': '₸',
    '₽ Рубль': '₽',
    '💲 Доллар': '$',
    '€ Евро': '€'
}
    
#Обработка команды start
@dp.message(Command('start'))
async def start(message: types.Message, state: FSMContext):
    try:
        conn = sqlite3.connect('finance.db')
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount REAL,
            category TEXT,
            date TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            currency TEXT
        )
        """)

        cur.execute(
            "SELECT currency FROM users WHERE user_id = ?",
            (message.from_user.id,)
        )
        user = cur.fetchone()

        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        await message.answer(f"❌ Ошибка инициализации: {e}")
        return


    if user:
        await message.answer(
            f'Привет, {message.from_user.first_name}\nЯ твой личный финансовый помощник🤖\nЯ помогу тебе удобно фиксировать доходы или расходы💸\nТы можешь просмотреть свою статитстику доходов/расходов за определенный период📊',
            reply_markup=get_main_keyboard()
        )
        return  

    if not user:
        await message.answer(
            f"Привет, {message.from_user.first_name}!\n💱 В какой валюте ты хочешь вести финансы?",
            reply_markup=get_currency_keyboard()
        )
        await state.set_state(AddSettings.waiting_for_currency)


# ========== Обработчик выбора валюты ==========
@dp.message(AddSettings.waiting_for_currency)
async def change_currency(message: types.Message, state: FSMContext):
    if message.text == '⬅ Главное меню':
        await state.clear()
        await message.answer('Вы вернулись в главное меню', reply_markup=get_main_keyboard())
        return
    
    if message.text not in currency_map:
        await message.answer("❌ Выберите валюту кнопкой ниже")
        return

    currency = currency_map[message.text]

    try:
        conn = sqlite3.connect('finance.db')
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO users (user_id, currency) VALUES (?, ?)",
            (message.from_user.id, currency)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        await message.answer(f"❌ Ошибка сохранения: {e}")
        return

    await state.clear()
    await message.answer(f"✅ Валюта сохранена: {currency}", reply_markup=get_main_keyboard())


def get_user_currency(user_id):
    try:
        conn = sqlite3.connect('finance.db')
        cur = conn.cursor()
        cur.execute(
            "SELECT currency FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cur.fetchone()
        conn.close()
        return result[0] if result else '₸'
    except Exception:
        return '₸'


@dp.message(AddProfit.waiting_for_amount)
async def add_profit_amount(message: types.Message, state: FSMContext):
    currency = get_user_currency(message.from_user.id)
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            await message.answer("❌ Сумма должна быть положительной")
            return
    except ValueError:
        await message.answer("❌ Введите число")
        return  
    await message.answer(f"✅ Доход {amount}{currency} добавлен!")
    user_id = message.from_user.id
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # сохраняем в базу данных
    try:
        conn = sqlite3.connect('finance.db')
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO transactions (user_id, type, amount, date) VALUES (?, ?, ?, ?)",
            (user_id, 'income', amount, date)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        await message.answer(f"❌ Ошибка сохранения: {e}")
    
    await state.clear()

@dp.message(AddExpenditure.waiting_for_amount)
async def add_expenditure_amount(message: types.Message, state: FSMContext):
    currency = get_user_currency(message.from_user.id)
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            await message.answer("❌ Сумма должна быть положительной")
            return
    except ValueError:
        await message.answer("❌ Введите число")
        return

    user_id = message.from_user.id
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # сохраняем в базу данных
    try:
        conn = sqlite3.connect('finance.db')
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO transactions (user_id, type, amount, date) VALUES (?, ?, ?, ?)",
            (user_id, 'expense', amount, date)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        await message.answer(f"❌ Ошибка сохранения: {e}")

    await message.answer(f"💸 Расход {amount}{currency} добавлен!")
    await state.clear()

@dp.message(AddStatistics.waiting_for_period)
async def statistics_period(message: types.Message, state: FSMContext):
    currency = get_user_currency(message.from_user.id)
    text = message.text.strip()
    period_text = text
    
    if text == '⬅ Главное меню':
        await state.clear()
        await message.answer('Вы вернулись в главное меню', reply_markup=get_main_keyboard())
        return
    elif text == '🌞 Сегодня':
        start_date = datetime.now().date()
    elif text == '📅 Неделя':
        start_date = datetime.now() - timedelta(days=7)
    elif text == '🗓️ Месяц':
        start_date = datetime.now() - timedelta(days=30)
    elif text == '📆 Год':
        start_date = datetime.now() - timedelta(days=365)
    elif text == '⏳ Всё время':
        start_date = None
    else:
        await message.answer("❌ Выберите период из меню")
        return
    
    try:
        conn = sqlite3.connect('finance.db')
        cur = conn.cursor()

        if start_date is not None:
            cur.execute(
                "SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='income' AND date(date) >= ?",
                (message.from_user.id, start_date)
            )
            income = cur.fetchone()[0] or 0

            cur.execute(
                "SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='expense' AND date(date) >= ?",
                (message.from_user.id, start_date)
            )
            expense = cur.fetchone()[0] or 0
        else:
            # Всё время, без фильтра по дате
            cur.execute(
                "SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='income'",
                (message.from_user.id,)
            )
            income = cur.fetchone()[0] or 0

            cur.execute(
                "SELECT SUM(amount) FROM transactions WHERE user_id=? AND type='expense'",
                (message.from_user.id,)
            )
            expense = cur.fetchone()[0] or 0

        conn.close()
    except Exception as e:
        await message.answer(f"❌ Ошибка чтения данных: {e}")
        return

    balance = income - expense

    await message.answer(
        f"📊 Статистика за {period_text}:\n"
        f"💰 Доход: {income}{currency}\n"
        f"💸 Расход: {expense}{currency}\n"
        f"📈 Баланс: {balance}{currency}"
    )

@dp.message()
async def text_button(message: types.Message, state: FSMContext):
    text = message.text
    current_state = await state.get_state()
    
    if text == '⬅ Главное меню':
        await state.clear()
        await message.answer('Вы вернулись в главное меню', reply_markup=get_main_keyboard())
        return
    
    if current_state is None:
        if text == '➕ Добавить доход':
            await message.answer('💰 Введите сумму дохода:')
            await state.set_state(AddProfit.waiting_for_amount)
        elif text == "➖ Добавить расход":
            await message.answer("💸 Введи сумму расхода:")
            await state.set_state(AddExpenditure.waiting_for_amount)
        elif text == "📊 Статистика":
            await message.answer("📊 Выберите период для статистики:", reply_markup=get_statistics_keyboard())
            await state.set_state(AddStatistics.waiting_for_period)
        elif text == "⚙ Настройки":
            markup = types.ReplyKeyboardMarkup(
                keyboard=[
                [
                    types.KeyboardButton(text='₸ Тенге'),
                    types.KeyboardButton(text='₽ Рубль'),
                    types.KeyboardButton(text='💲 Доллар'),
                    types.KeyboardButton(text='€ Евро')
                ],
                [
                    types.KeyboardButton(text='⬅ Главное меню')
                ]
            ],
            resize_keyboard=True
            )
            await message.answer("⚙ Выберите новую валюту:", reply_markup=markup)
            await state.set_state(AddSettings.waiting_for_currency)
        else:
            await message.answer("Я не понял команду ")




async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
