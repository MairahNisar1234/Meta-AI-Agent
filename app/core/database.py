from pymongo import MongoClient
import os

client = MongoClient(os.getenv("MONGODB_URI"))

db = client["meta_ai_agent"]

agents_collection = db["agents"]