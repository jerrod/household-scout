# Extract health and pet facts from the vault

Read `CLAUDE.md` first. `inbox/task-health/files.txt` lists the files for this run, one path per line. Open every one of them now, even when `documents/summaries.csv` already has a title for it: a summary is not a source of facts. The files stay where they are. Read each one in full: PDFs through `pdftotext`, images with the Read tool (convert HEIC with `sips -s format jpeg <file> --out /tmp/<name>.jpg`).

Add facts with `bin/kb add` for every person and pet in `household.toml`:

- Current medications with dose and prescriber, and the date the source states them.
- Allergies and diagnosed conditions.
- Vaccines and the date given, and the next dose due when the source states it (put it in `due`).
- Checkups, cleanings and vet visits: the date, the provider, and the next visit due when stated.
- Health insurance and pet insurance plan names and carriers. Never write a member, group, policy or account number: write "in the vault" instead.
- Primary doctor, dentist, orthodontist and vet for each person or pet.

For a person or pet with `status = "passed"` in `household.toml`, record their history but never a next visit or a reminder. Use domain `health` for people and `pets` for pets. Cite `file:<vault path>`. Check for an existing fact first with `bin/kb facts <words> --person <name>`; update it instead of adding a second one. Add each new document to `documents/summaries.csv` and each fact to `documents/fact-links.csv`.

Finish with `bin/kb check` (zero errors) and `bin/test`. Write `inbox/task-health/REVIEWED.md` last: one line per path in `files.txt` with the number of facts it gave, facts added per person, and every file you could not read. The number of lines must equal the number of paths.
