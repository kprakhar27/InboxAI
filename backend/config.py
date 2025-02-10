import os

# create basick congiguration of backend app
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', '046d9210-d695-43a9-ad1e-3bd813ae4e5e')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'ae7f52c0-3a2d-4961-9725-d9b34b5c9e72')
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:inboxai-project@144.24.127.222:5432/inboxai_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False