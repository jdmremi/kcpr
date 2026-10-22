#!/bin/bash

set -euo pipefail

# ===== CONFIGURATION =====
REPO_DIR="/root/kcpr"
BRANCH="data"
LOG_FILE="$HOME/csv_auto_push.log"

# ===== NAVIGATE TO REPO =====
cd "$REPO_DIR"

# ===== STAGE CHANGED CSV FILES =====
# Includes new, modified, and deleted CSV files
git add -A -- ':(glob)**/*.csv'

# ===== CHECK FOR CSV CHANGES =====
if git diff --cached --quiet -- ':(glob)**/*.csv'; then
    echo "$(date): No CSV changes detected." >> "$LOG_FILE"
    exit 0
fi

# ===== COMMIT CSV CHANGES =====
git commit -m "Auto-update CSV files: $(date '+%Y-%m-%d %H:%M:%S')" \
    --only -- ':(glob)**/*.csv'

# ===== PUSH TO GITHUB =====
git push origin "$BRANCH"

echo "$(date): CSV changes successfully pushed." >> "$LOG_FILE"
