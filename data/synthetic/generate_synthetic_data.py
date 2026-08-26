"""Generate synthetic clients.csv and leads.csv for the FinAssist AI portfolio demo.

All data produced by this script is entirely fictional and generated with a fixed
random seed for reproducibility. No real people, companies, or financial values are
used. Re-run this script any time to regenerate the CSVs from scratch.
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

SEED = 42
NUM_CLIENTS = 40
NUM_LEADS = 40

OUTPUT_DIR = Path(__file__).parent

SERVICES = [
    "Retirement Planning",
    "Investment Advisory Consultation",
    "Tax Planning Consultation",
    "Estate Planning Guidance",
    "Business Financial Consulting",
]

ADVISORS = [
    "Morgan Ellis",
    "Priya Nandakumar",
    "Jordan Fitzgerald",
    "Aisha Bello",
    "Daniel Kowalski",
    "Sofia Reyes",
]

ACCOUNT_STATUSES = ["Active", "Pending", "Closed"]
ONBOARDING_STATUSES = ["Complete", "Documents Pending", "In Review"]

LEAD_SOURCES = ["Referral", "Website", "Event", "Cold Outreach"]
LEAD_STATUSES = ["New", "Contacted", "Qualified", "Unqualified"]
ENGAGEMENT_LEVELS = ["High", "Medium", "Low"]

EMAIL_DOMAINS = ["example.com", "example.org", "example.net"]


def random_date(start_days_ago: int, end_days_ago: int) -> date:
    """Return a random date between `end_days_ago` and `start_days_ago` days in the past."""
    delta_days = random.randint(end_days_ago, start_days_ago)
    return date.today() - timedelta(days=delta_days)


def fake_email(fake: Faker, name: str) -> str:
    local = name.lower().replace(" ", ".")
    return f"{local}@{random.choice(EMAIL_DOMAINS)}"


def generate_clients(fake: Faker) -> list[dict]:
    clients = []
    for i in range(NUM_CLIENTS):
        client_id = f"C{1001 + i}"
        name = fake.name()
        created = random_date(400, 30)
        last_contact = random_date(29, 0)
        onboarding_status = random.choice(ONBOARDING_STATUSES)
        account_status = (
            "Active" if onboarding_status == "Complete" else random.choice(["Pending", "Active"])
        )
        # Sprinkle in a few closed accounts regardless of onboarding status.
        if random.random() < 0.1:
            account_status = "Closed"

        clients.append(
            {
                "client_id": client_id,
                "name": name,
                "email": fake_email(fake, name),
                "service": random.choice(SERVICES),
                "account_status": account_status,
                "onboarding_status": onboarding_status,
                "assigned_advisor": random.choice(ADVISORS),
                "last_contact": last_contact.isoformat(),
                "created_date": created.isoformat(),
            }
        )
    return clients


def generate_leads(fake: Faker) -> list[dict]:
    leads = []
    for i in range(NUM_LEADS):
        lead_id = f"L{1001 + i}"
        name = fake.name()
        created = random_date(200, 5)
        last_contact = random_date(4, 0)

        leads.append(
            {
                "lead_id": lead_id,
                "name": name,
                "email": fake_email(fake, name),
                "company": fake.company(),
                "service_interest": random.choice(SERVICES),
                "engagement_level": random.choice(ENGAGEMENT_LEVELS),
                "information_complete": random.choice(["Yes", "No"]),
                "source": random.choice(LEAD_SOURCES),
                "status": random.choice(LEAD_STATUSES),
                "created_date": created.isoformat(),
                "last_contact": last_contact.isoformat(),
            }
        )
    return leads


def write_csv(rows: list[dict], filename: str) -> Path:
    path = OUTPUT_DIR / filename
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def main() -> None:
    random.seed(SEED)
    fake = Faker()
    Faker.seed(SEED)

    clients = generate_clients(fake)
    leads = generate_leads(fake)

    clients_path = write_csv(clients, "clients.csv")
    leads_path = write_csv(leads, "leads.csv")

    print(f"Wrote {len(clients)} clients to {clients_path}")
    print(f"  columns: {list(clients[0].keys())}")
    print(f"Wrote {len(leads)} leads to {leads_path}")
    print(f"  columns: {list(leads[0].keys())}")


if __name__ == "__main__":
    main()
