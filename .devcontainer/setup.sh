#!/usr/bin/env bash
# .devcontainer/setup.sh — runs once inside the container after creation.
# Safe to re-run; all steps are idempotent.
set -euo pipefail

# ── System packages ───────────────────────────────────────────────────────────
echo "→ Installing system packages (vim)…"
sudo apt-get update -qq && sudo apt-get install -y --no-install-recommends vim

# ── Dev tools ─────────────────────────────────────────────────────────────────
echo "→ Installing dev tools (ruff, pytest)…"
pip install --quiet ruff pytest

# ── SSH keys ──────────────────────────────────────────────────────────────────
# .ssh is staged at /tmp/host-ssh (bind-mounted read-only from the host).
# We copy it to ~/.ssh with the permissions SSH requires (700/600).
# Contributors without an .ssh directory simply skip this step.
echo "→ Configuring SSH…"
if [ -d /tmp/host-ssh ] && [ -n "$(ls -A /tmp/host-ssh 2>/dev/null)" ]; then
    mkdir -p ~/.ssh
    cp -rp /tmp/host-ssh/. ~/.ssh/
    chmod 700 ~/.ssh
    find ~/.ssh -type f -exec chmod 600 {} \;
    echo "  SSH keys installed."
else
    echo "  No SSH keys found on host — skipping."
fi

# ── SSH config sanitisation ──────────────────────────────────────────────────
# The host's ~/.ssh/config may use options that this container's OpenSSH does
# not know yet (e.g. `WarnWeakCrypto` on older/newer mismatches). ssh aborts on
# any unknown keyword, which breaks git-over-SSH. Use ssh's own error output to
# find each offending line and comment it out, repeating until the file parses.
if [ -f ~/.ssh/config ]; then
    echo "→ Sanitising ~/.ssh/config for this OpenSSH version…"
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        ssh_err=$(ssh -G github.com 2>&1 >/dev/null || true)
        bad_line=$(printf '%s\n' "$ssh_err" \
            | sed -n 's|^.*\.ssh/config: line \([0-9]\{1,\}\): Bad configuration option:.*|\1|p' \
            | head -1)
        if [ -z "$bad_line" ]; then
            echo "  Config parses cleanly."
            break
        fi
        echo "  Commenting out unsupported option on line $bad_line."
        sed -i "${bad_line}s|^|# Unsupported by container OpenSSH: |" ~/.ssh/config
    done
fi

# ── Host credentials (git / ssh / gh) ────────────────────────────────────────
# The host's ~/.gitconfig, ~/.ssh and ~/.config/gh are bind-mounted into the
# container user's home so the host's `git` and `gh` logins are reused as-is —
# no copy step and no re-authentication. A bind mount keeps the host uid, which
# usually differs from the container user, so grant the container user
# ownership of the mounted paths (otherwise a 0600 hosts.yml/key is unreadable
# and gh/ssh fail).
echo "→ Fixing ownership of mounted host config…"
for path in ~/.gitconfig ~/.ssh ~/.config/gh; do
    if [ -e "$path" ]; then
        sudo chown -R "$(id -u):$(id -g)" "$path"
    fi
done
echo "  Done."

# ── .profile (SSH signing env vars etc.) ──────────────────────────────────────
# The host .profile is mounted to ~/.profile-host.
# VS Code terminals start as non-login interactive shells, so ~/.profile is
# not sourced automatically.  We add a one-time source line to both rc files.
echo "→ Wiring ~/.profile-host into shell init files…"
if [ -s ~/.profile-host ]; then
    for rc in ~/.bashrc ~/.zshrc; do
        if [ -f "$rc" ] && ! grep -q 'profile-host' "$rc" 2>/dev/null; then
            echo '' >> "$rc"
            echo '# Sourced by devcontainer setup — host .profile (SSH signing, etc.)' >> "$rc"
            echo 'source ~/.profile-host 2>/dev/null || true' >> "$rc"
        fi
    done
    echo "  Done."
else
    echo "  ~/.profile-host is empty — skipping."
fi

echo ""
echo "✅ Container setup complete."
echo "   Workspace : /workspace"
echo "   Python    : $(python3 --version)"
echo "   ruff      : $(ruff --version)"
echo "   pytest    : $(pytest --version 2>&1 | head -1)"
echo "   gh        : $(gh --version 2>&1 | head -1)"
echo "   gh auth   : $(gh auth status 2>&1 | head -1 || true)"
