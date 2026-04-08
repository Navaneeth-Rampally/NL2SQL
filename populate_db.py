import sqlite3
import os
from faker import Faker
from dotenv import load_dotenv

# Load your .env file to get the database path
load_dotenv()

# Initialize Faker
fake = Faker()

def populate_database():
    db_path = os.getenv("DATABASE_PATH")
    if not db_path:
        print("❌ Error: DATABASE_PATH not found in .env file.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print(f"🚀 Connecting to {db_path}...")

    try:
        # 1. Add some Doctors
        specialties = ['Cardiology', 'Neurology', 'Pediatrics', 'General Medicine', 'Orthopedics']
        for specialty in specialties:
            cursor.execute(
                "INSERT INTO doctors (name, specialization) VALUES (?, ?)",
                (f"Dr. {fake.last_name()}", specialty)
            )
        print("✅ Doctors added.")

        # 2. Add 50 Patients
        for _ in range(50):
            cursor.execute(
                "INSERT INTO patients (first_name, last_name, email) VALUES (?, ?, ?)",
                (fake.first_name(), fake.last_name(), fake.email())
            )
        print("✅ 50 Patients added.")

        # 3. Add some dummy Appointments (Linking them)
        # We'll fetch the IDs we just created
        cursor.execute("SELECT id FROM patients")
        patient_ids = [row[0] for row in cursor.fetchall()]
        
        cursor.execute("SELECT id FROM doctors")
        doctor_ids = [row[0] for row in cursor.fetchall()]

        for _ in range(20):
            import random
            cursor.execute(
                "INSERT INTO appointments (patient_id, doctor_id, appointment_date, status) VALUES (?, ?, ?, ?)",
                (random.choice(patient_ids), random.choice(doctor_ids), fake.date_this_year().isoformat(), 'Scheduled')
            )
        print("✅ 20 Appointments added.")

        conn.commit()
        print("\n🎉 Database population complete! Your clinic is now full of patients.")

    except Exception as e:
        print(f"❌ An error occurred: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    populate_database()