import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COLUMNS = ["id", "date", "time", "person", "domain", "kind", "entity", "summary", "value", "amount", "due", "contact", "link", "source"]

FACTS = [
    ("2026-11-19", "15:30", "Riley", "activities", "practice", "Northside Swim Club", "Swim practice at Northside Aquatic Center", "", "", "", "", "", "mail:1001"),
    ("2026-11-19", "", "Jordan", "school", "assignment", "6th Grade Science - Ortiz", "Waves lab write-up: due 2026-11-20", "", "", "2026-11-20", "", "", "canvas:jordan"),
    ("2026-11-19", "", "Riley", "school", "grade", "Biology Honors", "Unit 4 test score in Biology Honors: 92%", "92%", "", "", "", "", "canvas:riley"),
    ("2026-11-20", "08:00", "Jordan", "school", "quiz", "Math 6 Plus - Chen", "Unit 7.2 quiz in Math 6 Plus", "", "", "2026-11-20", "", "", "canvas:jordan"),
    ("2026-11-20", "16:00", "Biscuit", "pets", "appointment", "Oak Hill Animal Hospital", "Biscuit annual exam and rabies booster at Oak Hill Animal Hospital", "", "", "2026-11-20", "(555) 010-2231", "", "mail:1002"),
    ("2026-11-21", "09:00", "Jordan", "activities", "game", "Riverside Youth Soccer", "U12 Hawks vs. Falcons at Lakeview Park field 3, arrive 8:30", "", "", "", "", "", "text:2001"),
    ("2026-11-21", "18:30", "household", "dining", "reservation", "Lucia Trattoria", "Dinner reservation for 4 at Lucia Trattoria", "", "", "", "", "", "mail:1003"),
    ("2026-11-23", "10:30", "Alex", "health", "appointment", "Main Street Dental", "Dental cleaning at Main Street Dental", "", "", "", "(555) 010-4410", "", "mail:1004"),
    ("2026-11-24", "", "Riley", "school", "form", "Westbrook High School", "Permission form for the science museum field trip due to Ms. Park", "", "15", "2026-11-24", "", "", "mail:1005"),
    ("2026-11-25", "06:15", "household", "travel", "flight", "Delta", "Delta 1422 PDX to DEN departs 6:15 AM, confirmation in the trip mail", "", "", "2026-11-25", "", "", "mail:1006"),
    ("2026-11-26", "", "household", "calendar", "event", "Grandma Jo", "Thanksgiving dinner at Grandma Jo's", "", "", "", "", "", "text:2002"),
    ("2026-11-29", "13:40", "household", "travel", "flight", "Delta", "Delta 1987 DEN to PDX return flight departs 1:40 PM", "", "", "2026-11-29", "", "", "mail:1006"),
    ("2026-12-01", "", "household", "home", "renewal", "Bright Pest Control", "Quarterly pest service renews; technician visit window 8 AM to noon", "", "89", "2026-12-01", "", "vendors/bright-pest-control", "mail:1007"),
    ("2026-12-04", "", "Sam", "home", "registration", "State DMV", "Registration renewal due for the 2021 Honda Odyssey", "", "38.75", "2026-12-04", "", "vehicles/honda-odyssey", "mail:1008"),
    ("2026-12-15", "", "household", "finance", "bill", "City Power & Light", "City Power & Light bill due", "", "142.18", "2026-12-15", "", "", "mail:1009"),
    ("2027-03-02", "", "Alex", "health", "passport", "U.S. Department of State", "Alex's passport expires", "", "", "2027-03-02", "", "", "file:documents/library/passports.pdf"),
    ("2027-06-30", "", "household", "home", "warranty", "Carrier", "Carrier heat pump parts warranty ends", "", "", "2027-06-30", "", "appliances/heat-pump", "file:documents/library/heat-pump-warranty.pdf"),
    ("2026-10-02", "", "Biscuit", "pets", "vaccine", "Oak Hill Animal Hospital", "Biscuit got the Bordetella vaccine", "", "48", "", "", "", "mail:1010"),
    ("2026-09-14", "", "household", "home", "repair", "Ace Plumbing", "Ace Plumbing replaced the water heater expansion tank", "", "312", "", "(555) 010-7781", "vendors/ace-plumbing", "mail:1011"),
    ("2026-06-03", "", "household", "home", "repair", "Ace Plumbing", "Ace Plumbing cleared the kitchen drain line", "", "175", "", "(555) 010-7781", "vendors/ace-plumbing", "mail:1012"),
    ("2026-08-20", "", "Jordan", "health", "appointment", "Pine Pediatrics", "Jordan sports physical at Pine Pediatrics, cleared for soccer", "", "", "", "", "", "mail:1013"),
    ("2026-11-12", "", "Sam", "dining", "preference", "", "Sam wants whole milk, not 2%", "", "", "", "", "", "text:2003"),
    ("2026-11-05", "", "household", "purchases", "order", "Costco", "Costco order: air filters 20x25x1, 4-pack", "20x25x1", "54.99", "", "", "property/hvac", "mail:1014"),
]
SERIES = ("2026-11-02", "17:00", "Riley", "activities", "lesson", "Harmony Music", "Piano lesson with Ms. Grant", "repeats on 6 dates: 2026-11-02 2026-11-09 2026-11-16 2026-11-23 2026-11-30 2026-12-07", "", "", "", "", "calendar:Family")

