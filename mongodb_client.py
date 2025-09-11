from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import DuplicateKeyError
import os
from dotenv import load_dotenv
from typing import List, Dict, Optional
from datetime import datetime

load_dotenv()
# mongodb_client.py
from pymongo import MongoClient
from pymongo.server_api import ServerApi
import os
# from dotenv import load_dotenv

# load_dotenv()
mongo_uri = os.getenv("MONGODB_URI")
class MongoDBClient:
    _instance = None  # singleton instance

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)

            cls._instance.mongo_uri = os.getenv("MONGODB_URI")
            cls._instance.db_name = os.getenv("MONGODB_DB_NAME")
            # cls._instance.collection_name = os.getenv("MONGODB_COLLECTION")

            if not cls._instance.mongo_uri:
                raise ValueError("MONGODB_URI not found")

            cls._instance.client = MongoClient(
                cls._instance.mongo_uri,
                server_api=ServerApi('1'),
                tls=True,
                tlsAllowInvalidCertificates=True,
                tlsAllowInvalidHostnames=True,
                retryWrites=True,
                w='majority'
            )
            cls._instance.db = cls._instance.client[cls._instance.db_name]
            # cls._instance.collection = cls._instance.db[cls._instance.collection_name]

            # Test connection
            cls._instance.client.admin.command('ping')
            print("✅ Connected to MongoDB!")
        return cls._instance

    def close_connection(self):
        """Close connection"""
        try:
            self.client.close()
            print("✅ MongoDB connection closed!")
        except Exception as e:
            print(f"❌ Error closing connection: {e}")

    def get_collection(self, collection_name: str):
        """Return a pymongo collection object"""
        return self.db[collection_name]

    def insert_documents(self, collection_name: str, documents: list[dict]):
        """Insert list of documents into a specified collection"""
        if not documents:
            print("⚠️ No documents to insert")
            return
        collection = self.get_collection(collection_name)
        result = collection.insert_many(documents)
        print(f"✅ Inserted {len(result.inserted_ids)} documents into {collection_name}")