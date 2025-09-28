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
    prompt = f"""
You are an intent detection engine. Your job is to detect whether the user's message is trying to schedule a meeting or not.

Reply only "yes" or "no".

User message: "{user_input}"
Does this message express intent to schedule a meeting?
"""
    try:
        result = gemini_model.generate_content(prompt)
        reply = result.text.strip().lower()
        return "yes" in reply
    except:
        return False
    
def detect_agent_intent(user_input: str) -> bool:
    # Check for explicit agent/human requests first
    explicit_keywords = [
        "agent", "human", "person", "support", "representative", 
        "speak to someone", "talk to someone", "connect me", 
        "escalate", "supervisor", "staff", "employee"
    ]
    
    input_lower = user_input.lower()
    
    # If it contains explicit keywords, it's likely an agent request
    if any(keyword in input_lower for keyword in explicit_keywords):
        return True
    
    # Don't use AI for simple greetings - they're NOT agent requests
    simple_greetings = [
        "hi", "hello", "hey", "good morning", "good afternoon", 
        "good evening", "greetings", "howdy", "what's up"
    ]
    
    # If it's just a simple greeting, don't redirect to agent
    if input_lower.strip() in simple_greetings:
        return False
    
    # For other cases, use AI but with more specific prompt
    prompt = f"""
You are an intent detection engine. Does this message SPECIFICALLY request to speak with a human agent, support person, or representative?

Only return "yes" if the user is EXPLICITLY asking for human help, not just asking general questions or needing assistance.

Simple greetings like "hi", "hello" should be "no".
General questions like "I need help with..." should be "no" unless they specifically mention wanting a human.

Message: "{user_input}"

Answer only "yes" or "no":
"""
    try:
        result = gemini_model.generate_content(prompt)
        return "yes" in result.text.strip().lower()
    except:
        return False

def detect_services_intent(user_input: str) -> bool:
    """Detect if user is asking about services offered by Notionhive"""
    # Check for explicit service-related keywords
    service_keywords = [
        "services", "what do you do", "what do you offer", "what services",
        "service list", "what can you help", "capabilities", "offerings",
        "what do you provide", "what are your services", "list your services",
        "tell me about your services", "services you offer", "what kind of services",
        "services available", "service offerings", "what services do you have"
    ]
    
    input_lower = user_input.lower().strip()
    
    # Direct keyword match
    if any(keyword in input_lower for keyword in service_keywords):
        return True
    
    # Use AI for more complex cases
    prompt = f"""
You are an intent detection engine. Does this message ask about what services, capabilities, or offerings a company provides?

Examples of service inquiries:
- "What services do you offer?"
- "Tell me about your services"
- "What can you help me with?"
- "What do you do?"
- "What are your capabilities?"

Examples of NON-service inquiries:
- "How much does it cost?"
- "Can I schedule a meeting?"
- "Hi"
- "Tell me about your company"

Message: "{user_input}"

Answer only "yes" or "no":
"""
    try:
        result = gemini_model.generate_content(prompt)
        return "yes" in result.text.strip().lower()
    except:
        return False