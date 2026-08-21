"""ewsctl: manage Exchange server-side state over EWS.

Today that means inbox rules — the ones clients like macOS Mail only fake
locally. Accounts live in ~/.config/ewsctl/config.toml:

    [accounts.work]
    server = "mail.example.com"          # EWS host
    email = "user@example.com"
    username = "ntlm-login"              # or DOMAIN\\login
    password_cmd = "pass show mail/work" # first line = password

The first account is the default; pick another with -a NAME.
"""

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import NoReturn

from exchangelib import DELEGATE, NTLM, Account, Configuration, Credentials
from exchangelib.folders import Folder
from exchangelib.properties import Actions, Conditions, Rule

CONFIG = Path.home() / ".config/ewsctl/config.toml"


def die(msg) -> NoReturn:
    print(f"ewsctl: {msg}", file=sys.stderr)
    sys.exit(1)


def load_account(name):
    if not CONFIG.exists():
        die(f"no config at {CONFIG} (see module docstring for the format)")
    accounts = tomllib.loads(CONFIG.read_text()).get("accounts", {})
    if not accounts:
        die("no [accounts.*] sections in config")
    if name is None:
        name = next(iter(accounts))
    if name not in accounts:
        die(f"unknown account '{name}' (have: {', '.join(accounts)})")
    acc = accounts[name]
    password = subprocess.run(
        acc["password_cmd"], shell=True, capture_output=True, text=True, check=True
    ).stdout.splitlines()[0]
    config = Configuration(
        server=acc["server"],
        credentials=Credentials(acc.get("username", acc["email"]), password),
        auth_type=NTLM,
    )
    return Account(
        primary_smtp_address=acc["email"],
        config=config,
        autodiscover=False,
        access_type=DELEGATE,
    )


def fmt_set(container):
    """One-line summary of a Conditions/Actions/Exceptions object."""
    if container is None:
        return "-"
    parts = []
    for f in container.FIELDS:
        v = getattr(container, f.name, None)
        # no `in (None, False, [])`: exchangelib property __eq__ chokes on lists
        if v is None or v is False or (isinstance(v, (list, tuple)) and not v):
            continue
        if f.name == "move_to_folder" or f.name == "copy_to_folder":
            v = getattr(v, "display_name", None) or getattr(v, "id", v)
        parts.append(f"{f.name}={v}")
    return ", ".join(parts) or "-"


def find_rule(account, name):
    for r in account.rules:
        if r.display_name == name:
            return r
    die(f"no rule named '{name}'")


def find_folder(account, name):
    for f in account.msg_folder_root.walk():
        if f.name == name:
            return f
    die(f"no folder named '{name}' in the mailbox")


def cmd_list(account, args):
    for r in sorted(account.rules, key=lambda r: r.priority or 0):
        flags = "" if r.is_enabled else " [disabled]"
        flags += " [ERROR]" if r.is_in_error else ""
        print(f"{r.priority:>3}  {r.display_name}{flags}")
        if args.verbose:
            print(f"     if:   {fmt_set(r.conditions)}")
            if r.exceptions and fmt_set(r.exceptions) != "-":
                print(f"     not:  {fmt_set(r.exceptions)}")
            print(f"     then: {fmt_set(r.actions)}")


def cmd_show(account, args):
    r = find_rule(account, args.name)
    print(f"name:     {r.display_name}")
    print(f"priority: {r.priority}")
    print(f"enabled:  {r.is_enabled}")
    print(f"in_error: {r.is_in_error}")
    print(f"if:       {fmt_set(r.conditions)}")
    print(f"not:      {fmt_set(r.exceptions)}")
    print(f"then:     {fmt_set(r.actions)}")


def build_conditions(args):
    kw = {}
    if args.from_contains:
        kw["contains_sender_strings"] = args.from_contains
    if args.subject_contains:
        kw["contains_subject_strings"] = args.subject_contains
    if not kw:
        die("give at least one condition (--from-contains / --subject-contains)")
    return Conditions(**kw)


def build_actions(args, account):
    kw = {}
    if args.move_to:
        kw["move_to_folder"] = find_folder(account, args.move_to)
    if args.delete:
        kw["delete"] = True
    if args.mark_read:
        kw["mark_as_read"] = True
    if args.stop:
        kw["stop_processing_rules"] = True
    if not kw:
        die("give at least one action (--move-to / --delete / --mark-read)")
    return Actions(**kw)


