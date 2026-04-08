import asyncio
from vanna_setup import vanna_agent  
from vanna.core.user import User, RequestContext

async def seed_memory():
    # Context required for Vanna 2.0 operations
    context = RequestContext(user=User(id="admin", name="Admin User"))

    print("🚀 Seeding agent memory with 15 Q&A pairs...")

    # We use .agent_memory.save_tool_usage to mimic a successful past interaction
    queries = [
        ("How many patients do we have?", "SELECT COUNT(*) AS total_patients FROM patients"),
        ("List all doctors and their specializations", "SELECT name, specialization FROM doctors"),
        ("What is the total revenue?", "SELECT SUM(total_amount) AS total_revenue FROM invoices WHERE status = 'Paid'"),
        ("Which doctor has the most appointments?", "SELECT d.name, COUNT(a.id) as appt_count FROM doctors d JOIN appointments a ON d.id = a.doctor_id GROUP BY d.name ORDER BY appt_count DESC LIMIT 1"),
        ("List all patients from New York", "SELECT * FROM patients WHERE city = 'New York'"),
        ("Show revenue by doctor", "SELECT d.name, SUM(i.total_amount) AS total_revenue FROM invoices i JOIN appointments a ON a.patient_id = i.patient_id JOIN doctors d ON d.id = a.doctor_id GROUP BY d.name ORDER BY total_revenue DESC"),
        ("Average treatment cost by specialization", "SELECT d.specialization, AVG(t.cost) as avg_cost FROM treatments t JOIN appointments a ON t.appointment_id = a.id JOIN doctors d ON a.doctor_id = d.id GROUP BY d.specialization"),
        ("Show monthly appointment count for the past 6 months", "SELECT strftime('%Y-%m', appointment_date) as month, COUNT(*) as count FROM appointments WHERE appointment_date >= date('now', '-6 months') GROUP BY month"),
        ("Top 5 patients by spending", "SELECT p.first_name, p.last_name, SUM(i.total_amount) as total_spent FROM patients p JOIN invoices i ON p.id = i.patient_id GROUP BY p.id ORDER BY total_spent DESC LIMIT 5"),
        ("Show unpaid invoices", "SELECT * FROM invoices WHERE status != 'Paid'"),
        ("How many cancelled appointments last quarter?", "SELECT COUNT(*) FROM appointments WHERE status = 'Cancelled' AND appointment_date >= date('now', '-3 months')"),
        ("Which city has the most patients?", "SELECT city, COUNT(*) as count FROM patients GROUP BY city ORDER BY count DESC LIMIT 1"),
        ("What percentage of appointments are no-shows?", "SELECT (COUNT(CASE WHEN status = 'No-Show' THEN 1 END) * 100.0 / COUNT(*)) as percentage FROM appointments"),
        ("Show the busiest day of the week for appointments", "SELECT strftime('%w', appointment_date) as day_of_week, COUNT(*) as count FROM appointments GROUP BY day_of_week ORDER BY count DESC LIMIT 1"),
        ("Average appointment duration by doctor", "SELECT d.name, AVG(t.duration_minutes) as avg_duration FROM doctors d JOIN appointments a ON d.id = a.doctor_id JOIN treatments t ON a.id = t.appointment_id GROUP BY d.name")
    ]

    for question, sql in queries:
        # save_tool_usage is the core Vanna 2.0 method to store "success" patterns
        await vanna_agent.agent_memory.save_tool_usage(
            question=question,
            tool_name="run_sql", # This identifies that these args belong to the SQL tool
            args={"sql": sql},   # This is the "correct" argument the AI should learn
            context=context,
            success=True         # We mark it as successful so the AI prioritizes it
        )

    print("✅ Memory seeding complete!")

if __name__ == "__main__":
    asyncio.run(seed_memory())