import logging
import re
import time
import asyncio
import requests
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from config import API_ID, API_HASH, BOT_TOKEN, IMAGE_URL, PAGE_SIZE, ADMIN_USER_ID, CHANNEL_USERNAME
from handlers import register_handlers
from api import get_user_api_key
from Force_sub import not_subscribed, forces_sub

# Initialize the set to track unique user IDs
user_ids = set()
logging.basicConfig(level=logging.INFO)

app = Client("filemoon_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

register_handlers(app, ADMIN_USER_ID)

# Function to fetch the API key dynamically for each user
async def fetch_user_api_key(user_id):
    api_key = get_user_api_key(user_id)
    if api_key:
        return api_key
    return None
    
# Pagination variables
current_rename_folder_id = None
current_delete_folder_id = None
current_upload_folder_id = None
active_upload_handlers = {}

def get_account_info(api_key):
    account_url = f"https://filemoonapi.com/api/account/info?key={api_key}"
    try:
        response = requests.get(account_url)
        response.raise_for_status()
        data = response.json()
        if data["status"] == 200:
            return True, data
        else:
            return False, data.get("msg", "Error fetching account info.")
    except requests.RequestException as e:
        logging.error(f"Request error: {e}")
        return False, str(e)
    except ValueError as e:
        logging.error(f"JSON decoding error: {e}")
        return False, "Error decoding JSON response."

def bytes_to_gb(bytes_size):
    return round(bytes_size / (1024 * 1024), 2)

def get_encoding_list(api_key):
    encoding_url = f"https://filemoonapi.com/api/encoding/list?key={api_key}"
    try:
        response = requests.get(encoding_url)
        response.raise_for_status()
        data = response.json()
        if data["status"] == 200:
            return True, data
        else:
            return False, data.get("msg", "Error fetching encoding list.")
    except requests.RequestException as e:
        logging.error(f"Request error: {e}")
        return False, str(e)
    except ValueError as e:
        logging.error(f"JSON decoding error: {e}")
        return False, "Error decoding JSON response."

def fetch_all_folders(api_key):
    url = f"https://filemoonapi.com/api/folder/list?key={api_key}&fld_id=0"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data["status"] == 200:
            return sorted(data["result"].get("folders", []), key=lambda x: x.get('creation_date', ''), reverse=True)
        else:
            logging.error(f"Error fetching folders: {data.get('msg', 'Unknown error')}")
            return []
    except requests.RequestException as e:
        logging.error(f"Request error: {e}")
        return []

def fetch_folders(page=1, api_key=None):
    folders = fetch_all_folders(api_key)
    start_index = (page - 1) * PAGE_SIZE
    end_index = start_index + PAGE_SIZE
    return folders[start_index:end_index], len(folders)

def fetch_files(folder_id, api_key):
    url = f"https://filemoonapi.com/api/file/list?key={api_key}&fld_id={folder_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data["status"] == 200:
            return data["result"].get("files", [])
        else:
            logging.error(f"Error fetching files: {data['msg']}")
            return []
    except requests.RequestException as e:
        logging.error(f"Request error: {e}")
        return []

def build_folder_buttons(folders, page, total_folders):
    buttons = [
        [InlineKeyboardButton(f"{folder['name']} (ID: {folder['fld_id']})", callback_data=f"folder_{folder['fld_id']}")]
        for folder in folders
    ]
    pagination_buttons = []
    total_pages = (total_folders + PAGE_SIZE - 1) // PAGE_SIZE
    if page > 1:
        pagination_buttons.append(InlineKeyboardButton("< Prev", callback_data=f"page_{page-1}"))
    pagination_buttons.append(InlineKeyboardButton(f"{page} | {total_pages}", callback_data="page_no"))
    if total_folders > page * PAGE_SIZE:
        pagination_buttons.append(InlineKeyboardButton("Next >", callback_data=f"page_{page+1}"))

    buttons.append(pagination_buttons)
    buttons.append([InlineKeyboardButton(f"Total Folders: {total_folders}", callback_data="total_folders")])
    return InlineKeyboardMarkup(buttons)

def create_folder(name, api_key):
    url = f"https://filemoonapi.com/api/folder/create?key={api_key}&parent_id=0&name={name}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data["status"] == 200, data.get("msg", "Error creating folder.")
    except requests.RequestException as e:
        logging.error(f"Request error: {e}")
        return False, str(e)

def rename_folder(folder_id, new_name, api_key):
    url = f"https://filemoonapi.com/api/folder/rename?key={api_key}&fld_id={folder_id}&name={new_name}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data["status"] == 200:
            return True, "Folder renamed successfully."
        else:
            return False, f"Failed to rename folder. {data.get('msg', 'Invalid operation')}"
    except requests.RequestException as e:
        logging.error(f"Request error: {e}")
        return False, str(e)

def delete_folder(folder_id, api_key):
    url = f"https://filemoonapi.com/api/folder/delete?key={api_key}&fld_id={folder_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data["status"] == 200:
            return True, "Folder deleted successfully."
        else:
            return False, f"Failed to delete folder. {data.get('msg', 'Invalid operation')}"
    except requests.RequestException as e:
        logging.error(f"Request error: {e}")
        return False, str(e)
        
# Function to start remote upload
def remote_upload(url, folder_id, api_key):
    upload_url = f"https://filemoonapi.com/api/remote/add?key={api_key}&url={url}&fld_id={folder_id}"
    try:
        response = requests.get(upload_url)
        response.raise_for_status()
        data = response.json()
        if data["status"] == 200:
            return True, data["result"]["filecode"]
        else:
            return False, data.get("msg", "Error initiating remote upload.")
    except requests.RequestException as e:
        logging.error(f"Request error: {e}")
        return False, str(e)

# Function to check the upload status
def check_upload_status(filecode, api_key):
    status_url = f"https://filemoonapi.com/api/remote/status?key={api_key}&file_code={filecode}"
    try:
        response = requests.get(status_url)
        response.raise_for_status()
        data = response.json()
        logging.debug(f"API Response: {data}")  # Log full response for debugging
        return True, data
    except requests.RequestException as e:
        logging.error(f"Request error: {e}")
        return False, str(e)
    except ValueError as e:
        logging.error(f"JSON decoding error: {e}")
        return False, "Error decoding JSON response."

# Function to build progress bar
def build_progress_bar(percent, is_completed=False):
    bar_length = 10
    filled_length = int(round(bar_length * percent / 100))
    bar = '█' * filled_length + '▒' * (bar_length - filled_length)
    if is_completed:
        return f"{bar} {int(percent)}% (Completed)"
    return f"{bar} {int(percent)}%"    

# Health check endpoint
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'OK')

