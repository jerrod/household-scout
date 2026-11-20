import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from kb import jev  # noqa: E402
from kb.schema import FAMILY, PETS  # noqa: E402

DOMAINS = {
    "health": "Medical, dental, vision, pharmacy, therapy, insurance claims for care.",
    "school": "A child's school: classes, grades, assignments, teachers, school events and fees.",
    "activities": "Sports, camps, lessons, clubs, gym, shows and outings.",
    "calendar": "A general family plan or date that fits no other area.",
    "travel": "Trips, flights, hotels, rentals and itineraries.",
    "dining": "Restaurants, recipes, groceries planned for meals.",
    "home": "The house, yard, repairs, contractors, utilities, appliances and vehicles.",
    "purchases": "Things bought or shopped for, orders and returns.",
    "finance": "Banks, cards, bills, loans, insurance premiums, investments and pay.",
    "taxes": "Tax returns, forms, assessments and accountants.",
    "pets": "Pet care, vets and pet supplies.",
    "job": "Paid work: employers, clients, work meetings and contracts.",
}
CONFIDENT = 0.85


def questions():
    people = {name: f"{name}, a family {'pet' if name in PETS else 'member'}." for name in FAMILY + PETS}
    people.update({"household": "The whole household or the house itself, not one person.", "other": "Someone outside the family."})
    return {
        "domain": {"type": "choice", "instructions": "Which household area does the `fact` belong to?", "criteria": DOMAINS},
        "person": {"type": "choice", "instructions": "Who is the `fact` about?", "criteria": people},
    }


def state_of(fact):
    return {"fact": f"{fact['date']} [{fact['kind']}] {fact['entity']}: {fact['summary']}"}


def disagreements(facts, ask=None):
    ask = ask or (lambda states: jev.ask_many(states, questions()))
    found = []
    for fact, answers in zip(facts, ask([state_of(f) for f in facts])):
        domain, person = answers["domain"], answers["person"]
        if domain["choice"] != fact["domain"] and domain["confidence"] >= CONFIDENT:
            found.append({"id": fact["id"], "field": "domain", "has": fact["domain"], "jev": domain["choice"], "confidence": domain["confidence"], "summary": fact["summary"]})
        named = person["choice"] in FAMILY + PETS and fact["person"] in FAMILY + PETS
        if named and person["choice"] != fact["person"] and person["confidence"] >= CONFIDENT:
            found.append({"id": fact["id"], "field": "person", "has": fact["person"], "jev": person["choice"], "confidence": person["confidence"], "summary": fact["summary"]})
    return found
