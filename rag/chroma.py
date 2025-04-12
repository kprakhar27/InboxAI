import chromadb
from chromadb.config import Settings
import json
from openai import OpenAI

# Initialize ChromaDB client
client = chromadb.HttpClient(host="", port=)

openai = OpenAI(api_key="")  # Replace with your OpenAI API key

# Create or get a collection
collection_name = "test_collection"  # Replace with your collection name
collection = client.get_or_create_collection(name=collection_name)

# Load data from JSON file
json_file_path = "generated_emails.json"  # Replace with your JSON file path
with open(json_file_path, "r") as file:
    data = json.load(file)

# Ensure the JSON data is in the correct format
# Example format: [{"id": "1", "text": "sample text", "metadata": {"key": "value"}}, ...]
for item in data:
    collection.add(
        ids=[item["metadata"]["message_id"]],
        documents=[item["content"]["plain_text"]],
        embeddings=[openai.embeddings.create(input=item["content"]["plain_text"], model="text-embedding-3-small").data[0].embedding],  # Optional: Add embeddings if available
        metadatas=[item.get("analytics", {})]
    )

print(f"Data successfully pushed to collection '{collection_name}' in ChromaDB.")