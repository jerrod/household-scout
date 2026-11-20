import argparse
import sys

from kb import commands, store
from kb.schema import DOMAINS, ENTITY_FOLDERS, PEOPLE


def parser():
    top = argparse.ArgumentParser(prog="kb", description="Query the household knowledgebase.")
    top.add_argument("--json", action="store_true", help="print JSON")
    sub = top.add_subparsers(dest="command", required=True)

    facts = sub.add_parser("facts", help="list dated facts, newest first")
    facts.add_argument("text", nargs="*")
    facts.add_argument("--person", choices=[p for p in PEOPLE if p])
    facts.add_argument("--domain", choices=DOMAINS)
    facts.add_argument("--kind")
    facts.add_argument("--org", help="organization id, such as westbrook-high-school")
    facts.add_argument("--since", help="YYYY-MM-DD")
    facts.add_argument("--until", help="YYYY-MM-DD")
    facts.add_argument("--limit", type=int, default=50)
    facts.add_argument("--oldest", action="store_true", help="oldest first")
    facts.set_defaults(run=commands.facts)

    find = sub.add_parser("find", help="search facts, records, documents, notes, ledger and unread mail")
    find.add_argument("text", nargs="+")
    find.add_argument("--limit", type=int, default=10)
    find.add_argument("--private", action="store_true", help="include vault file names")
    find.set_defaults(run=commands.find)

    show = sub.add_parser("show", help="print one record with its facts and links")
    show.add_argument("name", nargs="+")
    show.set_defaults(run=commands.show)

    org = sub.add_parser("org", help="print one organization with every fact, name and document tied to it")
    org.add_argument("name", nargs="+")
    org.add_argument("--limit", type=int, default=100)
    org.set_defaults(run=commands.org)

    links = sub.add_parser("links", help="print the typed links into and out of one record or organization")
    links.add_argument("name", nargs="+")
    links.set_defaults(run=commands.links)

    listing = sub.add_parser("list", help="list the records in one folder")
    listing.add_argument("folder", choices=list(ENTITY_FOLDERS))
    listing.add_argument("--fields", default="name,purchased,purchase_price,serial,owner", help="comma-separated frontmatter keys")
    listing.set_defaults(run=commands.listing)

    source = sub.add_parser("source", help="print the mail or text behind one fact")
    source.add_argument("id", help="fact id, such as F012345")
    source.add_argument("--limit", type=int, default=3000, help="characters of mail body")
    source.set_defaults(run=commands.source)

    events = sub.add_parser("calendar", help="print Calendar.app events with their original titles")
    events.add_argument("--since", default="", help="YYYY-MM-DD")
    events.set_defaults(run=commands.events)

    plan = sub.add_parser("week", help="print what each person has each day, with outings that need a driver")
    plan.add_argument("--days", type=int, default=7)
    plan.add_argument("--start", help="YYYY-MM-DD, default today")
    plan.add_argument("--person", choices=[p for p in PEOPLE if p])
    plan.set_defaults(run=commands.week)
    sql = sub.add_parser("sql", help="run one read-only SQL statement")
    sql.add_argument("statement")
    sql.set_defaults(run=commands.sql)

    audit = sub.add_parser("audit", help="list facts whose domain or person Jev reads differently, with high confidence")
    audit.add_argument("--since", default="")
    audit.add_argument("--field", choices=["domain", "person"])
    audit.set_defaults(run=commands.audit)
    sub.add_parser("stats", help="count everything").set_defaults(run=commands.stats)
    checks = sub.add_parser("check", help="report data problems; exit 1 on an error")
    checks.add_argument("--examples", type=int, default=3)
    checks.set_defaults(run=commands.checks)
    sub.add_parser("add", help="append facts from JSON lines on standard input").set_defaults(run=commands.add)
    page = sub.add_parser("site", help="write the browsable page to one HTML file")
    page.add_argument("out")
    page.set_defaults(run=commands.publish)
    letter = sub.add_parser("mail", help="print one mail from this Mac's Mail store, or save it and its attachments")
    letter.add_argument("id", type=int, help="the Mail row id on this Mac")
    letter.add_argument("--save", help="folder for the .eml file and the attachments")
    letter.add_argument("--limit", type=int, default=20000)
    letter.set_defaults(run=commands.mail_command)

    queue = sub.add_parser("intake", help="pull the review queue from the server, or accept or reject one item")
    queue.add_argument("action", choices=["pull", "accepted", "rejected"])
    queue.add_argument("id", nargs="?", type=int)
    queue.add_argument("--outcome", default="", help="the fact ids added, or the reason for a rejection")
    queue.add_argument("--day", default=__import__("datetime").date.today().isoformat())
    queue.set_defaults(run=commands.intake)
    sub.add_parser("build", help="rebuild the index").set_defaults(run=commands.build)
    return top


def main(argv=None):
    args = parser().parse_args(argv)
    con = store.connect()
    try:
        args.run(con, args)
    except (LookupError, ValueError) as error:
        sys.exit(str(error))
