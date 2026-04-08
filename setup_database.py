import sqlite3
import random
from faker import Faker
from datetime import datetime, timedelta

fake = Faker()
DB_NAME = "clinic.db"

def setup_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # --- 1. Create Tables ---
    print("Creating tables...")
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            date_of_birth DATE,
            gender TEXT,
            city TEXT,
            registered_date DATE
        );

        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialization TEXT,
            department TEXT,
            phone TEXT
        );

        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            doctor_id INTEGER,
            appointment_date DATETIME,
            status TEXT,
            notes TEXT,
            FOREIGN KEY(patient_id) REFERENCES patients(id),
            FOREIGN KEY(doctor_id) REFERENCES doctors(id)
        );

        CREATE TABLE IF NOT EXISTS treatments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER,
            treatment_name TEXT,
            cost REAL,
            duration_minutes INTEGER,
            FOREIGN KEY(appointment_id) REFERENCES appointments(id)
        );

        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            invoice_date DATE,
            total_amount REAL,
            paid_amount REAL,
            status TEXT,
            FOREIGN KEY(patient_id) REFERENCES patients(id)
        );
    ''')

    # --- 2. Insert Dummy Data ---
    
    # Doctors (15)
    specs = ['Dermatology', 'Cardiology', 'Orthopedics', 'General', 'Pediatrics']
    doctor_ids = []
    for _ in range(15):
        cursor.execute("INSERT INTO doctors (name, specialization, department, phone) VALUES (?, ?, ?, ?)",
                       (fake.name(), random.choice(specs), "Main Building", fake.phone_number()))
        doctor_ids.append(cursor.lastrowid)

    # Patients (200)
    patient_ids = []
    cities = ["New York", "London", "Hyderabad", "Berlin", "Tokyo", "Paris", "Sydney", "Toronto"]
    for _ in range(200):
        reg_date = fake.date_between(start_date='-1y', end_date='today')
        cursor.execute("INSERT INTO patients (first_name, last_name, email, phone, date_of_birth, gender, city, registered_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       (fake.first_name(), fake.last_name(), fake.email(), fake.phone_number(), 
                        fake.date_of_birth(minimum_age=5, maximum_age=85), random.choice(['M', 'F']), 
                        random.choice(cities), reg_date))
        patient_ids.append(cursor.lastrowid)

    # Appointments (500)
    appt_ids = []
    statuses = ['Scheduled', 'Completed', 'Cancelled', 'No-Show']
    for _ in range(500):
        appt_date = fake.date_time_between(start_date='-1y', end_date='today')
        cursor.execute("INSERT INTO appointments (patient_id, doctor_id, appointment_date, status, notes) VALUES (?, ?, ?, ?, ?)",
                       (random.choice(patient_ids), random.choice(doctor_ids), appt_date, random.choice(statuses), fake.sentence()))
        appt_ids.append(cursor.lastrowid)

    # Treatments (350) - Linked only to completed appts
    for i in range(350):
        cursor.execute("INSERT INTO treatments (appointment_id, treatment_name, cost, duration_minutes) VALUES (?, ?, ?, ?)",
                       (appt_ids[i], fake.word().capitalize() + " Procedure", random.uniform(50, 5000), random.randint(15, 120)))

    # Invoices (300)
    invoice_statuses = ['Paid', 'Pending', 'Overdue']
    for _ in range(300):
        amt = random.uniform(100, 6000)
        status = random.choice(invoice_statuses)
        paid = amt if status == 'Paid' else (0 if status == 'Overdue' else amt * 0.5)
        cursor.execute("INSERT INTO invoices (patient_id, invoice_date, total_amount, paid_amount, status) VALUES (?, ?, ?, ?, ?)",
                       (random.choice(patient_ids), fake.date_between(start_date='-1y', end_date='today'), amt, paid, status))

    conn.commit()
    print(f"Success! Created {len(patient_ids)} patients, {len(doctor_ids)} doctors, and 500 appointments in {DB_NAME}.")
    conn.close()

if __name__ == "__main__":
    setup_database()