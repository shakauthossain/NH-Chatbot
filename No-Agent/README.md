# 🧠 Notionhive AI Chatbot

A FastAPI-based intelligent FAQ chatbot powered by Google Gemini and LangChain, designed to answer questions based on Notionhive's official FAQs and website: [notionhive.com](https://notionhive.com).

---

## 🚀 Features

* Semantic search using Sentence Transformers & Chroma DB
* Gemini AI (gemini-2.0-flash) for accurate response generation
* CSV-based FAQ management (upload, add, delete, view)
* RESTful API built with FastAPI
* Prompt structure enforcing Notionhive's tone and boundaries
* CORS enabled for frontend integration

---

## 📁 Project Structure

```
.
├── main.py                  # FastAPI app initialization
├── faq_routes.py           # All chatbot + FAQ management API endpoints
├── faq_services.py         # Vector store logic, Gemini model setup
├── chatbot_prompt.py       # Prompt template for Gemini responses
├── faqs.csv                # Stored FAQs (question/answer pairs)
└── README.md
```

---

## 🍞 Requirements

* Python 3.9+
* Google API Key for Gemini
* `sentence-transformers`
* `langchain`
* `chromadb`
* `fastapi`, `uvicorn`
* `python-dotenv`, `pandas`

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## 🔐 Environment Setup

Create a `.env` file in your root directory with the following:

```env
GOOGLE_API_KEY=your_google_api_key_here
```

---

## 💠 Usage

Run the API server locally:

```bash
uvicorn main:app --reload
```

Access endpoints:

* `POST /ask` — Ask a question
* `POST /add_faq` — Add a new FAQ
* `POST /upload_faqs_csv` — Upload bulk FAQs from CSV
* `DELETE /delete_faq` — Delete FAQ by content
* `DELETE /deleted/{faq_id}` — Delete FAQ by ID
* `DELETE /delete/destroyall` — Delete all FAQs
* `GET /get_faqs` — View all FAQs
* `POST /retrain` — Reload vector DB

---

## 🤖 Chatbot Behavior

* Introduces itself as **Noah**, Notionhive’s AI Assistant.
* Answers based on FAQs and content from [notionhive.com](https://notionhive.com).
* Uses web search *only if* FAQ-based answers aren’t available and question is general or critical.
* Will never generate fabricated or speculative responses.

---

## 📌 Notes

* All FAQs are stored in `faqs.csv`. Updating this file retrains the vector search index.
* Currently single-tenant; for multi-tenant expansion, isolate CSV and vector store per tenant ID.

---

## 👨‍💼 Credits

Developed by the Notionhive AI team.

