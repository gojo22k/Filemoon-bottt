from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import UserNotParticipant
from config import FORCE_SUB

async def not_subscribed(_, client, message):
    # If FORCE_SUB is not defined, skip the subscription check
    if not Config.FORCE_SUB:
        return False
    try:
        user = await client.get_chat_member(Config.FORCE_SUB, message.from_user.id)
        if user.status == enums.ChatMemberStatus.BANNED:
            return True
        else:
            return False
    except UserNotParticipant:
        pass
    return True

@Client.on_message(filters.private & filters.create(not_subscribed))
async def forces_sub(client, message):
    buttons = [[InlineKeyboardButton(text=" 🔥 Uᴘᴅᴀᴛᴇ Cʜᴀɴɴᴇʟ 🔥 ", url=f"https://t.me/{Config.FORCE_SUB}")]]
    text = "**Sᴏʀʀy Dᴜᴅᴇ, Yᴏᴜ Hᴀᴠᴇ Nᴏᴛ Jᴏɪɴᴇᴅ My Uᴩᴅᴀᴛᴇ Cʜᴀɴɴᴇʟ 😐 \n Pʟᴇᴀꜱᴇ Jᴏɪɴ My Uᴩᴅᴀᴛᴇ Cʜᴀɴɴᴇʟ Tᴏ Usᴇ Mᴇ **"
    try:
        user = await client.get_chat_member(Config.FORCE_SUB, message.from_user.id)
        if user.status == enums.ChatMemberStatus.BANNED:
            return await client.send_message(message.from_user.id, text="Sᴏʀʀy Yᴏᴜ'ʀᴇ Bᴀɴɴᴇᴅ Tᴏ Uꜱᴇ Mᴇ")
    except UserNotParticipant:
        return await message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(buttons))
    return await message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(buttons))
