# Laptop ⇄ Desktop SSH Compute Offload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Passwordless bidirectional SSH between laptop (`aaron-yoga-linux`) and desktop (`linux.local` / 192.168.1.45, user `aaron`), plus an `on-desktop` helper that runs commands in the desktop's repo clone.

**Architecture:** Plain OpenSSH with ed25519 key auth. mDNS hostnames (`linux.local`, `aaron-yoga-linux.local`) instead of IPs so DHCP changes don't break anything. SSH config aliases `desktop` (on laptop) and `laptop` (on desktop). No shared filesystem — the desktop has its own repo clone; offload = `git pull` + build there.

**Tech Stack:** OpenSSH, firewalld/ufw, avahi (already working), bash.

## Global Constraints

- Desktop user is `aaron`; laptop user is `aaron`.
- Use mDNS names in config, never hardcoded IPs (spec: survives DHCP changes).
- `sshd` must be *enabled* (survives reboot), not just started (spec success criterion).
- Two steps are inherently interactive/manual and cannot be automated from the laptop: enabling sshd on the desktop (Task 1) and the one-time password entry for `ssh-copy-id` (Task 2). Everything else runs from the laptop.
- This is machine setup, not repo code — "tests" are the verification commands in each task. No unit tests.

---

### Task 1: Enable sshd on the desktop (manual, user at the desktop)

**Files:** none in this repo (desktop system config).

**Interfaces:**
- Produces: TCP port 22 open on `linux.local`, sshd enabled at boot.

- [ ] **Step 1: User runs on the desktop** (ask the user to run this at the desktop, or paste it to them; distro unknown, so both variants):

```bash
# systemd distros (Fedora/Arch/openSUSE — service name "sshd"):
sudo systemctl enable --now sshd
# Debian/Ubuntu (service name "ssh"):
sudo systemctl enable --now ssh

# Firewall — run whichever tool exists:
sudo firewall-cmd --permanent --add-service=ssh && sudo firewall-cmd --reload   # firewalld
sudo ufw allow ssh                                                              # ufw
# (If neither is installed, there is likely no host firewall — skip.)
```

- [ ] **Step 2: Verify from the laptop**

Run: `nc -zv -w 3 linux.local 22`
Expected: `Connected to ... :22` (previously this timed out).
If it still times out, the desktop firewall is still blocking — re-check Step 1 firewall lines.

### Task 2: Laptop → desktop key auth + `desktop` alias

**Files:**
- Modify: `~/.ssh/config` (laptop) — append a `Host desktop` block.

**Interfaces:**
- Consumes: open port 22 on `linux.local` (Task 1).
- Produces: `ssh desktop <cmd>` works without password; later tasks use exactly the alias name `desktop`.

- [ ] **Step 1: Append the alias to laptop `~/.ssh/config`**

```
Host desktop
    HostName linux.local
    User aaron
    IdentityFile ~/.ssh/id_ed25519
```

- [ ] **Step 2: Install the laptop's existing key on the desktop (interactive — ONE password entry)**

The user runs in the Claude Code prompt (the `!` prefix runs it interactively in-session):

```
! ssh-copy-id -o StrictHostKeyChecking=accept-new desktop
```

Expected: prompts for `aaron@linux.local`'s password once, then `Number of key(s) added: 1`.

- [ ] **Step 3: Verify passwordless**

Run: `ssh -o BatchMode=yes desktop true && echo OK`
Expected: `OK` (no password prompt; BatchMode makes any prompt a hard failure).

- [ ] **Step 4: Verify sshd is enabled on the desktop (reboot survival)**

Run: `ssh desktop 'systemctl is-enabled sshd 2>/dev/null || systemctl is-enabled ssh'`
Expected: `enabled`. If `disabled`, run `ssh -t desktop 'sudo systemctl enable sshd || sudo systemctl enable ssh'` (interactive sudo — use `!` prefix).

### Task 3: Enable sshd on the laptop

**Files:** none in this repo (laptop system config).

**Interfaces:**
- Produces: TCP port 22 open on `aaron-yoga-linux.local`, sshd enabled at boot.

- [ ] **Step 1: Enable and open firewall (Fedora: firewalld; needs sudo — run interactively via `!` if sudo prompts)**

```bash
sudo systemctl enable --now sshd
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --reload
```

- [ ] **Step 2: Verify locally**

Run: `systemctl is-enabled sshd && systemctl is-active sshd && nc -zv -w 3 localhost 22`
Expected: `enabled`, `active`, `Connected`.

