from langchain_groq import ChatGroq

from dotenv import load_dotenv
import os

 
import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not found")




guard_llm = ChatGroq(
    model="llama-3.1-8b-instant",  
    temperature=0,
    api_key=GROQ_API_KEY
)

def llama_guard_check(text: str) -> bool:
    system_prompt = """
You are a strict safety moderation system.

If the user input involves:
- violence
- weapons
- hacking
- illegal activity
- self-harm
- explicit content

Reply with only ONE word:
UNSAFE

Otherwise reply with:
SAFE
"""

    response = guard_llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text}
    ])

    return response.content.strip().upper() == "SAFE"
