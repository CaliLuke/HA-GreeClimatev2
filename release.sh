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
TARGET_BRANCH="master"
TAG_PATTERN='^[0-9]+\.[0-9]+\.[0-9]+$' # X.Y.Z format

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
check_command gh

if ! gh auth status &> /dev/null; then
  print_error "Not authenticated with GitHub CLI (gh). Please run 'gh auth login'."
fi

if [ ! -d ".git" ]; then
  print_error "Not a git repository."
fi
echo "Prerequisites met."
echo

# --- Git Status Check ---
echo "Checking git status..."
if ! git diff --quiet HEAD --; then
  print_error "Working directory is not clean. Please commit or stash changes."
fi

current_branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$current_branch" != "$TARGET_BRANCH" ]; then
  print_error "Must be on the '$TARGET_BRANCH' branch to create a release (current: '$current_branch')."
fi

echo "Fetching latest tags from origin..."
git fetch --tags origin || print_error "Failed to fetch tags from origin."
echo "Git status OK."
echo

# --- Determine Repository ---
echo "Determining GitHub repository..."
remote_url=$(git remote get-url origin)
# Extract owner/repo from URL (handles https and git@ formats)
repo_full_name=$(echo "$remote_url" | sed -E 's/.*github.com[:\/](.*)\.git/\1/' | sed 's/\/$//')
if [ -z "$repo_full_name" ] || [[ ! "$repo_full_name" == */* ]]; then
  print_error "Could not determine GitHub owner/repo from origin URL: $remote_url"
fi
echo "Repository found: $repo_full_name"
echo


# --- Determine Latest Tag ---
echo "Determining latest version tag..."
latest_tag=$(git tag --sort=-v:refname | grep -E "$TAG_PATTERN" | head -n 1)

if [ -z "$latest_tag" ]; then
  # This case should ideally not happen based on user confirmation, but included for robustness
  print_error "No previous tag matching pattern '$TAG_PATTERN' found. Cannot determine next version."
fi
echo "Latest tag found: $latest_tag"

# --- Calculate Next Tag ---
IFS=. read -r major minor patch <<< "$latest_tag"
next_patch=$((patch + 1))
new_tag="$major.$minor.$next_patch"
echo "Calculated next tag: $new_tag"
echo

# --- Dry Run Output ---
if [ "$dry_run" = true ]; then
  echo "Dry run complete. Would execute the following commands:"
  echo "  git tag \"$new_tag\""
  echo "  git push origin \"$new_tag\""
  echo "  gh release create \"$new_tag\" -R \"$repo_full_name\" --generate-notes --title \"Release $new_tag\" --notes-start-tag \"$latest_tag\""
  exit 0
fi

# --- User Confirmation ---
read -p "Create and push tag '$new_tag' and create GitHub release? (y/N) " confirm
confirm_lower=$(echo "$confirm" | tr '[:upper:]' '[:lower:]') # Convert to lowercase

if [[ "$confirm_lower" != "y" ]]; then
  echo "Aborted by user."
  exit 0
fi
echo

# --- Git Tagging ---
echo "Creating and pushing tag '$new_tag'..."
if git tag "$new_tag"; then
  echo "Tag '$new_tag' created locally."
else
  print_error "Failed to create local tag '$new_tag'. Does it already exist?"
fi

if git push origin "$new_tag"; then
  echo "Tag '$new_tag' pushed to origin."
else
  # Attempt to clean up local tag if push fails
  git tag -d "$new_tag" &> /dev/null || true
  print_error "Failed to push tag '$new_tag' to origin. Local tag removed."
fi
echo

# --- GitHub Release Creation ---
echo "Creating GitHub release for tag '$new_tag'..."
# Use --generate-notes to automatically create release notes
# Use --title for a clear release title
# Use --notes-start-tag to generate notes since the previous release tag
if release_url=$(gh release create "$new_tag" -R "$repo_full_name" --generate-notes --title "Release $new_tag" --notes-start-tag "$latest_tag"); then
  echo "Successfully created GitHub release."
  echo "Release URL: $release_url"
else
  # Attempt cleanup if release creation fails (tag already pushed)
  echo "Error: Failed to create GitHub release for tag '$new_tag'." >&2
  echo "The git tag '$new_tag' was pushed, but the GitHub release failed." >&2
  echo "You may need to manually create the release on GitHub or clean up the tag:" >&2
  echo "  gh release create \"$new_tag\" -R \"$repo_full_name\" --generate-notes --title \"Release $new_tag\" --notes-start-tag \"$latest_tag\"" >&2
  echo "  OR" >&2
  echo "  git push origin --delete \"$new_tag\" && git tag -d \"$new_tag\"" >&2
  exit 1
fi

echo
echo "Release process completed successfully for $new_tag."