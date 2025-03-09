import logging
import requests
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# BOT TOKEN
API_TOKEN = "TOKEN"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

user_cookies = {}

# Deleted Friends Storage
deleted_friends = set()

class UnfriendStates(StatesGroup):
    waiting_for_cookie = State()
    waiting_for_user_id = State()

def get_user_info(cookie):
    url = "https://users.roblox.com/v1/users/authenticated"
    headers = {
        "Content-Type": "application/json",
        "Cookie": f".ROBLOSECURITY={cookie}",
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 401:
        raise Exception("Ошибка: Куки недействительны. Пожалуйста, отправьте актуальные куки. Напишите команду /start")
    else:
        raise Exception(f"Ошибка при получении информации о пользователе: {response.status_code}, {response.text}")

def get_friends(cookie, roblox_user_id):
    url = f"https://friends.roblox.com/v1/users/{roblox_user_id}/friends"
    headers = {
        "Content-Type": "application/json",
        "Cookie": f".ROBLOSECURITY={cookie}",
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()["data"]
    else:
        raise Exception(f"Ошибка при получении списка друзей: {response.status_code}, {response.text}")

def get_avatar_thumbnail(user_id):
    url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=150x150&format=Png&isCircular=false"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if "data" in data and data["data"]:
            return data["data"][0]["imageUrl"]
        else:
            raise Exception("Ошибка: Не удалось получить тамбнейл пользователя.")
    else:
        raise Exception(f"Ошибка при запросе тамбнейла: {response.status_code}, {response.text}")

def unfriend_user(cookie, target_user_id, user_id):
    url = f"https://friends.roblox.com/v1/users/{target_user_id}/unfriend"
    csrf_tokens = {}
    csrf_token = csrf_tokens.get(user_id, "")

    headers = {
        "Content-Type": "application/json",
        "Cookie": f".ROBLOSECURITY={cookie}",
        "X-CSRF-TOKEN": csrf_token,
    }

    response = requests.post(url, headers=headers)
    if response.status_code == 403 and "x-csrf-token" in response.headers:
        csrf_token = response.headers["x-csrf-token"]
        csrf_tokens[user_id] = csrf_token
        headers["X-CSRF-TOKEN"] = csrf_token
        response = requests.post(url, headers=headers)

    if response.status_code == 200:
        return f"Друг с ID {target_user_id} успешно удален."
    elif response.status_code == 400:
        return f"Ошибка: Неверный ID пользователя {target_user_id}."
    elif response.status_code == 403:
        return "Ошибка: Ошибка авторизации. Проверьте куки."
    elif response.status_code == 401:
        return "Ошибка: Куки недействительны. Пожалуйста, отправьте актуальные куки."
    elif response.status_code == 404:
        return f"Ошибка: Пользователь с ID {target_user_id} не найден."
    else:
        return f"Произошла ошибка: {response.status_code}, Ответ: {response.text}"

@dp.message(Command("start"))
async def send_welcome(message: types.Message, state: FSMContext):
    logging.info(f"Пользователь {message.from_user.id} отправил /start.")

    start_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍪 Отправить Cookie", callback_data="send_cookie")]
    ])

    await message.reply(
        "👋 Добро пожаловать в бот управления друзьями Roblox!\n\n"
        "С помощью этого бота вы можете:\n"
        "1️⃣ Удалять друзей.\n"
        "2️⃣ Просматривать список друзей.\n\n"
        "Чтобы начать, нажмите кнопку ниже и отправьте свои куки.",
        reply_markup=start_keyboard
    )
    await state.clear()

@dp.callback_query(lambda c: c.data == "send_cookie")
async def ask_for_cookie(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"Пользователь {callback_query.from_user.id} нажал 'Отправить Cookie'.")

    await callback_query.message.reply(
        "Пожалуйста, отправьте свои куки в формате:\n<code>_|WARNING:-DO-NOT-SHARE-THIS.--Sharing-this-will-allow-someone-to-log-in-as-you-and-to-steal-your-ROBUX-and-items.|</code>",
        parse_mode="HTML"
    )
    await state.set_state(UnfriendStates.waiting_for_cookie)
    await callback_query.answer()

