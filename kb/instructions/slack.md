# Read one chunk of the household Slack

Read `CLAUDE.md` first. `inbox/task-slack/chunk.md` holds one chunk of Slack history: whole conversations, each a run of messages with no gap over three hours, with thread replies (marked `↳`) under their parent. Read every conversation as a whole before you write anything, because a plan, a change and its outcome often span several messages.

Each person's Slack names are listed under `aliases` in `household.toml`.

For every conversation in the chunk:

1. Add a fact for each household date, plan, decision, purchase, appointment, trip, school or health event, vendor, repair, price, account change, or task. One fact per thing, not per message. When later messages change a plan, record the final plan and its date.
2. Date the fact by the event when the messages state one, otherwise by the message. Use `source: slack:<channel>:<ts>` with the `ts` of the message that states the fact, plus a second `slack:` source when the outcome sits in another message.
3. Skip chatter, jokes, reactions and greetings. Never quote a private remark that holds no household fact.
4. Before you add a fact, search for it with `bin/kb facts "<words>" --since <date>`. When the knowledgebase already holds it from mail or texts, add the `slack:` source to that row instead of a second row.

For every `file:` line with a saved path:

1. Open the file. Read every page of a PDF, look at every image, read `<file>.txt` when it exists.
2. Add its title and summary to `documents/summaries.csv` and its path and `slack:<channel>:<ts>` source to `documents/sources.csv`.
3. Add facts from it, and link each fact to the file in `documents/fact-links.csv`.
4. Move a file that holds medical, identity, finance or license details to the matching folder under `vault/archive/`, and update its paths.

`documents/slack-links.csv` catalogs every shared URL. For a URL in this chunk that names a household vendor, product, listing, booking, school page or document, record the fact it supports with the URL in the fact's summary.

Never write a password, an account number or a card number outside `vault/` and `secrets/`. Edit fact rows in `facts/<year>.csv` in place, and never change an `id`. Finish with `bin/kb check` (zero errors) and `bin/test`. Write `inbox/task-slack/REVIEWED.md` last: the chunk's file name, conversations read, facts added, facts updated, files read, and files you could not open.
