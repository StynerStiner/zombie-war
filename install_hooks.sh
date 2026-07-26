#!/usr/bin/env bash
#
# install_hooks.sh
# ================
# Installs a git hook that deploys Zombie War to Vercel every time you push.
#
#     bash install_hooks.sh
#
# After this, your normal workflow is just:
#
#     git add -A && git commit -m "..." && git push
#
# ...and the live site updates on its own. No Vercel/GitHub connection and no
# access tokens are involved: the hook simply runs the Vercel CLI on your
# machine, which is already logged in.
#
# To stop it:   rm .git/hooks/pre-push
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="$REPO_ROOT/.git/hooks/pre-push"

if [ ! -d "$REPO_ROOT/.git" ]; then
    echo "ERROR: $REPO_ROOT is not a git repository." >&2
    exit 1
fi

cat > "$HOOK" <<'HOOK_BODY'
#!/usr/bin/env bash
# Installed by install_hooks.sh - deploys to Vercel on every push.
# Delete this file to turn it off.
set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

if ! command -v vercel >/dev/null 2>&1; then
    echo "pre-push: vercel CLI not found, skipping deploy." >&2
    exit 0        # never block the push itself
fi

echo ""
echo "==> pushing to Vercel (production)…"
# Vercel builds the WebAssembly bundle itself: see vercel.json.
if vercel deploy --prod --yes >/tmp/zw-deploy.log 2>&1; then
    URL=$(grep -Eo 'https://[a-zA-Z0-9.-]+\.vercel\.app' /tmp/zw-deploy.log | tail -1)
    CODE=$(curl -s -o /dev/null -w '%{http_code}' https://zombie-war-web.vercel.app/ || echo "???")
    echo "==> deployed: ${URL:-(url not captured)}"
    echo "==> https://zombie-war-web.vercel.app  ->  HTTP $CODE"
else
    echo "==> DEPLOY FAILED. Last lines of the log:" >&2
    tail -15 /tmp/zw-deploy.log >&2
    echo "==> (your git push still went through)" >&2
fi
echo ""
exit 0            # a failed deploy must not block the git push
HOOK_BODY

chmod +x "$HOOK"
echo "Installed: $HOOK"
echo "Every 'git push' from this folder will now deploy to Vercel."
echo "Turn it off with:  rm .git/hooks/pre-push"
