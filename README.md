# household-scout

household-scout turns a family's mail, texts, calendars, school portals, chat and documents into one sourced record of facts. Claude reads every item and writes what it learns to plain CSV and markdown files in a private git repository. Every fact names the mail, text or file it came from. Any agent can then answer questions from those files over a command line or MCP.

household-scout is the knowledge and retrieval layer only. It doesn't send messages or take actions. Put any agent on top of it.

## Try it

```sh
git clone https://github.com/jerrod/household-scout
cd household-scout
bin/demo
bin/kb find plumb
bin/kb source F000005
```

`bin/demo` builds Maple Lane, a made-up household with two parents, two kids and a dog. Every command below works on it.

## Start your own household

1. Run `bin/init-household ~/household`. It makes a new folder with the code, an empty fact table and its own git repository.
2. Edit `household.toml` in that folder. List each person with a role, each pet, your time zone, the areas you track and the sources you read.
3. Set up git-crypt for `vault/` and `secrets/`.
4. Create a private GitHub repository and add it as `origin`. `bin/kb-guard` stops every worker from pushing to a repository that is not private.
5. Copy the files in `templates/launchd/` to `~/Library/LaunchAgents/`, set the repository path in each one, and load them.
6. Grant Full Disk Access to `/bin/zsh`, so launchd jobs can read Mail and Messages.

Every person whose messages Claude reads must agree to it first. Leave out every source someone hasn't agreed to.

## Parts

| Part | What it does |
| --- | --- |
| `household.toml` | Lists the people, pets, areas, sources and time zone. Every other part reads it. |
| Collector (`kb/ingest.py`) | Runs every hour. Writes new mail, texts, calendar events, files, Canvas items, gradebook changes and Slack messages to `inbox/<date>/`. |
| Classifier (`kb/jev.py`) | Labels each new mail with an area and a confidence, so the reviewer reads the important mail first. |
| Reviewer (`bin/kb-collect-worker`, `bin/kb-task-worker`) | Runs `claude -p` on Sonnet with an allow-list of tools. Reads every inbox row and writes facts, records and document summaries. |
| Secret scan (`kb/secret_scan.py`) | Checks every new archive file before each commit. Moves a file with a key, password or account number into the vault. |
| `bin/kb` | Builds a SQLite index from the files and answers questions. |
| Fold (`bin/kb-fold-recurring`) | Turns a repeating event into one fact that lists every date. |
| Audit (`bin/kb-audit-review`) | Lists facts where the classifier disagrees with the stored person or area, then has the reviewer recheck each one against its source. |
| Agent calendar (`kb/agent_calendar.py`) | Writes every future date to a calendar called Agent events, with a daily digest at 7 AM. |
| Intake (`kb/intake.py`, `bin/kb-intake-worker`) | Pulls facts and documents that agents submit to your server, and has the reviewer check each one before it reaches git. |

## Facts

Each fact is one row in `facts/<year>.csv`.

| Column | What goes in it |
| --- | --- |
| `id` | A stable `F######`. Never reuse or change one. |
| `date`, `time` | The event's date when the source gives one, otherwise the source's date, in local time. |
| `person` | A name from `household.toml`, `household`, or `other`. |
| `domain` | An area from `household.toml`. |
| `kind` | The kind of fact, such as appointment, bill or assignment. |
| `entity` | The provider, school or vendor, spelled the way the source spells it. |
| `summary` | One sentence that works as a calendar title. |
| `value`, `amount`, `due` | A score or dose, an amount, a due date. |
| `source` | Where the fact came from, such as `file:documents/archive/...` or `slack:<channel>:<ts>`. |

Records are markdown files with frontmatter, one per vehicle, vendor, appliance, device, room, job, person and insurance policy. Start each one from `templates/`. `bin/kb build` works out every link between facts, people, organizations, records and documents.

## Areas

The sample config has these areas. Add, rename or remove areas in `household.toml`.

| Area | Holds |
| --- | --- |
| health | Medical, dental, vision, pharmacy and therapy |
| school | Classes, grades, assignments, teachers and school events |
| activities | Sports, camps, lessons, clubs and outings |
| calendar | A family plan that fits no other area |
| travel | Trips, flights, hotels and rentals |
| dining | Restaurants, recipes and groceries |
| home | The house, yard, repairs, utilities, appliances and vehicles |
| purchases | Orders and returns |
| finance | Banks, cards, bills, loans, investments and pay |
| taxes | Returns, forms and accountants |
| insurance | Policies, coverage, renewals and claims |
| legal | Wills, powers of attorney, guardianship and beneficiaries |
| civic | IDs, voting, jury duty and government notices |
| care | Nannies, sitters, tutors, eldercare and custody schedules |
| emergency | Contacts, shutoffs, medications and plans |
| pets | Vets and pet supplies |
| job | Employers, clients, meetings and contracts |

