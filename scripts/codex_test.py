from openai import OpenAI

client = OpenAI()

response = client.chat.completions.create(
    model="gpt-4.1",
    messages=[
        {"role": "system", "content": "Je bent een Python expert."},
        {"role": "user", "content": "Maak een simpele FastAPI endpoint met JWT bescherming."}
    ]
)

print(response.choices[0].message.content)