- [ ] **Step 3: Verify reachable from the LAN side (from the desktop, over the Task-2 link)**

Run: `ssh desktop 'nc -zv -w 3 aaron-yoga-linux.local 22 2>&1 || true'`
Expected: output contains `Connected`. (If `nc` is missing on the desktop, use `ssh desktop 'timeout 3 bash -c "</dev/tcp/aaron-yoga-linux.local/22" && echo Connected'`.)

### Task 4: Desktop → laptop key auth + `laptop` alias

**Files:**
- Modify: `~/.ssh/authorized_keys` (laptop) — append desktop's public key.
- Modify: desktop `~/.ssh/config` — append a `Host laptop` block (written over SSH).

**Interfaces:**
- Consumes: `desktop` alias (Task 2), laptop sshd (Task 3).
- Produces: `ssh laptop <cmd>` works from the desktop without password.

- [ ] **Step 1: Ensure the desktop has an ed25519 key (create only if absent)**

```bash
ssh desktop '[ -f ~/.ssh/id_ed25519 ] || ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519'
```

- [ ] **Step 2: Authorize it on the laptop (append, dedup, correct perms)**

```bash
PUB=$(ssh desktop 'cat ~/.ssh/id_ed25519.pub')
mkdir -p ~/.ssh && touch ~/.ssh/authorized_keys
grep -qxF "$PUB" ~/.ssh/authorized_keys || echo "$PUB" >> ~/.ssh/authorized_keys
chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys
```

- [ ] **Step 3: Add the `laptop` alias on the desktop**

```bash
ssh desktop 'mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/config && chmod 600 ~/.ssh/config
grep -q "^Host laptop$" ~/.ssh/config || cat >> ~/.ssh/config <<EOF

Host laptop
    HostName aaron-yoga-linux.local
    User aaron
    IdentityFile ~/.ssh/id_ed25519
EOF'
```

- [ ] **Step 4: Verify passwordless desktop → laptop**

Run: `ssh desktop 'ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new laptop true && echo OK'`
Expected: `OK`.

### Task 5: `on-desktop` helper + end-to-end verification

**Files:**
- Create: `~/.local/bin/on-desktop` (laptop; `~/.local/bin` is already on PATH).

**Interfaces:**
- Consumes: `desktop` alias (Task 2).
- Produces: `on-desktop <cmd...>` runs `<cmd...>` inside the desktop's repo clone; `on-desktop` with no args opens an interactive shell there.

- [ ] **Step 1: Locate the repo clone on the desktop**

Run: `ssh desktop 'for d in ~/Projects/personal/de-trains-speed-map ~/Projects/de-trains-speed-map ~/de-trains-speed-map; do [ -d "$d/.git" ] && echo "$d" && exit; done; find ~ -maxdepth 4 -type d -name de-trains-speed-map 2>/dev/null | head -1'`
Expected: one absolute path. Use it as `REPO_PATH` in Step 2. If empty, ask the user where the clone lives.

- [ ] **Step 2: Write the helper (substitute the real `REPO_PATH`)**

```bash
#!/usr/bin/env bash
# Run a command in the de-trains-speed-map clone on the desktop.
# Usage: on-desktop <cmd...>   |   on-desktop   (interactive shell there)
set -euo pipefail
REPO_PATH="REPO_PATH_FROM_STEP_1"
if [ $# -eq 0 ]; then
    exec ssh -t desktop "cd '$REPO_PATH' && exec \$SHELL -l"
fi
exec ssh desktop "cd '$REPO_PATH' && $*"
```

Then: `chmod +x ~/.local/bin/on-desktop`

- [ ] **Step 3: Verify the helper (spec success criterion)**

Run: `on-desktop git status | head -3`
Expected: branch/status output from the desktop clone, no password prompt.

- [ ] **Step 4: Verify the full success-criteria list from the spec**

```bash
ssh -o BatchMode=yes desktop true && echo "laptop→desktop OK"
ssh desktop 'ssh -o BatchMode=yes laptop true && echo "desktop→laptop OK"'
ssh desktop 'systemctl is-enabled sshd 2>/dev/null || systemctl is-enabled ssh'
systemctl is-enabled sshd
```

Expected: both `OK` lines, `enabled` twice.

- [ ] **Step 5: Commit the plan checkboxes + any doc updates**

```bash
git add docs/superpowers/plans/2026-07-16-laptop-desktop-ssh.md
git commit -m "docs: laptop⇄desktop SSH offload plan executed"
```
