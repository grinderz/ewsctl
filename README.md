# ewsctl

CLI for Exchange over EWS (exchangelib): server-side inbox rules today,
room for out-of-office and friends later. Built because client-side rules
(macOS Mail, Evolution filters) only run while that client is open —
server rules filter before delivery, for every client at once.

## Setup

```sh
uv tool install --editable ~/src/personal/ewsctl
```

Config (kept out of the repo), `~/.config/ewsctl/config.toml`:

```toml
[accounts.work]
server = "mail.example.com"           # EWS host
email = "user@example.com"
username = "ntlm-login"               # or DOMAIN\login
password_cmd = "pass show mail/work"  # any command; first line = password
```

First account is the default, pick others with `-a NAME`.

## Usage

```sh
ewsctl rules list -v
ewsctl rules show "noisy-sender"
ewsctl rules add "noisy-sender" --from-contains noisy --move-to robots@example.com --stop
ewsctl rules rm "noisy-sender"
ewsctl rules disable "some rule"
```

Auth is NTLM (what on-prem Exchange usually insists on). Requires the
CalDAV/EWS endpoint to be reachable directly — no davmail in between.