Each area has an `access` setting of `adults` or `everyone`. A server that serves the knowledgebase can filter by it.

## Sources

Turn each source on in `household.toml`. A source that isn't listed is skipped.

| Source | Reader | How it reads |
| --- | --- | --- |
| Apple Mail | `apple_mail` | Opens Mail's database read-only, then the message files. Writes the text of each PDF next to it. |
| Gmail | `gmail` | Calls the Gmail API with an OAuth refresh token in `~/.config/household-scout/gmail.json`. Uses history IDs as the cursor. |
| Messages | `messages` | Opens `~/Library/Messages/chat.db` read-only. |
| Calendar | `apple_calendar` | Opens the Calendar cache read-only and skips the calendars in `skip`. |
| Documents | `documents` | Picks up files changed in `~/Documents` since the last run. |
| Canvas | `canvas` | Uses a parent observer token for each student. Fetches assignments, submissions, syllabi and module outlines. |
| Infinite Campus | `infinite_campus` | Signs in to the parent portal and writes only what changed. |
| Slack | `slack` | Uses a user token with read scopes. Fetches new messages and new thread replies. |

Each reader returns new rows and a cursor. To add a source, write one file in `kb/sources/` with a `collect` function, then call it from `kb/ingest.py`. Tokens go in `~/.config/household-scout/`, readable only by you.

## The reviewer

Each kind of work has one instruction file in `kb/instructions/`. Each worker runs it the same way.

1. The worker checks that `origin` is private.
2. It takes a lock folder, so only one worker writes at a time.
3. It pulls and rebuilds the index.
4. It runs `claude -p` on Sonnet with an explicit `--allowedTools` list. The list allows no network tools and no git writes.
5. It throws the changes away when Claude writes no `REVIEWED.md` report.
6. It stops unless `bin/kb check` reports zero errors and `bin/test` passes.
7. It runs the secret scan, commits with the report as the message, and pushes. It retries the push three times.

## Backfills

A backfill exports a source's history once and splits it into chunks. The reviewer reads one chunk per run, and a rerun starts at the next chunk.

- **Chat:** group messages into conversations with no gap over three hours. Pack whole conversations into chunks of about 300 messages. Download every file. Write every shared URL to a CSV file.
- **Bills:** match each bill to its mail. Set the due date and amount.
- **Payments:** name the card that paid each bill from a card map in the vault.
- **Health:** give the reviewer 30 vault files per chunk as an explicit list.

## Clean data

- Convert every UTC time to local time before the reviewer sees it.
- When a second source confirms a fact, add the source to the existing row.
- Write `unknown`. Never guess a model number, a date or a price.
- Cite the archived file as `file:<path>`, because Mail row IDs differ between Macs.
- Scan raw files for secrets before the first commit. Chat and mail archives often hold credentials, and git keeps every commit.

## Where it runs

| Option | Collectors | Reviewer | Model billing |
| --- | --- | --- | --- |
| Mac with Claude Code | The Mac | `claude -p` on the Mac | Subscription |
| Mac with the Claude API | The Mac | The Claude Agent SDK on the Mac | Per token |
| Hosted | A cloud server that calls the Gmail, Calendar, LMS and Slack APIs | The Agent SDK on the same server | Per token |
| Managed Agents | Cloud APIs, or a Mac that uploads its inbox | Anthropic runs the loop on a schedule | Per token, plus sessions |

An Apple household needs a Mac to read iMessage. A Google or Microsoft household can run fully hosted.

## Models

| Job | Model |
| --- | --- |
| Sort mail into read-first and read-later | Jev or Haiku 5.5 |
| Read a document and pull out facts | Sonnet 5.5 |
| Merge near-duplicate facts and settle conflicts | Sonnet 5.5 at higher effort |

## Assumptions

| Area | Assumption | If it doesn't hold |
| --- | --- | --- |
| Hardware | An always-on Mac signed in to Mail, Messages and Calendar | Use the Gmail reader and run hosted |
| Model access | A Claude subscription that runs `claude -p` for hours | Pay per token through the Claude API |
| Storage | One private git repository holds facts and documents | Move large files to Git LFS or object storage |
| Writers | One writer at a time | Use a queue or a database with transactions |
| Secrets | The secret scan reads text files only | Add OCR for images, or keep raw archives outside git |

## Security

- Each household's repository must be private. `bin/kb-guard` blocks every push to a public one.
- This repository commits code only. `.gitignore` allows code folders and blocks every data folder.
- `tests/test_privacy.py` fails when any committed file holds a word from a private list. CI reads the list from a repository secret.
- Report a security problem privately. See `SECURITY.md`.

## License

MIT