@dp.message(UnfriendStates.waiting_for_cookie)
async def handle_cookies(message: types.Message, state: FSMContext):
    logging.info(f"Получено сообщение: {message.text}")
    cookie = message.text.strip()
    if cookie.startswith(".ROBLOSECURITY="):
        cookie = cookie[len(".ROBLOSECURITY="):]

    user_id = message.from_user.id
    try:
        user_info = get_user_info(cookie)
        user_name = user_info["name"]
        roblox_user_id = user_info["id"]

        user_cookies[user_id] = {"cookie": cookie, "roblox_user_id": roblox_user_id}

        friends_button = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 Друзья", callback_data="show_friends")]
        ])

        avatar_url = get_avatar_thumbnail(roblox_user_id)

        await message.reply_photo(
            photo=avatar_url,
            caption=(
                f"Ваши куки сохранены! Вот информация о вашем аккаунте:\n"
                f"👤 Имя пользователя: {user_name}\n"
                f"🆔 ID: {roblox_user_id}\n\n"
                f"Теперь нажмите 'Друзья', чтобы посмотреть список."
            ),
            reply_markup=friends_button
        )
        await state.set_state(UnfriendStates.waiting_for_user_id)
    except Exception as e:
        logging.error(f"Ошибка обработки куки: {e}")
        await message.reply(f"Произошла ошибка: {str(e)}")

@dp.callback_query(lambda c: c.data == "show_friends")
async def show_friends(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in user_cookies:
        await callback_query.message.reply("Сначала отправьте куки, чтобы получить список друзей.")
        return

    try:
        cookie = user_cookies[user_id]["cookie"]
        roblox_user_id = user_cookies[user_id]["roblox_user_id"]

        friends = get_friends(cookie, roblox_user_id)

        if not friends:
            await callback_query.message.reply("У вас нет друзей.")
            return

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"Удалить {friend['displayName']} (@{friend['name']})",
                callback_data=f"delete_{friend['id']}"
            )] for friend in friends
        ])

        await callback_query.message.reply("👥 Список друзей. Нажмите 'Удалить', чтобы удалить друга:", reply_markup=keyboard)
    except Exception as e:
        logging.error(f"Ошибка при получении списка друзей: {e}")
        await callback_query.message.reply(f"Произошла ошибка: {str(e)}")

@dp.callback_query(lambda c: c.data.startswith("delete_"))
async def delete_friend(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in user_cookies:
        await callback_query.message.reply("Сначала отправьте куки, чтобы удалить друга.")
        return

    try:
        target_user_id = int(callback_query.data.split("_")[1])
        if target_user_id in deleted_friends:
            await callback_query.answer("Этот друг уже был удален.", show_alert=True)
            return

        cookie = user_cookies[user_id]["cookie"]

        url = f"https://users.roblox.com/v1/users/{target_user_id}"
        headers = {
            "Content-Type": "application/json",
            "Cookie": f".ROBLOSECURITY={cookie}",
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            friend_info = response.json()
            friend_name = friend_info["name"]
            friend_display_name = friend_info.get("displayName", friend_name)
            avatar_url = get_avatar_thumbnail(target_user_id)
        else:
            raise Exception("Не удалось получить информацию о друге.")

        result = unfriend_user(cookie, target_user_id, user_id)

        deleted_friends.add(target_user_id)

        await callback_query.answer()
        await callback_query.message.reply_photo(
            photo=avatar_url,
            caption=(
                f"✅ Успешно удалено:\n"
                f"👤 Никнейм: {friend_display_name} (@{friend_name})\n"
                f"🆔 ID: {target_user_id}\n\n"
                f"{result}"
            )
        )
    except Exception as e:
        logging.error(f"Ошибка при удалении друга: {e}")
        await callback_query.message.reply(f"Произошла ошибка: {str(e)}")

async def main():
    logging.info("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())