from openai import OpenAI

client = OpenAI()

with open("app/main.py", "r") as f:
    source = f.read()

prompt = f"""
Analyseer deze FastAPI code.
Controleer:
1. Tenant isolation fouten
2. Directe db.query zonder organization filter
3. Security risico’s
4. Verbeterpunten

Geef een gestructureerd technisch rapport.
Hier is de code:
{source}
"""

response = client.chat.completions.create(
    model="gpt-4.1",
    messages=[
        {"role": "system", "content": "Je bent een senior security code auditor."},
        {"role": "user", "content": prompt}
    ],
    temperature=0
)

print(response.choices[0].message.content)