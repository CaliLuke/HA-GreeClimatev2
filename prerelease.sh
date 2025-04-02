#!/bin/bash

# Exit on error, treat unset variables as errors, fail pipeline if any command fails
set -euo pipefail

# --- Argument Parsing ---
dry_run=false
if [[ "${1:-}" == "--dry-run" || "${1:-}" == "-d" ]]; then
  dry_run=true
  echo "*** Dry Run Mode Enabled ***"
  echo
fi

# --- Configuration ---
TARGET_BRANCH="master" # Adjust if your main branch is different (e.g., "main")
TAG_PATTERN='^[0-9]+\.[0-9]+\.[0-9]+$' # X.Y.Z format
MANIFEST_PATH="custom_components/greev2/manifest.json"
MEMORY_BANK_PATH="memory-bank/"
COMMIT_MSG_FILENAME="commit_msg.txt" # Define filename for commit message

# --- Helper Functions ---
check_command() {
  if ! command -v "$1" &> /dev/null; then
    echo "Error: Required command '$1' not found. Please install it." >&2
    exit 1
  fi
}

print_error() {
  echo "Error: $1" >&2
  exit 1
}

# --- Prerequisite Checks ---
echo "Checking prerequisites..."
check_command git
echo "Prerequisites met."
echo

# --- Git Branch Check ---
echo "Checking git branch..."
current_branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$current_branch" != "$TARGET_BRANCH" ]; then
  print_error "Must be on the '$TARGET_BRANCH' branch to run prerelease (current: '$current_branch')."
fi
echo "Currently on '$TARGET_BRANCH' branch."
echo

# --- Determine Next Version ---
echo "Determining latest version tag..."
# Fetch tags only in non-dry run
if [ "$dry_run" = false ]; then
    # Fetch from origin to ensure we have the latest tags from the remote
    git fetch --tags origin || print_error "Failed to fetch tags from origin."
fi

# Get latest tag matching pattern from *all* tags (local and fetched)
latest_tag=$(git tag --list --sort=-v:refname | grep -E "$TAG_PATTERN" | head -n 1)

if [ -z "$latest_tag" ]; then
  echo "No previous tag matching pattern '$TAG_PATTERN' found. Assuming first version."
  latest_tag="0.0.0" # Default for calculation if no tags exist
fi
echo "Latest tag found: $latest_tag"

IFS=. read -r major minor patch <<< "$latest_tag"
# Handle potential non-numeric patch if latest_tag was empty/invalid (though grep should prevent)
if ! [[ "$patch" =~ ^[0-9]+$ ]]; then
    echo "Warning: Could not parse patch version from '$latest_tag'. Defaulting patch to 0."
    patch=0
fi
next_patch=$((patch + 1))
new_tag="$major.$minor.$next_patch"
echo "Next version calculated: $new_tag"
echo

# --- Update Manifest ---
echo "Updating manifest file..."
if [ "$dry_run" = true ]; then
  echo "Dry Run: Would update '$MANIFEST_PATH' with version '$new_tag'."
else
  # Check if manifest exists
  if [ ! -f "$MANIFEST_PATH" ]; then
      print_error "Manifest file not found at '$MANIFEST_PATH'."
  fi
  # Use sed -i '' for macOS compatibility
  sed -i '' "s/\"version\": *\"[^\"]*\"/\"version\": \"$new_tag\"/" "$MANIFEST_PATH" || print_error "Failed to update version in '$MANIFEST_PATH'."
  echo "Updated '$MANIFEST_PATH' to version '$new_tag'."
fi
echo

# --- Stash Memory Bank ---
echo "Handling memory bank changes..."
stashed_memory_bank=false
# Check if there are any changes (staged or unstaged) in the memory bank path first
if git status --porcelain "$MEMORY_BANK_PATH" | grep -q .; then
    # Always stash for accurate file listing, mark if we did for dry run pop
    echo "Stashing changes in '$MEMORY_BANK_PATH' temporarily..."
    git stash push --quiet -- "$MEMORY_BANK_PATH" || print_error "Failed to stash changes in '$MEMORY_BANK_PATH'."
    stashed_memory_bank=true # Mark that we stashed something
    echo "Stashed changes in '$MEMORY_BANK_PATH'."
else
    echo "No changes detected in '$MEMORY_BANK_PATH' to stash."
fi
echo

# --- List Changed Files ---
echo "Listing files staged or modified (excluding memory-bank):"
# Use git status --porcelain and filter out memory-bank entries
# This will now accurately reflect the state after stashing
git status --porcelain | grep -vE "^[? ][? ] ${MEMORY_BANK_PATH}" || echo "(No other changes detected)"
echo

# --- Suggest Next Steps ---
echo "--------------------------------------------------"
echo "Prerelease preparation complete."
echo "Next Version: $new_tag"
echo "--------------------------------------------------"
echo
echo "Next steps:"
echo "1. Roo (AI) will review the changed files listed above."
echo "2. Roo will formulate a detailed commit message (title and body)."
echo "3. Roo will present the message for User approval."
echo "4. Upon approval, Roo will save the message to '$COMMIT_MSG_FILENAME' in the project root."
echo "5. Roo will then execute './release.sh' which uses '$COMMIT_MSG_FILENAME'."
echo


# --- Dry Run Cleanup / Footer ---
if [ "$dry_run" = true ]; then
  # Pop the stash if we created one during the dry run
  if [ "$stashed_memory_bank" = true ]; then
      echo "Dry Run: Restoring stashed memory bank changes..."
      git stash pop --quiet || echo "Warning: Failed to pop stash during dry run cleanup. Manual check needed."
      echo "Dry Run: Restored memory bank changes."
  fi
  echo "*** DRY RUN COMPLETE - No changes were made permanently. ***"
fi