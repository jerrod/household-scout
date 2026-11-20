# Build the card map

Read `CLAUDE.md` first. Build `vault/finance/cards.md`: one table row per payment card the household uses, with the columns `name`, `issuer`, `network`, `last four`, `holder`, `autopay from`, `evidence`.

- `name` is the plain name people use, such as "Apple Card" or "the travel Visa". Never invent a name the sources do not support.
- Find each card in card statements, payment notices and receipts under `vault/archive/finance/`, and in facts: `bin/kb facts --domain finance --since 2025-01-01 --limit 400`. Read the files themselves, PDFs through `pdftotext`.
- Fill `last four` only from a statement, notice or receipt that prints it, and name that file in `evidence`.
- A card that has closed or been replaced gets a row too, with "closed" or "replaced by <name>" in `autopay from`.

`vault/` is encrypted, so the last four digits may live there and nowhere else. Never copy them into `facts/`, `documents/` or any other folder.

Finish with `bin/kb check` (zero errors) and `bin/test`. Write `inbox/task-cards/REVIEWED.md` last: the cards found, and every card you could not name.
