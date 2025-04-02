#!/bin/bash

# Exit on error, treat unset variables as errors, fail pipeline if any command fails
set -euo pipefail

# --- Argument Parsing ---
dry_run=false
commit_message_file="" # Initialize variable

# Parse arguments
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    -d|--dry-run)
      dry_run=true
      shift # past argument
      ;;
    -m|--commit-message-file)
      commit_message_file="$2"
      shift # past argument
      shift # past value
      ;;
    *)    # unknown option
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

if [ "$dry_run" = true ]; then
    echo "*** Dry Run Mode Enabled ***"
    echo
fi

# Validate commit message file path (required for both dry and real run now)
if [ -z "$commit_message_file" ]; then
  echo "Error: --commit-message-file <path> is required." >&2
  exit 1
fi
# Check existence only if not dry run, as file might not exist yet for dry run planning
if [ "$dry_run" = false ] && [ ! -f "$commit_message_file" ]; then
  echo "Error: Commit message file not found at '$commit_message_file'." >&2
  exit 1
fi


# --- Configuration ---
TARGET_BRANCH="master"
TAG_PATTERN='^[0-9]+\.[0-9]+\.[0-9]+$' # X.Y.Z format
# COMMIT_MSG_FILENAME_BASENAME=$(basename "$commit_message_file") # No longer needed for stashing

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

# --- Git Branch Check ---
# REMOVED: Clean working directory check
echo "Checking git branch..."
current_branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$current_branch" != "$TARGET_BRANCH" ]; then
  print_error "Must be on the '$TARGET_BRANCH' branch to create a release (current: '$current_branch')."
fi
echo "Currently on '$TARGET_BRANCH' branch."
echo

# --- Fetch Tags ---
echo "Fetching latest tags from origin..."
# Fetch tags only in non-dry run
if [ "$dry_run" = false ]; then
    git fetch --tags origin || print_error "Failed to fetch tags from origin."
fi
echo "Tags fetched (or skipped in dry run)."
echo

# --- Determine Latest Tag & Calculate Next Tag ---
# Note: Version calculation is primarily for the tag name now, manifest was updated by prerelease.sh
echo "Determining latest version tag..."
latest_tag=$(git tag --list --sort=-v:refname | grep -E "$TAG_PATTERN" | head -n 1)

if [ -z "$latest_tag" ]; then
  echo "No previous tag matching pattern '$TAG_PATTERN' found. Assuming first version."
  latest_tag="0.0.0"
fi
echo "Latest tag found: $latest_tag"

IFS=. read -r major minor patch <<< "$latest_tag"
if ! [[ "$patch" =~ ^[0-9]+$ ]]; then
    echo "Warning: Could not parse patch version from '$latest_tag'. Defaulting patch to 0."
    patch=0
fi
next_patch=$((patch + 1))
new_tag="$major.$minor.$next_patch"
echo "Calculated next tag: $new_tag"
echo

# --- Stash Commit Message File --- (REMOVED)
# echo "Handling commit message file..."
# stashed_commit_msg=false
# ... stash logic removed ...
# echo

# --- Git Add, Commit, Push --- (Corrected Order - No Stash Handling for commit msg)
echo "Staging, committing, and pushing changes..."
if [ "$dry_run" = true ]; then
    echo "Dry Run: Would execute 'git add .'"
    echo "Dry Run: Would execute 'git commit --file=\"$commit_message_file\"'"
    echo "Dry Run: Would execute 'git push origin $TARGET_BRANCH'"
else
    echo "Running: git add ."
    # Add all changes except the commit message file itself (which is untracked)
    # Use git add -- :!filename to exclude, but simpler to just add all and rely on .gitignore or untracked status
    git add . || print_error "Failed to stage changes."

    echo "Running: git commit --file=\"$commit_message_file\""
    # Check if file exists before committing
    if [ ! -f "$commit_message_file" ]; then
        print_error "Commit message file '$commit_message_file' not found before commit attempt."
    fi
    # Commit using the file path provided
    git commit --file="$commit_message_file" || print_error "Failed to commit changes. Check commit message file and git status."

    # Clean up commit message file *after* successful commit
    echo "Cleaning up commit message file: $commit_message_file"
    rm -f "$commit_message_file" || echo "Warning: Failed to delete commit message file '$commit_message_file'."

    echo "Running: git push origin $TARGET_BRANCH"
    git push origin "$TARGET_BRANCH" || print_error "Failed to push commit to origin."
    echo "Changes committed and pushed successfully."

fi
echo

# --- Pop Commit Message Stash --- (REMOVED)

# --- Determine Repository --- (Moved after push)
echo "Determining GitHub repository..."
remote_url=$(git remote get-url origin)
repo_full_name=$(echo "$remote_url" | sed -E -e 's#^.*github\.com[:/](.*)#\1#' -e 's#\.git$##' -e 's#/$##')
if [ -z "$repo_full_name" ] || [[ ! "$repo_full_name" == */* ]]; then
  print_error "Could not determine GitHub owner/repo from origin URL: $remote_url"
fi
echo "Repository found: $repo_full_name"
echo


# --- Dry Run Output for Tagging/Release ---
if [ "$dry_run" = true ]; then
  # REMOVED: Dry run stash pop logic
  echo "Dry run complete for commit phase. Would also execute the following for tagging/release:"
  echo "  git tag \"$new_tag\""
  echo "  git push origin \"$new_tag\""
  echo "  gh release create \"$new_tag\" -R \"$repo_full_name\" --generate-notes --title \"Release $new_tag\" --notes-start-tag \"$latest_tag\""
  echo "*** DRY RUN COMPLETE - No changes were made. ***"
  exit 0
fi

# --- User Confirmation (Tag/Release) ---
read -p "Commit pushed. Create and push tag '$new_tag' and create GitHub release? (y/N) " confirm
confirm_lower=$(echo "$confirm" | tr '[:upper:]' '[:lower:]') # Convert to lowercase

if [[ "$confirm_lower" != "y" ]]; then
  echo "Aborted by user before tagging/releasing."
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
# Use --generate-notes to automatically create release notes from commits since last tag
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