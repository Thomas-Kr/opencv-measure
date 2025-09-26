#!/bin/bash

REPO_DIR="/path/to/your/repo"
VENV_DIR="$REPO_DIR/venv"
REQUIREMENTS="$REPO_DIR/requirements.txt"
LAST_REQ_HASH="/tmp/last_requirements_hash"

cd "$REPO_DIR" || exit 1

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

while true; do
    git fetch

    LOCAL=$(git rev-parse @)
    REMOTE=$(git rev-parse @{u})

    if [ "$LOCAL" != "$REMOTE" ]; then
        echo "Changes detected. Pulling..."
        git pull

        # Check if requirements.txt changed
        NEW_HASH=$(sha256sum "$REQUIREMENTS" | awk '{print $1}')
        OLD_HASH=""
        if [ -f "$LAST_REQ_HASH" ]; then
            OLD_HASH=$(cat "$LAST_REQ_HASH")
        fi

        if [ "$NEW_HASH" != "$OLD_HASH" ]; then
            echo "requirements.txt changed. Installing dependencies..."
            pip install -r "$REQUIREMENTS"
            echo "$NEW_HASH" > "$LAST_REQ_HASH"
        else
            echo "requirements.txt has not changed."
        fi
    else
        echo "No changes detected."
    fi

    sleep 60
done