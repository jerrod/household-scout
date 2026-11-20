# Extract facts from new mail, texts and calendar events

Read every row in the inbox files to the last line. Write one JSON object per fact, one per line, and pipe the lines to `bin/kb add`.

```
{"date": "2026-11-20", "time": "14:45", "person": "Riley", "domain": "health", "kind": "appointment", "entity": "Main Street Dental", "summary": "Cleaning and exam", "value": "", "amount": "", "due": "", "contact": "", "link": "", "source": "mail:283101"}
```

- Record only what the source states. Leave a field empty when the source does not state it.
- Copy numbers, doses, scores, dates, names and titles exactly.
- `date` is the event or due date when the source states one, otherwise the date of the source.
- `person` is a name from `household.toml`, `household` or `other`. Leave it empty when the source does not say who.
- `domain` is one of the areas in `household.toml`.
- Use a `kind` that `bin/kb sql "select kind, count(*) from facts where domain = '<domain>' group by 1 order by 2 desc"` already lists, when one fits.
- Set `link` to the vendor, vehicle, appliance, device or property record the fact belongs to. Create the record first when a new vendor does work or takes a payment.
- `source` is `mail:<id>`, `text:<message id>` or `calendar:<calendar name>`.
- Skip login codes, marketing and a second copy of the same mail.
- Never copy a password, an account number, a member id, a policy number, a card number or a Social Security number.
- A calendar event becomes a fact with the title copied exactly. `bin/kb calendar --since 2026-11-01` prints every Calendar.app event from that date with its original title.
- After a payment, add a row to `expenses/ledger.csv`. After a job, create a `work/` record and update the linked property, appliance or vehicle record.
- Write `entity` as the source writes it. After `bin/kb add`, run `bin/kb check` and map each new name in `organizations/names.csv`.
- Add each archived attachment to `documents/sources.csv` with `mail:<id>` so the fact links to its evidence.