# Function to run the health check server
def run_health_check_server():
    server_address = ('', 8000)
    httpd = HTTPServer(server_address, HealthCheckHandler)
    httpd.serve_forever()

@app.on_callback_query(filters.regex(r"remote_upload_(\d+)"))
async def remote_upload_callback(client, callback_query):
    global current_upload_folder_id
    folder_id = int(callback_query.data.split("_")[2])
    current_upload_folder_id = folder_id
    await callback_query.message.reply("Send the URLs for remote upload:")

    # Remove any existing handlers for the same user
    if callback_query.from_user.id in active_upload_handlers:
        app.remove_handler(*active_upload_handlers.pop(callback_query.from_user.id))

    # Define the new handler for the user
    @app.on_message(filters.text & filters.user(callback_query.from_user.id))
    async def handle_upload_url(client, message):
        nonlocal folder_id
        user_id = message.from_user.id  # Get user ID to fetch their API key
        api_key = get_user_api_key(user_id)  # Function to fetch API key for the user

        # Validate the URLs and extract them
        url_pattern = re.compile(r'http[s]?://[^\s]+')
        urls = url_pattern.findall(message.text)
        
        if urls and api_key:
            for url in urls:
                success, filecode = remote_upload(url.strip(), folder_id, api_key)
                if success:
                    upload_message = await message.reply(f"File added to remote upload queue with code: {filecode}")

                    last_content = None  # Variable to store the last content of the message
                    upload_completed = False  # Flag to indicate if the upload is completed or failed

                    # Polling the upload status
                    while not upload_completed:
                        await asyncio.sleep(3)  # Wait for 3 seconds before checking again
                        upload_success, status = check_upload_status(filecode, api_key)  # Include api_key here
                        if upload_success:
                            result = status.get('result', [])
                            if result:
                                result = result[0]  # Get the first item in the result list
                                progress = int(result.get('progress', '0'))
                                status_text = result.get('status', '').upper()  # Status should be in capital letters

                                if status_text == "WORKING":
                                    progress_bar = build_progress_bar(progress)
                                    new_content = f"⏳ Upload in progress... FileId: {filecode}\n{progress_bar}"
                                elif status_text == "COMPLETED":
                                    if status.get("msg") == "OK":
                                        new_content = f"✅ Upload completed successfully for file: {filecode}\n{build_progress_bar(progress, is_completed=True)}"
                                    else:
                                        new_content = f"❌ Upload failed for file: {filecode}\n{build_progress_bar(progress)}"
                                    upload_completed = True  # Stop polling
                                elif status_text == "ERROR":
                                    new_content = f"❌ Upload failed for file: {filecode}\n{build_progress_bar(progress)}"
                                    upload_completed = True  # Stop polling
                                else:
                                    continue  # Continue polling if the status is neither WORKING, COMPLETED, nor ERROR

                                # Only update message if content has changed
                                if new_content != last_content:
                                    await upload_message.edit(new_content)
                                    last_content = new_content
                            else:
                                # Result list is empty, consider it a success
                                progress = 100
                                progress_bar = build_progress_bar(progress, is_completed=True)
                                new_content = f"✅ Upload completed successfully for file: {filecode}\n{progress_bar}"
                                await upload_message.edit(new_content)
                                upload_completed = True  # Stop polling
                        else:
                            await upload_message.edit(f"❌ Failed to check upload status: {status}")
                            break
                else:
                    await message.reply(f"Failed to start remote upload. {filecode}")
        else:
            await message.reply("Invalid URLs or no API key found.")

    # Add the new handler to the active handlers list
    handler_info = app.add_handler(handle_upload_url)
    active_upload_handlers[callback_query.from_user.id] = handler_info


