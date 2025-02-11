import os
from os.path import join, dirname
from dotenv import load_dotenv

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

DB_USER=os.environ.get("DB_USER")
DB_PASWWORD=os.environ.get("DB_PASWWORD")
DB_HOST=os.environ.get("DB_HOST")
DB_PORT=os.environ.get("DB_PORT")
DB_NAME=os.environ.get("DB_NAME")

# create basick congiguration of backend app
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = f'postgresql://{DB_USER}:{DB_PASWWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False