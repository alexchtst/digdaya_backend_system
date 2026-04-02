from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

DB_URI = os.getenv("DB_URI")
DB_NAME = "satria-data-v0"

client = MongoClient(DB_URI)

db = client[DB_NAME]

collection = db["financials"]

def get_all_records() -> list:
    data = list(collection.find({}, {"_id": 0}))
    return data


def get_company_records(code: str) -> list:
    data = list(collection.find(
        {"code": code},
        {"_id": 0}
    ))
    return data