def cmd_add(account, args):
    rule = Rule(
        display_name=args.name,
        priority=args.priority,
        is_enabled=True,
        conditions=build_conditions(args),
        actions=build_actions(args, account),
    )
    account.create_rule(rule)
    print(f"created rule '{args.name}' (id {rule.id})")


def cmd_rm(account, args):
    account.delete_rule(find_rule(account, args.name))
    print(f"deleted rule '{args.name}'")


def cmd_folders_list(account, args):
    root = account.msg_folder_root
    for f in sorted(root.walk(), key=lambda f: f.absolute):
        print(f.absolute.removeprefix(root.absolute + "/"))


def cmd_folders_add(account, args):
    parent = (
        find_folder(account, args.parent) if args.parent else account.msg_folder_root
    )
    Folder(parent=parent, name=args.name).save()
    print(f"created folder '{args.name}' under '{parent.name}'")


def cmd_folders_rm(account, args):
    f = find_folder(account, args.name)
    if f.total_count:
        die(f"folder '{args.name}' still holds {f.total_count} items; empty it first")
    f.delete()
    print(f"deleted folder '{args.name}'")


def cmd_toggle(account, args, enabled):
    r = find_rule(account, args.name)
    r.is_enabled = enabled
    account.set_rule(r)
    print(f"rule '{args.name}' {'enabled' if enabled else 'disabled'}")


def main():
    p = argparse.ArgumentParser(prog="ewsctl", description=__doc__)
    p.add_argument("-a", "--account", help="account name from the config")
    sub = p.add_subparsers(dest="cmd", required=True)

    rules = sub.add_parser("rules", help="server-side inbox rules")
    rsub = rules.add_subparsers(dest="rcmd", required=True)

    rl = rsub.add_parser("list", help="list rules")
    rl.add_argument("-v", "--verbose", action="store_true")

    rs = rsub.add_parser("show", help="show one rule")
    rs.add_argument("name")

    ra = rsub.add_parser("add", help="create a rule")
    ra.add_argument("name")
    ra.add_argument(
        "--from-contains",
        action="append",
        default=[],
        metavar="STR",
        help="sender matches substring (repeatable)",
    )
    ra.add_argument(
        "--subject-contains",
        action="append",
        default=[],
        metavar="STR",
        help="subject contains substring (repeatable)",
    )
    ra.add_argument("--move-to", metavar="FOLDER", help="move to folder by name")
    ra.add_argument("--delete", action="store_true", help="move to Deleted Items")
    ra.add_argument("--mark-read", action="store_true")
    ra.add_argument("--stop", action="store_true", help="stop processing more rules")
    ra.add_argument("--priority", type=int, default=1)

    rr = rsub.add_parser("rm", help="delete a rule")
    rr.add_argument("name")

    re_ = rsub.add_parser("enable", help="enable a rule")
    re_.add_argument("name")
    rd = rsub.add_parser("disable", help="disable a rule")
    rd.add_argument("name")

    folders = sub.add_parser("folders", help="mailbox folders")
    fsub = folders.add_subparsers(dest="fcmd", required=True)
    fsub.add_parser("list", help="list folders")
    fa = fsub.add_parser("add", help="create a folder")
    fa.add_argument("name")
    fa.add_argument("--parent", help="parent folder name (default: mailbox root)")
    fr = fsub.add_parser("rm", help="delete an empty folder")
    fr.add_argument("name")

    args = p.parse_args()
    account = load_account(args.account)

    if args.cmd == "folders":
        match args.fcmd:
            case "list":
                cmd_folders_list(account, args)
            case "add":
                cmd_folders_add(account, args)
            case "rm":
                cmd_folders_rm(account, args)
        return

    match args.rcmd:
        case "list":
            cmd_list(account, args)
        case "show":
            cmd_show(account, args)
        case "add":
            cmd_add(account, args)
        case "rm":
            cmd_rm(account, args)
        case "enable":
            cmd_toggle(account, args, True)
        case "disable":
            cmd_toggle(account, args, False)


if __name__ == "__main__":
    main()
