import os 
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])
r = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[
        {"role": "system", "content":"You are JARVIS. ANSWWER IN one short sentence"},
        {"role": "user", "content": "Scene: laptop(center), cup(left), What Am i looking at?"},
    ],
)

print(r.choices[0].message.content)