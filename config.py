import os

class Config:
    ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", 1740287480))
    API_ID = os.getenv('API_ID', '25198711')
    API_HASH = os.getenv('API_HASH', '2a99a1375e26295626c04b4606f72752')
    BOT_TOKEN = os.getenv('BOT_TOKEN', '7255118022:AAFehMzJKY0tOanA3ChpEMshrnxn2MPIswE')
    MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb+srv://Aniflix:Lipun123@aniflix.q2wina5.mongodb.net/?retryWrites=true&w=majority&appName=Aniflix')
    IMAGE_URL = 'https://graph.org/file/d994f3bdff19e29e8fdca.jpg'
    PAGE_SIZE = 20
    FORCE_SUB = "AniflixCloud"
