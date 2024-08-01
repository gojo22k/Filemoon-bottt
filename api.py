from pymongo import MongoClient

# MongoDB configuration
MONGO_URL = "mongodb+srv://Aniflix:Lipun123@aniflix.q2wina5.mongodb.net/?retryWrites=true&w=majority&appName=Aniflix"
client = MongoClient(MONGO_URL)
db = client["Aniflix"]
users_collection = db["myusers"]

def get_user_api_key(user_id):
    user = users_collection.find_one({"user_id": user_id})
    if user:
        return user.get("api_key")
    return None

def set_api_key(user_id, api_key):
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"api_key": api_key}},
        upsert=True
    )

def view_api_key(user_id):
    api_key = get_user_api_key(user_id)
    if api_key:
        return api_key
    return "No API key set."

def list_users():
    return list(users_collection.find({}, {"_id": 0, "user_id": 1, "api_key": 1}))

def add_user(user_id):
    if not users_collection.find_one({"user_id": user_id}):
        users_collection.insert_one({"user_id": user_id})
