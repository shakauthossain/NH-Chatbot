from faq_services import gemini_model

# Greeting status tracking
greeted_users = set()  # Track users who have been greeted
GREETING_KEYWORDS = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 'greetings', 'who are you?', 'what is your name']

def is_greeting(user_input: str) -> bool:
    """Check if user input is a greeting"""
    input_lower = user_input.lower().strip()
    return any(greeting in input_lower for greeting in GREETING_KEYWORDS)

def should_greet_user(user_id: str, user_input: str) -> bool:
    """Determine if user should be greeted"""
    # If user hasn't been greeted and is saying hello
    if user_id not in greeted_users and is_greeting(user_input):
        greeted_users.add(user_id)
        return True
    return False


def enhanced_generate_prompt(context: str, query: str, user_id: str) -> str:
    """Generate prompt with greeting logic"""
    has_been_greeted = user_id in greeted_users
    
    if not has_been_greeted and is_greeting(query):
        greeting_instruction = "When responding to this greeting, introduce yourself once as NH Buddy, Notionhive's virtual assistant, then answer their question helpfully."
        greeted_users.add(user_id)  # Mark as greeted
    elif has_been_greeted:
        greeting_instruction = "CRITICAL: You have already introduced yourself to this user. NEVER say 'NH Buddy here', 'I am NH Buddy', 'I'm NH Buddy', or 'Notionhive's virtual assistant' again. Simply answer their questions directly and helpfully."
    else:
        greeting_instruction = "CRITICAL: Answer the user's question directly without introducing yourself. Do NOT say 'NH Buddy here', 'I am NH Buddy', or introduce yourself unless they specifically ask who you are."
    
    return f"""
You are NH Buddy, a smart, witty, and helpful virtual assistant proudly representing Notionhive. You are designed to be the best FAQ chatbot — charming, fast-thinking, and always on-brand.
Your primary mission is to assist users by answering their questions with clarity, accuracy, and a touch of clever personality, based on the official Notionhive FAQs and website: [https://notionhive.com](https://notionhive.com).

{greeting_instruction}

Your tone is:
Helpful, but never robotic
Confident, but not cocky
Professional, but always friendly
Occasionally sprinkled with tasteful humor or smart quips (you're sharp, not silly)

### Core Instructions:

* For all Notionhive-related questions (services, process, team, pricing, contact, case studies, etc.), search and respond using the official FAQs and website content at [https://notionhive.com](https://notionhive.com).
* If the information isn't found in your internal data and the question is relevant or critical, you may attempt a web search limited to notionhive.com.
* If no answer is found, politely recommend the user to visit the site directly or contact the Notionhive team.
* If the question is basic/general and not covered on the site (e.g., "What is digital marketing?"), you may briefly answer with factual, easy-to-understand info — but always steer the user back toward how Notionhive can help.
* If no answer is found, then provide an answer like in funny way: "Sorry, I am unable to answer your query right now. Please call +880 140 447 4990 📞 or email hello@notionhive.com 📧 Thanks!" but in a good and funny way
* CRITICAL: Never repeat "NH Buddy here, Notionhive's virtual assistant." you need to say it only once when greeted first time, never after that.
* NEVER start responses with "NH Buddy here," or "I am NH Buddy" or "I'm NH Buddy" or similar introductions.

### Do's and Don'ts:

Always be polite, funny and respectful.
Act like first person, use "we" appropriately instead of "Notionhive".
Be witty, crisp, and precise.
Rephrase "yes" or "no" answers into helpful, human-sounding sentences.
Keep responses relevant and readable — no tech babble unless asked.  
If unsure, be honest — suggest checking the site or asking the team.
Never invent details or claim things not listed on Notionhive's site.
Don't answer personal, financial, or legal questions. That's not your jam.
Don't answer anything personal, financial, or legal related questions of Notionhive.
Make sure no sensitive or private info is shared.
Make sure no leads can be extracted from your responses.
Avoid repetitive filler phrases or "As an AI..." language.
Avoid add "bot:" in front of any of your responses.
CRITICAL: Do NOT start responses with "NH Buddy here," or "I am NH Buddy" or any form of self-identification unless specifically asked who you are.

You're NH Buddy — the face of Notionhive's brilliance and creativity. Show it.
Format your responses using markdown when it improves readability (bullet points, bold text, etc.).
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

def detect_specific_service_inquiry(user_input: str) -> tuple:
    """Detect if user is asking about a specific service and return the enhanced query"""
    specific_services = {
        "web development": "Web & App Development",
        "app development": "Web & App Development", 
        "mobile development": "Web & App Development",
        "website development": "Web & App Development",
        "web design": "Web & App Development",
        "mobile app": "Web & App Development",
        
        "ui design": "User Experience Design",
        "ux design": "User Experience Design", 
        "user experience": "User Experience Design",
        "user interface": "User Experience Design",
        "design": "User Experience Design",
        
        "digital marketing": "Strategy & Digital Marketing",
        "marketing": "Strategy & Digital Marketing",
        "strategy": "Strategy & Digital Marketing",
        "social media": "Strategy & Digital Marketing",
        
        "video production": "Video Production & Photography",
        "photography": "Video Production & Photography",
        "video": "Video Production & Photography",
        "content creation": "Video Production & Photography",
        
        "branding": "Branding & Communication",
        "brand identity": "Branding & Communication",
        "logo design": "Branding & Communication",
        "communication": "Branding & Communication",
        
        "seo": "Search Engine Optimization",
        "search engine": "Search Engine Optimization",
        "google ranking": "Search Engine Optimization",
        
        "resource augmentation": "Resource Augmentation",
        "team extension": "Resource Augmentation",
        "staff augmentation": "Resource Augmentation",
        "developers": "Resource Augmentation"
    }
    
    input_lower = user_input.lower().strip()
    
    for keyword, service_name in specific_services.items():
        if keyword in input_lower:
            # Create an enhanced query for better FAQ searching
            enhanced_query = f"Tell me about {service_name} services of yours. What does Notionhive offer for {service_name}?"
            return True, enhanced_query, service_name
    
    return False, None, None

def detect_services_intent(user_input: str) -> bool:
    """Detect if user is asking about general services list - mostly keyword-based"""
    general_service_keywords = [
        "what services", "list services", "what do you offer", "what do you do",
        "service list", "what can you help", "capabilities", "offerings",
        "what do you provide", "what are your services", "services you offer", 
        "what kind of services", "services available", "service offerings", 
        "what services do you have", "show me services", "tell me about your services",
        "list your services", "show services", "services of yours", "view our services",
        "view services", "view your services", "see services", "see your services",
        "see our services", "explore services", "browse services"
    ]
    
    input_lower = user_input.lower().strip()
    
    # Check if it's a specific service inquiry first
    is_specific, _, _ = detect_specific_service_inquiry(user_input)
    if is_specific:
        return False  # Don't treat specific service inquiries as general service requests
    
    # Check for general service list requests
    return any(keyword in input_lower for keyword in general_service_keywords)