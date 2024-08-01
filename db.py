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

def list_users():
    return list(users_collection.find({}, {"_id": 0, "user_id": 1, "api_key": 1}))
