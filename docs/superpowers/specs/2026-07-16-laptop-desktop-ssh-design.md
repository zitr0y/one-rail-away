# Laptop ⇄ Desktop SSH for compute offload — Design

**Date:** 2026-07-16
**Status:** Approved (design discussed and accepted in session)

## Goal

Permanent, bidirectional, passwordless SSH between the laptop
(`aaron-yoga-linux`, Fedora) and the desktop (`linux`, 192.168.1.45, Linux,
user `aaron`), so dev rebuilds and occasional Claude Code sessions can run on
the desktop's faster hardware. LAN-only for now; must not conflict with adding
Tailscale later.

## Design

1. **Hostnames, not IPs.** Both machines advertise mDNS names
   (`linux.local`, `aaron-yoga-linux.local`). SSH config aliases point at
   those, so the setup survives DHCP address changes. Optional belt-and-braces:
   DHCP reservation for the desktop in the router (manual, not part of this
   work).
2. **Desktop sshd (one-time manual step).** User enables `sshd` and opens the
   firewall on the desktop (two commands, run at that machine).
3. **Laptop → desktop.** `Host desktop` alias in laptop `~/.ssh/config` →
   `linux.local`, user `aaron`, existing `id_ed25519` key. Key installed once
   via `ssh-copy-id` (single interactive password entry).
4. **Desktop → laptop.** Enable `sshd` + firewall on the laptop; generate an
   ed25519 key on the desktop, authorize it on the laptop; `Host laptop`
   alias in the desktop's `~/.ssh/config` → `aaron-yoga-linux.local`. All
   doable over SSH from the laptop once step 3 works.
5. **Offload workflow.** The repo is already cloned on the desktop (exact
   path located during setup and baked into the helper). Rebuilds:
   `ssh desktop 'cd <repo-path> && git pull && <build cmd>'`. Add a small
   `on-desktop` helper (script or fish abbreviation) on the laptop so it's one
   word. Remote Claude Code: `ssh -t desktop claude` (desktop has a separate
   Claude account available when the laptop account's tokens run out).

## Out of scope

- Tailscale (deferred; keys/aliases here carry over — later, install Tailscale
  and add its hostname as an additional alias or `Match` block).
- Moving the trains pipeline off the server (stays on aaronbussche.eu cron).
- Server involvement of any kind — this is laptop ⇄ desktop only.

## Success criteria

- `ssh desktop true` from the laptop: no password, exit 0.
- `ssh laptop true` from the desktop: no password, exit 0.
- `on-desktop git status` runs in the desktop's repo clone from the laptop.
- Both still work after a reboot of either machine (sshd enabled, not just
  started).

## Alternatives considered

- Hardcoded IPs: brittle vs. mDNS names.
- Tailscale now: user chose LAN-first, Tailscale later.
- sshfs/NFS shared repo: more moving parts than `git pull`; rejected (YAGNI).