MAIL = {
    1001: ("Northside Swim Club", "Thursday practice moved", "Coach Dana: Thursday practice for the Gold group moves to 3:30 PM at Northside Aquatic Center this week."),
    1002: ("Oak Hill Animal Hospital", "Reminder: Biscuit's appointment", "Biscuit is due for an annual exam and a rabies booster. See you Friday, November 20 at 4:00 PM. Call (555) 010-2231 to reschedule."),
    1003: ("Lucia Trattoria", "Your reservation is confirmed", "Party of 4, Saturday November 21 at 6:30 PM."),
    1004: ("Main Street Dental", "Appointment reminder", "Alex, your cleaning is Monday November 23 at 10:30 AM."),
    1005: ("Westbrook High School", "Field trip permission form", "Please return the signed form and the $15 fee to Ms. Park by Tuesday, November 24."),
    1006: ("Delta", "Your trip confirmation", "Outbound Delta 1422 PDX to DEN, Wed Nov 25, 6:15 AM. Return Delta 1987 DEN to PDX, Sun Nov 29, 1:40 PM. Four passengers."),
    1007: ("Bright Pest Control", "Quarterly service renewal", "Your quarterly plan renews December 1 for $89. Your technician arrives between 8 AM and noon."),
    1008: ("State DMV", "Vehicle registration renewal", "Registration for your 2021 Honda Odyssey expires December 4. Renewal fee: $38.75."),
    1009: ("City Power & Light", "Your bill is ready", "Amount due $142.18 by December 15."),
    1010: ("Oak Hill Animal Hospital", "Visit receipt", "Bordetella vaccine, $48.00."),
    1011: ("Ace Plumbing", "Invoice 4471", "Replaced water heater expansion tank. Parts and labor $312.00."),
    1012: ("Ace Plumbing", "Invoice 4310", "Cleared kitchen drain line. $175.00."),
    1013: ("Pine Pediatrics", "Visit summary", "Sports physical for Jordan. Cleared for soccer."),
    1014: ("Costco", "Order confirmation", "Filtrete air filter 20x25x1, 4-pack, $54.99."),
}
TEXTS = {
    2001: [{"when": "2026-11-18 19:02", "from": "Coach Mike", "text": "Saturday 9am vs Falcons, Lakeview Park field 3. Please arrive by 8:30!"}],
    2002: [{"when": "2026-11-15 12:40", "from": "Grandma Jo", "text": "Thanksgiving at my house, dinner at 3. Bring the rolls!"}],
    2003: [{"when": "2026-11-12 08:15", "from": "Sam", "text": "can you grab whole milk, not 2%"}],
}
PEOPLE = {"sam": ("Sam", "parent"), "alex": ("Alex", "parent"), "riley": ("Riley", "daughter, 10th grade at Westbrook High School"), "jordan": ("Jordan", "son, 6th grade at Cedar Middle School"), "biscuit": ("Biscuit", "dog, golden retriever")}
RECORDS = {
    "vendors/ace-plumbing.md": "---\ntype: vendor\nname: Ace Plumbing\nupdated: 2026-09-14\ntrade: plumbing\nphone: (555) 010-7781\nwould_use_again: yes\n---\n\nAce Plumbing fixed the expansion tank and the kitchen drain.\n",
    "vendors/bright-pest-control.md": "---\ntype: vendor\nname: Bright Pest Control\nupdated: 2026-11-01\ntrade: pest control\n---\n\nQuarterly plan, $89 per visit.\n",
    "vehicles/honda-odyssey.md": "---\ntype: vehicle\nname: 2021 Honda Odyssey\nupdated: 2026-11-01\n---\n\nThe family van. Registration renews every December.\n",
    "appliances/heat-pump.md": "---\ntype: appliance\nname: Carrier heat pump\nupdated: 2026-06-30\n---\n\nInstalled 2017. Parts warranty ends 2027-06-30.\n",
    "property/hvac.md": "---\ntype: property\nname: HVAC\nupdated: 2026-11-05\n---\n\nThe return vent takes a 20x25x1 filter. Change it every 90 days.\n",
}


