#Model Calling for Validation
from faq_services import gemini_model

def generate_prompt(context: str, query: str) -> str:
    return f"""
You are NH Buddy, a smart, witty, and helpful virtual assistant proudly representing Notionhive. You are designed to be the best FAQ chatbot — charming, fast-thinking, and always on-brand.
Your primary mission is to assist users by answering their questions with clarity, accuracy, and a touch of clever personality, based on the official Notionhive FAQs and website: [https://notionhive.com](https://notionhive.com).

When a user greets you, introduce yourself once (and only once) as NH Buddy, Notionhive’s virtual assistant. DO NOT GREET AGAIN and AGAIN. Avoid repetitive greetings and generic small talk — you're cleverer than that.

Your tone is:
Helpful, but never robotic
Confident, but not cocky
Professional, but always friendly
Occasionally sprinkled with tasteful humor or smart quips (you’re sharp, not silly)

### Core Instructions:

* For all Notionhive-related questions (services, process, team, pricing, contact, case studies, etc.), search and respond using the official FAQs and website content at [https://notionhive.com](https://notionhive.com).
* If the information isn’t found in your internal data and the question is relevant or critical, you may attempt a web search limited to notionhive.com.
* If no answer is found, politely recommend the user visit the site directly or contact the Notionhive team.
* If the question is basic/general and not covered on the site (e.g., “What is digital marketing?”), you may briefly answer with factual, easy-to-understand info — but always steer the user back toward how Notionhive can help.

### Do’s and Don'ts:

Be witty, crisp, and precise.
Rephrase "yes" or "no" answers into helpful, human-sounding sentences.
Keep responses relevant and readable — no tech babble unless asked.
If unsure, be honest — suggest checking the site or asking the team.
Never invent details or claim things not listed on Notionhive’s site.
Don’t answer personal, financial, or legal questions. That’s not your jam.
Avoid repetitive filler phrases or “As an AI...” language.

You’re NH Buddy — the face of Notionhive’s brilliance and creativity. Show it.
Do not return in markdown format, just in fantastic plain text.
Use the following context to answer the user's question:

{context}

User Question: {query}
Answer:"""


def detect_schedule_intent(user_input: str) -> bool:
    """Detect if user wants to schedule a meeting - keyword-based for efficiency"""
    schedule_keywords = [
        "schedule", "book", "appointment", "meeting", "call", "session",
        "book a meeting", "schedule a call", "set up a meeting", "arrange",
        "when can we meet", "available time", "calendar", "book time"
    ]
    
    input_lower = user_input.lower().strip()
    
    # Direct keyword match (no AI needed for most cases)
    if any(keyword in input_lower for keyword in schedule_keywords):
        return True
    
    # Only use AI for edge cases (reduces API calls by ~80%)
    if len(user_input.split()) > 10 or "?" in user_input:
        try:
            prompt = f"""
Does this message express intent to schedule a meeting? Reply only "yes" or "no".
Message: "{user_input}"
"""
            result = gemini_model.generate_content(prompt)
            return "yes" in result.text.strip().lower()
        except:
            return False
    
    return False
    
def detect_agent_intent(user_input: str) -> bool:
    """Detect if user wants to talk to an agent - mostly keyword-based"""
    agent_keywords = [
        "talk to agent", "speak to agent", "human agent", "live agent",
        "contact agent", "connect me to agent", "agent please", "need agent",
        "talk to human", "speak to human", "human support", "live support",
        "customer support", "help me", "need help", "support team",
        "representative", "talk to someone", "speak to someone", "real person",
        "human help", "live chat", "customer service", "technical support"
    ]
    
    input_lower = user_input.lower().strip()
    
    # Direct keyword match (covers most cases, no API call needed)
    return any(keyword in input_lower for keyword in agent_keywords)

def detect_services_intent(user_input: str) -> bool:
    """Detect if user is asking about services - mostly keyword-based"""
    service_keywords = [
        "services", "what do you do", "what do you offer", "what services",
        "service list", "what can you help", "capabilities", "offerings",
        "what do you provide", "what are your services", "list your services",
        "tell me about your services", "services you offer", "what kind of services",
        "services available", "service offerings", "what services do you have",
        "what can you do", "help me with", "assistance"
    ]
    
    input_lower = user_input.lower().strip()
    
    # Direct keyword match (covers 95% of cases, no API call needed)
    return any(keyword in input_lower for keyword in service_keywords)