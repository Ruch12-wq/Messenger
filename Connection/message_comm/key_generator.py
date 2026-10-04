from dotenv import load_dotenv
import os
from pymongo import MongoClient
from pymongo.server_api import ServerApi
import bcrypt

class GenerateKey:
    def __init__(self):
        