def write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def main():
    rows = [(f"F{n:06d}", *fact) for n, fact in enumerate(FACTS + [SERIES], start=1)]
    for year in ("2026", "2027"):
        write_csv(ROOT / f"facts/{year}.csv", COLUMNS, [r for r in rows if r[1].startswith(year)])
    for row, (sender, subject, body) in MAIL.items():
        path = ROOT / f"sample/mail/{row}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"sender": sender, "subject": subject, "body": body}))
    for row, thread in TEXTS.items():
        path = ROOT / f"sample/texts/{row}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(thread))
    for slug, (name, role) in PEOPLE.items():
        path = ROOT / f"people/{slug}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\ntype: person\nname: {name}\nupdated: 2026-11-19\n---\n\n{name}: {role}.\n")
    for rel, text in RECORDS.items():
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    names = sorted({f[5] for f in FACTS + [SERIES] if f[5]})
    write_csv(ROOT / "organizations/organizations.csv", ["id", "name", "kind", "record"], [(n.lower().replace(" ", "-").replace(".", ""), n, "vendor", "") for n in names])
    write_csv(ROOT / "organizations/names.csv", ["name", "org", "unit"], [(n, n.lower().replace(" ", "-").replace(".", ""), "") for n in names])
    write_csv(ROOT / "expenses/ledger.csv", ["id", "date", "vendor", "category", "kind", "amount", "summary", "mail_id"], [
        ("P0001", "2026-09-14", "Ace Plumbing", "home", "invoice", "312", "Expansion tank replacement", "1011"),
        ("P0002", "2026-06-03", "Ace Plumbing", "home", "invoice", "175", "Kitchen drain cleared", "1012"),
        ("P0003", "2026-11-05", "Costco", "purchases", "receipt", "54.99", "Air filters 20x25x1", "1014"),
    ])
    write_csv(ROOT / "documents/summaries.csv", ["path", "title", "summary", "household"], [])
    write_csv(ROOT / "documents/sources.csv", ["path", "source"], [])
    write_csv(ROOT / "documents/fact-links.csv", ["fact", "path"], [])
    write_csv(ROOT / "unread/invites-and-tickets.csv", ["date", "kind", "sender", "subject", "source"], [])


if __name__ == "__main__":
    main()
