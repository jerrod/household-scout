---
name: household-setup
description: Set up a new household knowledgebase with household-scout. Use when someone asks to set up household-scout, start a household knowledgebase, or add a person, pet or source to one.
---

# Set up a household

1. Ask where the new knowledgebase goes. Run `bin/init-household <folder>` from the household-scout checkout.
2. Ask who lives in the house. Write each person to `household.toml` with a role: `parent`, `child` or `adult`. Write each pet with role `pet`.
3. Ask for the time zone. Ask which areas to track, and remove the areas the household doesn't need.
4. Ask which sources to read: Apple Mail or Gmail, Messages, Calendar, Documents, Canvas, Infinite Campus, Slack. Write only those under `[sources]`.
5. Ask each person whose messages Claude will read to agree first. Leave out every source someone hasn't agreed to.
6. Hand each sign-in to the person. Never ask for a password, and never type one. Tokens go in `~/.config/household-scout/`, readable only by the owner.
7. Ask the person to create a private GitHub repository. Add it as `origin`. Run `bin/kb-guard`, and stop if it fails.
8. Set up git-crypt for `vault/` and `secrets/`.
9. Copy `templates/launchd/*.plist` to `~/Library/LaunchAgents/`. Replace `REPLACE_WITH_REPOSITORY_PATH`. Ask before you load them.
10. Ask the person to grant Full Disk Access to `/bin/zsh` in System Settings.
11. Run `bin/kb build`, `bin/kb check` and `bin/test`. Report what passed.
