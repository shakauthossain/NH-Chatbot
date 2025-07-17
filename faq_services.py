#Basic Packages
import os
import pandas as pd
from dotenv import load_dotenv
import uuid

#Langchain Packages
from langchain_community.document_loaders import CSVLoader
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings as SentenceTransformerEmbeddings

#Gen AI Packages
import google.generativeai as genai

os.environ["HF_HOME"] = "/tmp/hf_cache" 

# Environment setup
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

gemini_model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    generation_config={"temperature": 0.4}
)
faq_path = "faqs.csv"

# Load FAQ DB
def load_faqs():
    loader = CSVLoader(faq_path, encoding="utf-8")
    docs = loader.load()
    embeddings = SentenceTransformerEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    if not docs:
        return Chroma.from_texts(["empty"], embeddings, collection_name="visaverse_empty_db")
    return Chroma.from_documents(docs, embeddings)

db = load_faqs()

# Add FAQ entry to CSV
def add_faq_to_csv(question: str, answer: str):
    df = pd.read_csv(faq_path, encoding="utf-8")
    if not ((df["prompt"] == question) & (df["response"] == answer)).any():
        new_row = pd.DataFrame([{"id": str(uuid.uuid4()), "prompt": question, "response": answer}])
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_csv(faq_path, index=False, encoding="utf-8")
