#!/bin/bash
# Install Python dependencies in Claude Code cloud sessions (web / mobile).
set -euo pipefail
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi
cd "$CLAUDE_PROJECT_DIR"
pip install -q -r requirements.txt
