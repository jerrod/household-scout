# Name the card that paid each bill and receipt

Read `CLAUDE.md` first, then `vault/finance/cards.md`, the map from each card's last four digits to its name. `inbox/task-payments/facts.jsonl` lists this run's bill, receipt, invoice, autopay, payment, subscription and order facts, with matching mail saved under `inbox/task-payments/mail/<id>/`. A fact whose source is `file:<path>` points to its file directly.

For every row:

1. Read the mail body or the file, and every attachment.
2. When it names the card or account that paid or will pay, look the last four digits up in `vault/finance/cards.md` and add `; paid with <card name>` to the summary. Use the bank account's plain name the same way for a bank draft, such as "paid with the joint checking".
3. When the card's digits are missing from the map, write `paid with a card not in the card map` and list the digits only in `inbox/task-payments/REVIEWED.md`, never in a fact.
4. When the source does not say how it was paid, leave the summary alone.
5. When the fact cites `mail:<id>`, archive the matching mail under `documents/archive/<category>/<year>/`, add it to `documents/sources.csv` and `documents/summaries.csv`, and change the source to `file:<path>`.

Never write card or account digits outside `vault/`. Edit fact rows in place and never change an `id`. Finish with `bin/kb check` (zero errors) and `bin/test`. Write `inbox/task-payments/REVIEWED.md` last: rows read, cards named, rows with no payment method, and any digits missing from the map.
