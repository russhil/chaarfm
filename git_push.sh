#!/bin/bash

# Git push script for ChaarFM project
# Usage: ./git_push.sh "Commit message"

COMMIT_MSG="$1"

# Check if commit message is provided
if [ -z "$COMMIT_MSG" ]; then
    echo "Usage: $0 \"Commit message\""
    exit 1
fi

echo "=== Pushing changes to Git ==="
echo "Commit message: $COMMIT_MSG"
echo "-----------------------------"

# Add all changes
git add .

# Commit changes
git commit -m "$COMMIT_MSG"

# Pull remote changes with rebase
echo "-----------------------------"
echo "Pulling remote changes (rebase)..."
git pull origin main --rebase

# Push changes
echo "-----------------------------"
echo "Pushing to remote repository..."
git push origin main

echo "-----------------------------"
echo "Push completed successfully!"
