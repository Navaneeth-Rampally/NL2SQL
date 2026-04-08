import sqlite3
import os
from faker import Faker
from dotenv import load_dotenv

load_dotenv()
fake = Faker()

def populate_clinic():
    conn = sqlite3.connect(os.getenv("DATABASE_PATH"))
    cursor = conn.cursor()

    # Generate 50 fake patients
    for _ in range(50):
        cursor.execute(
            "INSERT INTO patients (first_name, last_name, email) VALUES (?, ?, ?)",
            (fake.first_name(), fake.last_name(), fake.email())
        )
    
    conn.commit()
    conn.close()
    print(f"✅ 50 fake patients generated in {os.getenv('DATABASE_PATH')}")

populate_clinic()