@app.on_message(filters.command("start"))
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
@app.on_message(filters.command("account_info"))
async def handle_account_info(client, message):
    # Fetch the API key for the user (you need to implement this)
    user_id = message.from_user.id
    api_key = get_user_api_key(user_id)  # Implement get_user_api_key function to fetch the API key
    
    if not api_key:
        await message.reply("❌ API key not set. Please set your API key using /set_key command.")
        return

    # Pass the API key to the get_account_info function
    success, data = get_account_info(api_key)
    if success:
        result = data["result"]
        storage_used_gb = bytes_to_gb(int(result['storage_used']))  # Convert bytes to GB
        
        account_info = (
            "📋 ＡＣＣＯＵＮＴ ＩＮＦＯ\n\n"
            "───────────────────────────\n"
            f"👤 Usᴇʀɴᴀᴍᴇ: \n• {result['login']}\n"
            "───────────────────────────\n"
            f"📧 Eᴍᴀɪʟ: \n• {result['email']}\n"
            "───────────────────────────\n"
            f"💰 Bᴀʟᴀɴᴄᴇ: \n• {result['balance']} $\n"
            "───────────────────────────\n"
            f"📁 Tᴏᴛᴀʟ Fɪʟᴇs:\n• {result['files_total']}\n"
            "───────────────────────────\n"
            f"💾 Sᴛᴏʀᴀɢᴇ Usᴇᴅ: \n• {storage_used_gb:.2f} GB\n"
            "───────────────────────────\n"
            f"🗄️ Sᴛᴏʀᴀɢᴇ Lᴇғᴛ: \n• {result['storage_left']}\n"
            "───────────────────────────\n"
            f"⭐ Pʀᴇᴍɪᴜᴍ: \n• {'Yes' if result['premium'] else 'No'}\n"
            "───────────────────────────\n"
            f"📅 Pʀᴇᴍɪᴜᴍ Exᴘɪʀʏ: \n• {result['premium_expire']}\n"
            "───────────────────────────"
        )
        
        await message.reply(account_info)
    else:
        await message.reply(f"❌ Failed to fetch account info: {data}")

