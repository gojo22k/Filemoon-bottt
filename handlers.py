from pyrogram import Client, filters
from api import set_api_key, view_api_key, list_users, get_user_api_key, add_user
from functools import wraps
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import logging
from config import IMAGE_URL

def require_api_key(func):
    @wraps(func)
    async def wrapper(client, message):
        user_id = message.from_user.id
        api_key = get_user_api_key(user_id)
        if api_key:
            return await func(client, message, api_key)
        else:
            await message.reply("You must set your API key first using /set_key <API_KEY>.")
    return wrapper

def register_handlers(app: Client, admin_user_id: int):
    @app.on_message(filters.command("start"))
    async def start_handler(client, message):
        user_id = message.from_user.id
        add_user(user_id)
        api_key = get_user_api_key(user_id)
        if not api_key:
            await message.reply("Welcome! Please set your API key using /set_key <API_KEY> to get started.")
        else:
            await start_command(client, message)

    @app.on_message(filters.command("set_key"))
    async def set_api_key_handler(client, message):
        user_id = message.from_user.id
        args = message.text.split()
        if len(args) > 1:
            api_key = args[1]
            set_api_key(user_id, api_key)
            await message.reply("API key set successfully. You can now use the bot commands.")
            await start_command(client, message)  # Call the main start command once the API key is set
        else:
            await message.reply("Usage: /set_key <API_KEY>")

    @app.on_message(filters.command("view_key"))
    @require_api_key
    async def view_key_handler(client, message, api_key):
        await message.reply(f"Your API key: {api_key}")

    @app.on_message(filters.command("ankit_users_list"))
    async def ankit_users_list_handler(client, message):
        if message.from_user.id == admin_user_id:
            users = list_users()
            user_list = "\n".join([f"User ID: {user['user_id']}, API Key: {user['api_key']}" for user in users])
            await message.reply(f"User list:\n{user_list}")
        else:
            await message.reply("You are not authorized to use this command.")

async def start_command(client, message):
    buttons = [
        [InlineKeyboardButton("📖 Tutorial", callback_data="show_tutorial")],
        [InlineKeyboardButton("ℹ️ Account Info", callback_data="account_info")],
        [InlineKeyboardButton("📁 All Folders", callback_data="all_folders")],
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    if IMAGE_URL:
        try:
            await message.reply_photo(
                photo=IMAGE_URL,
                caption="Wᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ FɪʟᴇMᴏᴏɴ Bᴏᴛ! Usᴇ ᴛʜᴇ ʙᴜᴛᴛᴏɴs ʙᴇʟᴏᴡ ᴛᴏ ɢᴇᴛ sᴛᴀʀᴛᴇᴅ:",
                reply_markup=reply_markup
            )
        except Exception as e:
            logging.error(f"Error sending photo: {e}")
            await message.reply(
                "Wᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ FɪʟᴇMᴏᴏɴ Bᴏᴛ! Usᴇ ᴛʜᴇ ʙᴜᴛᴛᴏɴs ʙᴇʟᴏᴡ ᴛᴏ ɢᴇᴛ sᴛᴀʀᴛᴇᴅ:",
                reply_markup=reply_markup
            )
    else:
        await message.reply(
            "Wᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ FɪʟᴇMᴏᴏɴ Bᴏᴛ! Usᴇ ᴛʜᴇ ʙᴜᴛᴛᴏɴs ʙᴇʟᴏᴡ ᴛᴏ ɢᴇᴛ sᴛᴀʀᴛᴇᴅ:",
            reply_markup=reply_markup
        )
