#Basic Packages
import os
import pandas as pd
from dotenv import load_dotenv
import uuid
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

#Gen AI Packages
import google.generativeai as genai

# Environment setup
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

gemini_model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-lite",  # Uses free tier quotas efficiently
    generation_config={"temperature": 0.4}
)
faq_path = "faqs.csv"

class SimpleFAQDB:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
        self.faq_data = None
        self.faq_vectors = None
        self.load_faqs()
    
    def load_faqs(self):
        """Load FAQs from CSV and create TF-IDF vectors"""
        try:
            df = pd.read_csv(faq_path, encoding="utf-8")
            if df.empty:
                print("Warning: FAQ CSV is empty")
                return
                
            self.faq_data = df
            # Combine prompt and response for better semantic search
            combined_text = df['prompt'] + ' ' + df['response']
            self.faq_vectors = self.vectorizer.fit_transform(combined_text)
            print(f"Loaded {len(df)} FAQs into database")
        except Exception as e:
            print(f"Error loading FAQs: {e}")
            self.faq_data = pd.DataFrame(columns=['prompt', 'response', 'id'])
            self.faq_vectors = None
    
    def similarity_search(self, query, k=3):
        """Search for similar FAQs"""
        if self.faq_vectors is None or self.faq_data is None or self.faq_data.empty:
            return []
        
        try:
            query_vector = self.vectorizer.transform([query])
            similarities = cosine_similarity(query_vector, self.faq_vectors).flatten()
            
            # Get top k results
            top_indices = similarities.argsort()[-k:][::-1]
            
            results = []
            for idx in top_indices:
                if similarities[idx] > 0.1:  # Minimum similarity threshold
                    faq_row = self.faq_data.iloc[idx]
                    # Create document-like object
                    doc = type('Document', (), {
                        'page_content': f"Q: {faq_row['prompt']}\nA: {faq_row['response']}",
                        'metadata': {'similarity': similarities[idx]}
                    })()
                    results.append(doc)
            
            return results
        except Exception as e:
            print(f"Error in similarity search: {e}")
            return []

# Create global database instance
db = SimpleFAQDB()

# Load FAQ DB
def load_faqs():
    """Reload FAQs into the database"""
    global db
    db = SimpleFAQDB()
    return db

# Add FAQ entry to CSV
def add_faq_to_csv(question: str, answer: str):
    df = pd.read_csv(faq_path, encoding="utf-8")
    if not ((df["prompt"] == question) & (df["response"] == answer)).any():
        new_row = pd.DataFrame([{"id": str(uuid.uuid4()), "prompt": question, "response": answer}])
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_csv(faq_path, index=False, encoding="utf-8")
