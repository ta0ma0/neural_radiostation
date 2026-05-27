#!/bin/sh
# Увеличивает версию в VERSION и коммитит
# Использование: ./tools/bump_version.sh

VERSION_FILE="$(dirname "$0")/../VERSION"
CURRENT=$(cat "$VERSION_FILE")

# Увеличиваем patch-версию (1.0.4 -> 1.0.5)
MAJOR=$(echo "$CURRENT" | cut -d. -f1)
MINOR=$(echo "$CURRENT" | cut -d. -f2)
PATCH=$(echo "$CURRENT" | cut -d. -f3)
NEW="$MAJOR.$MINOR.$((PATCH + 1))"

echo "$NEW" > "$VERSION_FILE"
echo "$CURRENT → $NEW"
