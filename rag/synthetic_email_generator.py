import datetime
import json
import os
import random

import torch
import tqdm
from faker import Faker
from openai import OpenAI
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

fake = Faker()

HF_TOKEN = os.getenv("HF_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
HF_MODEL_NAME = "mistralai/Mistral-7B-v0.1"

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

tokenizer = AutoTokenizer.from_pretrained(HF_MODEL_NAME, token=HF_TOKEN)
model = AutoModelForCausalLM.from_pretrained(
    HF_MODEL_NAME, torch_dtype=torch.float16, device_map="auto", token=HF_TOKEN
)
generator = pipeline("text-generation", model=model, tokenizer=tokenizer)

# Define topics
TOPICS = [
    "Meeting Invitations",
    "Project Updates",
    "Financial Reports",
    "Customer Support",
    "Marketing Campaigns",
    "Sales Pitches",
    "Technical Documentation",
    "Event Invitations",
    "Security Alerts",
    "Event and Flight Tickets",
    "Shopping Orders",
]


INDUSTRIES = ["Tech", "Finance", "Healthcare", "Education", "Retail", "Government"]

TOXIC_KEYWORDS = ["scam", "idiot", "fraud", "stupid", "worthless"]


def clean_text(text):
    return text.strip()


# Function to generate email using HF model
def generate_email_hf(topic):
    prompt = f"""
    Generate a professional email about {topic}. The email should have:
    - A subject line starting with 'Subject:'
    - A professional greeting
    - A clear and concise body with 1-2 paragraphs
    - A professional closing with a name

    Output only the email content without explanations.
    """

    try:
        response = generator(prompt, max_length=512, temperature=0)
        return clean_text(response[0]["generated_text"])
    except Exception as e:
        print(f"Error generating email with Hugging Face model: {e}")
        return None


# Initialize the OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


def generate_email_openai(topic, industry):
    prompt = f"""
    Generate a professional email about {topic} relevant to the {industry} industry. The email should be fully detailed, well-structured, and feel authentic, as if it were ready to send. Ensure that all placeholders (e.g., recipient name, date, venue, RSVP deadline, speaker names, company details) are replaced with appropriate, realistic values. The email must include:

    - A subject line starting with 'Subject:' that is relevant, engaging, and informative.
    - A professional greeting that directly addresses a specific recipient (e.g., "Dear John Doe," or "Hello Sarah,").
    - A fully detailed email body with 2-3 well-structured paragraphs that clearly convey the purpose, key details, and any necessary actions. Avoid vague placeholders—use realistic event details, names, and deadlines.
    - A professional closing with an appropriate sign-off (e.g., "Best regards," "Sincerely," etc.), followed by a realistic sender name, title, and organization.

    Ensure the email is polished, professional, and free from placeholders or incomplete details. Output only the fully written email without explanations.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4",  # Use "gpt-4" or "gpt-4-turbo" depending on your access
            messages=[
                {"role": "system", "content": "You are an email writing assistant."},
                {"role": "user", "content": prompt},
            ],
        )
        return clean_text(response.choices[0].message.content)
    except Exception as e:
        print(f"Error generating email with OpenAI GPT-4: {e}")
        return None


emails = []

num_emails = 19
generated_emails = 0
j = 13

for topic in TOPICS:
    for i in tqdm.tqdm(range(num_emails)):
        j += 1
        industry = random.choice(INDUSTRIES)

        # Generate email content
        email_content = generate_email_openai(topic, industry)

        # Extract subject line
        subject = f"Important: {topic}"
        if "Subject:" in email_content:
            subject_line = email_content.split("Subject:")[1].split("\n")[0].strip()
            subject = subject_line if subject_line else subject

        # Introduce toxicity in 5% of emails
        is_toxic = random.random() < 0.05
        if is_toxic:
            toxic_word = random.choice(TOXIC_KEYWORDS)
            toxic_phrases = [
                f"This whole situation is {toxic_word}.",
                f"I think your approach is {toxic_word}.",
                f"The way this was handled is completely {toxic_word}.",
            ]
            email_content = email_content.replace(
                "Regards,", f"{random.choice(toxic_phrases)}\n\nRegards,"
            )

        # Generate fake metadata
        sender_name = fake.name()
        sender_email = fake.email()
        recipient_name = fake.name()
        recipient_email = fake.email()
        manager_email = fake.email() if random.random() < 0.5 else None
        bcc_email = fake.email() if random.random() < 0.2 else None
        company_name = fake.company()

        # Generate random email timestamp
        email_date = (
            datetime.datetime.utcnow()
            - datetime.timedelta(
                days=random.randint(0, 365),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )
        ).isoformat() + "Z"

        # Format email content
        email_content = email_content.replace("\n", "<br>")

        # Create email JSON
        email_json = {
            "metadata": {
                "message_id": f"email_{j+1:03d}",
                "from_email": sender_email,
                "to": [recipient_email],
                "cc": [manager_email] if manager_email else [],
                "bcc": [bcc_email] if bcc_email else [],
                "subject": subject,
                "date": email_date,
            },
            "content": {"plain_text": email_content},
            "analytics": {
                "topic": topic,
                "industry": industry,
                "is_toxic": is_toxic,
                "length": len(email_content),
            },
        }

        emails.append(email_json)

        print(f"Generated email {generated_emails + 1}/{len(TOPICS) * num_emails}")
        generated_emails += 1

email2 = emails.copy()

len(email2)

import json

output_path = "generated_emails.json"
with open(output_path, "w") as f:
    json.dump(emails, f, indent=4)

print(f"Emails saved to {output_path}")