@app.on_callback_query(filters.regex(r"show_tutorial"))
async def show_tutorial(client, callback_query):
    tutorial_text = (
        "📚 *Tutorial:*\n\n"
        "1. Use the `/start` command to view the main menu.\n"
        "2. Use the '📖 Tutorial' button to read this tutorial again.\n"
        "3. Use the 'ℹ️ Account Info' button or /account_info command to view your account information.\n"
        "4. Use the '📁 All Folders' button to view and manage your folders.\n"
        "5. To create a new folder, use the command `/create <folder_name>`.\n"
        "6. To upload files remotely, select a folder and use the 'Remote Upload' option.\n"
        "7. To view files in a folder, select a folder and use the 'View Files' option.\n"
        "8. To delete or rename folders, use the respective options in the folder actions menu."
    )
    await callback_query.message.edit(tutorial_text)

@app.on_callback_query(filters.regex(r"account_info"))
async def account_info_callback(client, callback_query):
    await handle_account_info(client, callback_query.message)

@app.on_callback_query(filters.regex(r"all_folders"))
async def all_folders_callback(client, callback_query):
    user_id = callback_query.from_user.id
    api_key = get_user_api_key(user_id)  # Implement get_user_api_key function to fetch the API key
    
    if not api_key:
        await callback_query.message.edit("❌ API key not set. Please set your API key using /set_key command.")
        return

    page = 1
    folders, total_folders = fetch_folders(page, api_key)  # Pass api_key to fetch_folders
    if not folders:
        await callback_query.message.edit("No folders found or error fetching folders.")
        return
    
    reply_markup = build_folder_buttons(folders, page, total_folders)
    await callback_query.message.edit("Select a folder to manage:", reply_markup=reply_markup)

@app.on_message(filters.command("allfld"))
async def all_folders(client, message):
    user_id = message.from_user.id
    api_key = get_user_api_key(user_id)  # Implement get_user_api_key function to fetch the API key
    
    if not api_key:
        await message.reply("❌ API key not set. Please set your API key using /set_key command.")
        return

    page = 1
    folders, total_folders = fetch_folders(page, api_key)  # Pass api_key to fetch_folders
    
    if not folders:
        await message.reply("No folders found or error fetching folders.")
        return
    
    reply_markup = build_folder_buttons(folders, page, total_folders)
    await message.reply("Select a folder to manage:", reply_markup=reply_markup)

@app.on_callback_query(filters.regex(r"page_(\d+)"))
async def pagination_callback(client, callback_query):
    user_id = callback_query.from_user.id
    api_key = get_user_api_key(user_id)  # Implement get_user_api_key function to fetch the API key
    
    if not api_key:
        await callback_query.message.edit("❌ API key not set. Please set your API key using /set_key command.")
        return

    page = int(callback_query.data.split("_")[1])
    folders, total_folders = fetch_folders(page, api_key)  # Pass api_key to fetch_folders
    
    if not folders:
        await callback_query.message.edit("No folders found or error fetching folders.")
        return
    
    reply_markup = build_folder_buttons(folders, page, total_folders)
    await callback_query.message.edit("Sᴇʟᴇᴄᴛ ᴀ ғᴏʟᴅᴇʀ ᴛᴏ ᴍᴀɴᴀɢᴇ:", reply_markup=reply_markup)

