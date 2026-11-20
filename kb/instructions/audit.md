# Recheck facts that Jev reads differently

Read `CLAUDE.md` first. `inbox/task-audit/flags.jsonl` lists facts where Jev, a classifier, reads the fact's `domain` or `person` differently from the stored value with high confidence. Each row has `id`, `field`, `has` (the stored value), `jev` (Jev's reading), `confidence` and `summary`.

Jev is often right and sometimes wrong. Decide each row from the fact's source, never from Jev's label alone.

For every row:

1. Run `bin/kb source <id>` and read the mail, text or file behind the fact. For a `file:` source, open the file.
2. Decide the right value with the `CLAUDE.md` definitions. `person` names the family member the fact is about, `household` for the whole house, and `other` for anyone outside the family. `domain` is the most specific area that fits. Use `calendar` only when no other domain fits.
3. When the stored value is wrong, edit that row in `facts/<year>.csv`. Never change an `id`. Fix any other column the source shows is wrong too.
4. When the stored value is right, leave the row alone.

Finish with `bin/kb check` (zero errors) and `bin/test`. Write `inbox/task-audit/REVIEWED.md` last: rows read, rows changed by field, rows kept, and every row whose source you could not open.
