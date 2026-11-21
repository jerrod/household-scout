from kb.household import CONFIG

DEFAULT_DOMAINS = {
    "home": "The house: work done on it, appliances, tools, utilities, HOA, closing, taxes, home insurance, smart-home and security.",
    "vehicle": "A car, truck or motorcycle: purchase, service, registration, recall, insurance.",
    "school": "A child's school: grades, assignments, attendance, teachers, schedules, fees, forms, events.",
    "kids": "A child's activities outside school: sports, clubs, camps, lessons, childcare, parties.",
    "health": "Medical, dental, vision, pharmacy, lab results, health insurance, vaccination records.",
    "calendar": "An invite, reminder, reservation, itinerary or ticket for a dated event.",
    "finance": "Bank, card, tax, loan, mortgage, investment, payroll, benefits, subscription or purchase receipt for the household.",
    "legal_id": "Legal documents, government mail, identity, passport, licenses, wills, contracts.",
    "pets": "Veterinary, pet supplies, pet insurance, boarding.",
    "family": "A personal message from a relative or friend.",
    "other": "Marketing, newsletters, social media, work, shopping offers or anything else.",
}

DEFAULT_SUBTYPES = {
    "home": {
        "contractor_work": "Invoice, estimate or appointment from a contractor or trade.",
        "appliance": "Purchase, warranty, manual or service for an appliance.",
        "tools_equipment": "Purchase or warranty for a tool or yard equipment.",
        "utilities": "Electric, gas, water, sewer, trash or internet service.",
        "hoa": "Homeowners association dues, rules or requests.",
        "purchase_closing": "Home buying, selling, closing or mortgage paperwork for the house.",
        "property_tax": "Property tax bill or assessment.",
        "home_insurance": "Homeowner's insurance policy, renewal or claim.",
        "smart_home_security": "Thermostat, doorbell, lock, camera or alarm service.",
    },
    "vehicle": {
        "purchase_lease": "Buying, leasing or selling a vehicle.",
        "service_repair": "Oil change, repair, tires or maintenance receipt.",
        "registration_inspection": "DMV registration, plates or inspection.",
        "auto_insurance": "Auto insurance policy or renewal.",
        "recall": "Safety recall or warranty campaign.",
    },
    "school": {
        "grades": "Grades, report cards or progress reports.",
        "assignments": "Homework, assignments, projects or tests.",
        "attendance": "Absences, tardies or attendance notices.",
        "teacher_message": "A message from a teacher or counselor.",
        "schedule_calendar": "Class schedule, school calendar or early release.",
        "fees_forms": "Fees, permission slips, registration or forms.",
        "school_news": "General school or district announcements.",
    },
    "kids": {
        "sports": "A sports team, game, practice or league.",
        "clubs_camps": "A club, camp or program.",
        "lessons": "Music, tutoring or other lessons.",
        "childcare": "Daycare, babysitter or aftercare.",
        "party_social": "A birthday party or social invitation.",
    },
    "health": {
        "appointment": "A medical or dental appointment.",
        "bill_claim": "A medical bill or insurance claim.",
        "lab_result": "A lab or test result.",
        "prescription": "A pharmacy or prescription notice.",
        "health_insurance": "Health insurance plan or enrollment.",
        "vaccination_record": "Immunization or vaccination record.",
    },
    "calendar": {
        "invite": "A calendar invitation.",
        "reminder": "An appointment reminder.",
        "reservation": "A restaurant, hotel or booking confirmation.",
        "travel_itinerary": "Flight, rental car or trip itinerary.",
        "ticket": "An event ticket.",
    },
    "finance": {
        "bank_statement": "A bank account statement or alert.",
        "credit_card": "A credit card statement or alert.",
        "tax": "Income tax documents or notices.",
        "loan_mortgage": "A mortgage or loan statement.",
        "investment": "A brokerage or retirement statement.",
        "payroll_benefits": "Pay stubs or employee benefits.",
        "subscription": "A recurring subscription charge.",
        "purchase_receipt": "A receipt for a one-time purchase.",
    },
    "legal_id": {
        "legal_document": "A will, contract or legal filing.",
        "government": "Government mail or notice.",
        "identity_travel_docs": "Passport, license or travel document.",
    },
    "pets": {
        "vet": "A veterinary visit or record.",
        "pet_supplies": "Pet food or supplies.",
    },
}



def merged(defaults, extra):
    out = {**defaults, **extra}
    return {name: about for name, about in out.items() if about}


def domains(config=CONFIG):
    found = merged(DEFAULT_DOMAINS, config.get("mail", {}).get("domains", {}))
    return {**{k: v for k, v in found.items() if k != "other"}, "other": found.get("other", DEFAULT_DOMAINS["other"])}


def subtypes(config=CONFIG):
    extra = config.get("mail", {}).get("subtypes", {})
    names = set(DEFAULT_SUBTYPES) | set(extra)
    found = {name: merged(DEFAULT_SUBTYPES.get(name, {}), extra.get(name, {})) for name in names}
    return {name: kinds for name, kinds in found.items() if kinds}
