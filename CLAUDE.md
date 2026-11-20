# Household knowledgebase

This repository holds what one household knows about its home, family, vehicles, vendors, health, school, money and devices. Claude reads and edits it. `bin/kb` answers questions from it.

## The household

`household.toml` lists every person and pet, their roles, the areas, and the sources the collector reads. Read it first.

- Only the people and pets in `household.toml` are family. Any other name belongs to a friend, a relative, a classmate, a neighbor or a vendor contact.
- A fact about someone outside the family carries person `other`. Give anyone who comes up often a record in `people/` with a `relationship`.
- A person or pet with `status = "passed"` keeps their history. Never add a next visit or a reminder for them.

## Read every document

Reading documents is the main job of this repository. Every file that enters `documents/` or `vault/` gets opened and read: every page of a PDF, every image, every mail, every spreadsheet. Its facts go into `facts/`, its title and summary go into `documents/summaries.csv`, and each fact links to its file in `documents/fact-links.csv`.

- Never file a document by its name, its sender or its folder alone.
- Never count a document as covered because the mail or text that carried it was read.
- Before you say something is not in the knowledgebase, search `documents/summaries.csv` and open the likely files.
- `bin/kb check` warns on every document with no title from a reader. That count must reach zero.

## Answer a question

Run `bin/kb` first. Open a file only after `bin/kb` names it.

| Question | Command |
| --- | --- |
| What happened, for whom, when | `bin/kb facts [words] --person <name> --domain health --since 2025-01-01` |
| Anything about a word | `bin/kb find roof` |
| One vendor, vehicle, appliance, device, room, job or person | `bin/kb show <name>` |
| One school, doctor, airline or other organization, under every spelling | `bin/kb org <name>` |
| What links to a record or organization, and how | `bin/kb links vendors/<slug>` |
| Every record in a folder | `bin/kb list devices --fields name,purchased,serial,owner` |
| The mail or text behind a fact | `bin/kb source F000123` |
| What each person has this week, and which outings need a driver | `bin/kb week --days 7` |
| Totals and anything else | `bin/kb sql "select domain, count(*) from facts group by 1"` |
| Data problems | `bin/kb check` |

Add `--json` before the command name for JSON. Quote a fact with its id and its source. Say `unknown` when `bin/kb` finds nothing.

## Layout

| Path | Holds |
| --- | --- |
| `household.toml` | People, pets, areas, sources and the time zone |
| `facts/<year>.csv` | Every dated fact, one row each |
| `property/`, `appliances/`, `vehicles/`, `vendors/`, `work/`, `devices/`, `people/`, `policies/` | One markdown record per thing |
| `organizations/` | `organizations.csv` (one row per organization) and `names.csv` (every spelling in the facts, mapped to its organization) |
| `expenses/ledger.csv` | One row per payment |
| `documents/archive/` | Copies of attachments and mail by category and year |
| `documents/sources.csv`, `summaries.csv`, `fact-links.csv` | Where each document came from, what it says, and which facts it proves |
| `vault/`, `secrets/` | Identity, medical, finance and license files. git-crypt encrypts both. |
| `kb/`, `bin/`, `tests/` | The library, its commands and its tests |
| `kb/instructions/` | The reviewer's instructions for each kind of work |

## Fact columns

`id, date, time, person, domain, kind, entity, summary, value, amount, due, contact, link, source`

- `date`: the event date when the source states one, otherwise the date of the source. Use local time.
- `person`: a name from `household.toml`, `household`, `other`, or empty when the source does not say.
- `domain`: one of the areas in `household.toml`.
- `entity`: the provider, school, vendor or place as the source writes it.
- `value`: a score, dose, time or serial number. `amount`: a number in the household's currency.
- `link`: the record the fact belongs to, such as `vendors/ace-plumbing`.
- `source`: `mail:<id>`, `text:<id>`, `calendar:<calendar name>`, `canvas:<id>`, `slack:<channel>:<ts>`, `file:<path>` or `person:<name>`. Separate several sources with a space.

## Add or change

- Add facts with `bin/kb add`. It reads one JSON object per line, validates each one and skips a fact that already exists.
- Fix a fact by editing its row in `facts/<year>.csv`. Never change an `id`.
- Every record file starts with YAML frontmatter with `type`, `name` and `updated`. Copy the matching file in `templates/` to start a record.
- When `bin/kb check` warns that an entity name has no organization entry, add the name to `organizations/names.csv`.
- After every change run `bin/kb check` and `bin/test`. `bin/kb check` must report zero errors.

## Rules

- One fact lives in one place. Link to it, never copy it.
- Record an unknown as `unknown`. Never guess a model number, date, price or owner.
- Every fact names its source.
- Copy a title, name, number and date exactly as the source writes it.
- Never store a password, an account number or an alarm code outside `vault/` and `secrets/`. Elsewhere, write where the secret lives.
- Keep this household's repository private.
