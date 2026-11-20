# Review newly collected mail, texts, calendar events and files

The hourly collector wrote what arrived since its last run to `inbox/<date>/`: `mail.jsonl`, `texts.jsonl`, `calendar.jsonl`, `documents.jsonl`. Read `CLAUDE.md` first. Then work through every row of every file, to the last row.

## Mail

Each row has `id` (the Mail row id on this Mac), `sender`, `subject`, `snippet`, `saved` and `files`. The collector already saved each mail: `inbox/<date>/mail/<id>/body.txt` holds the full text, `<id>.eml` the original, and `files` lists the attachments it extracted. Read those files. You do not need access to the Mail app.

1. Skip marketing, newsletters with no date or consequence, sign-in codes, security alerts, and receipts for work purchases. Count what you skip.
2. For every other mail, read the whole `body.txt`.
3. When the mail or any attachment holds a household fact, move the `.eml` and the attachments that matter into `documents/archive/<category>/<year>/` (or `vault/archive/<category>/<year>/` for medical, identity, tax and financial records). Name each one `<YYYY-MM-DD>_<sender-slug>_<short-description>.<ext>`.
4. Read every saved attachment in full. For a PDF, Word, PowerPoint, Excel or text file, the collector wrote its text next to it as `<file>.txt`. Open an image with the Read tool.
5. For a bill, receipt or payment, name the card or account that paid it from `vault/finance/cards.md`, as `; paid with <card name>` in the summary. Never write card digits outside `vault/`.
5. Add facts with `bin/kb add`. Set `source` to `file:<path of the saved .eml>`. Never use `mail:<id>`: Mail row ids differ between Macs.
6. Add each saved file to `documents/sources.csv` with its own `file:` path as the source, to `documents/summaries.csv` with a title, a summary and `true`, and add a `fact,path` row to `documents/fact-links.csv` for each fact it proves.

## Texts

Rows are single messages. Read them as conversations, grouped by `handle`. Record a fact only when the conversation states one. Save the conversation excerpt that proves it as `documents/archive/texts/<year>/<YYYY-MM-DD>_<handle-slug>.txt`, cite it as `file:<path>`, and list it in `documents/sources.csv` and `documents/summaries.csv`.

## Calendar events

Add one fact per new event with the title copied exactly. Use `source: calendar:<calendar name>`. Leave out events titled Busy or Free. A repeating event is one fact per series: when the same title, time and calendar already have a fact whose `value` starts with `repeats on`, add the new dates to that value instead of adding a row. `kb/recurring.py` folds any repeats left over.

## Canvas

`canvas.jsonl` holds what changed in Canvas for each student in `household.toml`: assignments (due date, score, grade, missing, late), course announcements, and Canvas inbox messages.

- Canvas and Infinite Campus times are UTC. Use `due_local` (the household's time zone) for the fact `date`, `due` and `time`, and convert any other UTC time before you write it.
- Add a fact for each graded assignment (score out of points, the grade), each missing or late assignment, and each assignment with a due date today or later. Use domain `school`, the student as person, the course as entity, and `source: canvas:<student>:<kind>:<id>`.
- Update a fact you added earlier for the same Canvas item instead of adding a second one: search for its source with `bin/kb sql "select id from facts where source = 'canvas:...'"` and edit that row in `facts/<year>.csv`.
- A submitted assignment lists `saved_files`: the student's own work as Canvas holds it, with its text in `<file>.txt`. Read it. Archive it as `documents/archive/school/<year>/<YYYY-MM-DD>_<student>_<course-slug>_<assignment-slug>.<ext>` and link it to the assignment's fact. `submitted_text` holds typed answers; `submitted_link` is a Google Doc that Canvas does not copy, so record the link in the fact's value.
- A `course` row points to a snapshot of one course: its syllabus and its module outline, written when either changed. Archive it as `documents/archive/school/<year>/canvas/<student>-<course-slug>.md`, replacing the earlier copy. Record facts for the teacher's name, room, office hours and email, the grading weights, the late-work, make-up and retest rules, and the unit list. Update those facts when a later snapshot changes them.
- Read each announcement and message in full. Record dates, deadlines, events and anything a parent must act on.

## Jev labels

Each mail row carries `jev` (domain, subtype, confidence, and health, child and money flags) and `record` (whether it holds an order, bill or payment). Read health, child, money and record rows first, and give them the closest reading. Jev sets the reading order only: read every row, whatever its label. Copy Jev's domain into the fact only after the mail confirms it.

## Infinite Campus

`campus.jsonl` holds what changed in Infinite Campus, the school's official gradebook, for each student in `household.toml`: `grade` rows (term percent per course), `assignment` rows (score, points, category, missing, late, teacher comment, and `url`, the portal page for that assignment) and `attendance` rows. `campus/infinite-campus.json` is the full snapshot.

- Copy the snapshot to `documents/archive/school/<year>/infinite-campus/<YYYY-MM-DD>_infinite-campus.json` and cite it as `file:<path>`.
- Add or update one fact per term grade, per zero, missing, late or newly scored assignment, and per attendance event. Put the score in `value` and the portal `url` in the summary when a parent must act. Use `source: file:<archived snapshot path>`.
- Update the fact you added earlier for the same item instead of adding a second one: search `bin/kb facts "<assignment title>" --person <student>`, edit that row's summary, value and source.
- When Infinite Campus and Canvas disagree on the same assignment, record both in one fact.

## Slack

`slack.jsonl` holds new messages from the household Slack: `channel` (a channel name, or `DM <person>`), `time` in local time, `from`, `text`, `thread` (the parent message when it is a reply), `files` and `link`.

- Read every message. Add a fact for each date, plan, decision, purchase, appointment, task or anything a parent must act on. Skip chatter and reactions.
- Use `source: slack:<channel>:<ts>`, the sender's family name as person when the message is about them, and put the `link` in the fact's `link` column only when no record fits.
- A message that changes an earlier plan updates that plan's fact instead of adding a second one.

## Files

`documents.jsonl` lists new files in `~/Documents`. Copy each household file into the archive, read it, and record it the same way as a mail attachment.

## Appointments and events

A fact for a future appointment or event names who it is for, the provider or place in `entity`, and what it is for in `summary`, never only "New appointment booked". Put the start time in `time` as HH:MM. These facts appear in the Agent events calendar exactly as written.

Write each future-dated fact so it reads well as a calendar title: one event per fact, what it is in plain words (never only a course code or "11/13-11/20"), no status words such as "not yet submitted", and school calendar codes spelled out, such as "No school: teacher workday" for "Teacher Workday (W)", and no second event folded in.

## Rules

- `CLAUDE.md` rules apply: copy names, numbers and dates exactly; never write an account, card, policy or Social Security number outside `vault/` and `secrets/`; say unknown instead of guessing.
- Check for an existing fact before you add one: `bin/kb facts <words> --since <date>`.
- Map each new entity spelling in `organizations/names.csv`.
- Finish with `bin/kb check` (zero errors) and `bin/test`. Fix what fails.
- Do not commit or push. The worker does that after checking your work.
- Last, write `inbox/<date>/REVIEWED.md`: how many mails, texts, events and files you read, how many facts you added, and how many items you skipped and why. The worker moves the collector forward only when this file exists. If you could not read something, leave the file out and say why, so the next run retries.
