#!/usr/bin/env bash
# One-time Claude Code setup for this machine. Run from Git Bash:
#   bash setup-claude.sh
set -e
export PATH="$HOME/.local/bin:$PATH"

echo "1/3 Claude Code"
if command -v claude >/dev/null 2>&1; then
  echo "  already installed: $(claude --version)"
else
  powershell -NoProfile -Command "irm https://claude.ai/install.ps1 | iex"
  grep -q '.local/bin' ~/.bashrc 2>/dev/null || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
  claude --version
fi

echo "2/3 frontend-design skill (all projects)"
mkdir -p ~/.claude/skills/frontend-design
curl -fsSL -o ~/.claude/skills/frontend-design/SKILL.md \
  https://raw.githubusercontent.com/anthropics/skills/main/skills/frontend-design/SKILL.md
head -2 ~/.claude/skills/frontend-design/SKILL.md | tail -1

echo "3/3 Playwright MCP (all projects)"
if ! command -v npx >/dev/null 2>&1; then
  echo "  npx not found: install Node.js LTS from nodejs.org, then rerun this script"; exit 1
fi
if claude mcp get playwright >/dev/null 2>&1; then
  echo "  already added"
else
  claude mcp add --scope user playwright -- npx @playwright/mcp@latest
fi

echo "Done. Open a new Git Bash window, cd into this repo, and run: claude"