@app.on_callback_query(filters.regex(r"folder_(\d+)"))
async def folder_callback(client, callback_query):
    user_id = callback_query.from_user.id
    api_key = get_user_api_key(user_id)  # Implement get_user_api_key function to fetch the API key
    
    if not api_key:
        await callback_query.message.edit("❌ API key not set. Please set your API key using /set_key command.")
        return

    global current_rename_folder_id
    global current_delete_folder_id
    global current_upload_folder_id
    folder_id = int(callback_query.data.split("_")[1])
    all_folders = fetch_all_folders(api_key)  # Pass api_key to fetch_all_folders
    folder = next((folder for folder in all_folders if folder['fld_id'] == folder_id), None)
    
    if folder is None:
        await callback_query.message.edit("Folder not found.")
        return
    
    folder_name = folder['name']
    current_rename_folder_id = folder_id
    current_delete_folder_id = folder_id
    current_upload_folder_id = folder_id
    buttons = [
        [InlineKeyboardButton("View Files", callback_data=f"view_files_{folder_id}")],
        [InlineKeyboardButton("Edit Folder Name", callback_data=f"edit_name_{folder_id}")],
        [InlineKeyboardButton("Delete Folder", callback_data=f"delete_{folder_id}")],
        [InlineKeyboardButton("Remote Upload", callback_data=f"remote_upload_{folder_id}")],
        [InlineKeyboardButton("Back to Folders", callback_data="back_to_folders")]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await callback_query.message.edit(f"Actions for folder '{folder_name}' (ID: {folder_id}):", reply_markup=reply_markup)

@app.on_callback_query(filters.regex(r"view_files_(\d+)"))
async def view_files_callback(client, callback_query):
    user_id = callback_query.from_user.id
    api_key = get_user_api_key(user_id)  # Implement get_user_api_key function to fetch the API key
    
    if not api_key:
        await callback_query.message.edit("❌ API key not set. Please set your API key using /set_key command.")
        return

    folder_id = int(callback_query.data.split("_")[2])
    files = fetch_files(folder_id, api_key)  # Pass api_key to fetch_files
    
    if not files:
        await callback_query.message.edit("No files found or error fetching files.")
        return
    
    # Sort files by title in ascending order
    files = sorted(files, key=lambda x: x['title'])
    
    # Update the domain in the file links
    for file in files:
        file['link'] = file['link'].replace("filemoon.sx", "filemoon.in")
    
    file_buttons = [
        [InlineKeyboardButton(file['title'], url=file['link'])]
        for file in files
    ]
    file_buttons.append([InlineKeyboardButton("Send All Links", callback_data=f"send_links_{folder_id}")])
    file_buttons.append([InlineKeyboardButton("Back to Folder Actions", callback_data=f"folder_{folder_id}")])
    reply_markup = InlineKeyboardMarkup(file_buttons)
    await callback_query.message.edit(f"Files in folder ID {folder_id}:", reply_markup=reply_markup)

@app.on_callback_query(filters.regex(r"send_links_(\d+)"))
async def send_all_links_callback(client, callback_query):
    user_id = callback_query.from_user.id
    api_key = get_user_api_key(user_id)  # Implement get_user_api_key function to fetch the API key
    
    if not api_key:
        await callback_query.message.edit("❌ API key not set. Please set your API key using /set_key command.")
        return

    folder_id = int(callback_query.data.split("_")[2])
    files = fetch_files(folder_id, api_key)  # Pass api_key to fetch_files
    
    if not files:
        await callback_query.message.edit("No files found or error fetching files.")
        return
    
    # Sort files by title in ascending order
    files = sorted(files, key=lambda x: x['title'])
    
    # Update the domain in the file links
    for file in files:
        file['link'] = file['link'].replace("filemoon.sx", "filemoon.in")
    
    links_message = f"Here are all the file links in folder ID {folder_id}:\n\n"
    links_message += "\n".join([f"{file['title']}: {file['link']}" for file in files])
    
    await callback_query.message.reply(links_message)
    await callback_query.message.edit("Links sent.")

@app.on_callback_query(filters.regex(r"edit_name_(\d+)"))
async def edit_name_callback(client, callback_query):
    user_id = callback_query.from_user.id
    api_key = get_user_api_key(user_id)  # Implement get_user_api_key function to fetch the API key
    
    if not api_key:
        await callback_query.message.edit("❌ API key not set. Please set your API key using /set_key command.")
        return

    folder_id = int(callback_query.data.split("_")[2])
    await callback_query.message.reply("Send the new name for the folder:")

    @app.on_message(filters.text)
    async def rename_folder_message(client, message):
        nonlocal folder_id
        if message.text:
            success, msg = rename_folder(folder_id, message.text, api_key)  # Pass api_key to rename_folder
            if success:
                await message.reply(f"Folder renamed to '{message.text}' successfully!")
            else:
                await message.reply(f"Failed to rename folder. {msg}")

@app.on_callback_query(filters.regex(r"delete_(\d+)"))
async def delete_folder_callback(client, callback_query):
    user_id = callback_query.from_user.id
    api_key = get_user_api_key(user_id)  # Implement get_user_api_key function to fetch the API key
    
    if not api_key:
        await callback_query.message.edit("❌ API key not set. Please set your API key using /set_key command.")
        return

    folder_id = int(callback_query.data.split("_")[1])
    success, msg = delete_folder(folder_id, api_key)  # Pass api_key to delete_folder
    if success:
        await callback_query.message.edit(f"Folder (ID: {folder_id}) deleted successfully.")
    else:
        await callback_query.message.edit(f"Failed to delete folder. {msg}")

@app.on_callback_query(filters.regex(r"back_to_folders"))
async def back_to_folders_callback(client, callback_query):
    user_id = callback_query.from_user.id
    api_key = get_user_api_key(user_id)  # Implement get_user_api_key function to fetch the API key
    
    if not api_key:
        await callback_query.message.edit("❌ API key not set. Please set your API key using /set_key command.")
        return

    page = 1
    folders, total_folders = fetch_folders(page, api_key)  # Pass api_key to fetch_folders
    if not folders:
        await callback_query.message.edit("No folders found or error fetching folders.")
        return
    
    reply_markup = build_folder_buttons(folders, page, total_folders)
    await callback_query.message.edit("Select a folder to manage:", reply_markup=reply_markup)

@app.on_message(filters.command("create"))
async def create_folder_command(client, message: Message):
    user_id = message.from_user.id
    api_key = get_user_api_key(user_id)  # Implement get_user_api_key function to fetch the API key
    
    if not api_key:
        await message.reply("❌ API key not set. Please set your API key using /set_key command.")
        return

    # Extract folder name from the command message
    folder_name = message.text.split(" ", 1)[1] if len(message.text.split()) > 1 else None
    
    # Validate folder name
    if not folder_name:
        await message.reply("Please provide a folder name. Usage: /create <folder_name>")
        return

    # Call the create_folder function
    success, msg = create_folder(folder_name, api_key)  # Pass api_key to create_folder
    if success:
        await message.reply(f"Folder '{folder_name}' created successfully!")
    else:
        await message.reply(f"Failed to create folder. {msg}")

@app.on_message(filters.command("status"))
async def status_command(client, message: Message):
    start_time = time.time()
    test_message = await message.reply("Pinging...")
    latency = (time.time() - start_time) * 1000
    await test_message.edit(f"📡 Ping: {latency:.2f} ms\nBot is online and operational.")

@app.on_message(filters.command("start"))
async def start_command(client, message):
    await message.reply("Bot is running!")

if __name__ == "__main__":
    # Start the health check server in a separate thread
    threading.Thread(target=run_health_check_server, daemon=True).start()
    app.run()
