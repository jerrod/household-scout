# Put due dates and amounts on every bill

Read `CLAUDE.md` first. `inbox/task-bills/facts.jsonl` lists every bill, statement, invoice, autopay and payment fact since the start date the task names, with the mails on this Mac from the same sender within a day of the fact saved under `inbox/task-bills/mail/<id>/`. A row can list more than one candidate mail: use the one that matches the fact: `body.txt` and the attachments, with `<file>.txt` text next to each PDF.

For every row:

1. Read the whole `body.txt` and every attachment.
2. When the mail states a payment due date, set the fact's `due` to it (YYYY-MM-DD). When it states an amount due or a minimum payment, set `amount` to the amount due and put the minimum in `value`.
3. When the mail says the bill is paid automatically, say "autopay" in the summary.
4. Change the fact's `source` from `mail:<id>` to `file:<path>` of the matching mail after you archive its `.eml` under `documents/archive/<category>/<year>/`, because Mail ids differ between Macs.
5. Rewrite the summary so it reads well as a calendar title: who is billed, what, and the amount, such as "City Power & Light electric bill $142.18, autopay". Never write an account or card number.
6. When a mail only says a statement is ready and holds no due date or amount, leave `due` empty and say so in the report.

Then list each biller that sends a bill every month, with its usual due day and whether it is autopay, in `expenses/bills.md` (frontmatter not needed). Write one table row per biller. Use only what the mails state.

Edit fact rows in `facts/<year>.csv` in place. Never change an `id`. Finish with `bin/kb check` (zero errors) and `bin/test`. Write `inbox/task-bills/REVIEWED.md` last: rows read, due dates set, amounts set, mails with neither.
