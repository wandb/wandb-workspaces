# Release Process

This repository uses a mostly automated release process with GitHub Actions.

## Workflows

### 1. **Prepare Release** (`prepare-release.yml`)
Creates a pull request with the version bump.

### 2. **Auto Release** (`auto-release.yml`)
Detects version changes on main, then builds and publishes to GitHub and PyPI.

## How to Release

### Step 1: Prepare the Release

1. Go to **Actions** → **Prepare Release**
2. Click **Run workflow**
3. Enter the version number (e.g., `0.2.0`)
4. Click **Run workflow**

This will:
- Create a release branch `release/v{version}`
- Bump the version in `pyproject.toml`
- Push the branch
- Create a PR to `main`

### Step 2: Merge and Done!

1. Review the PR created by the workflow
2. Ensure the version bump is correct
3. Wait for CI checks to pass
4. Merge the PR to `main`

The rest happens automatically:

### The Automation Chain

When the PR is merged, the `auto-release` workflow:
1. Reads version from `pyproject.toml` at HEAD
2. Reads version from `pyproject.toml` at HEAD~1
3. If they differ:
   - Builds the package using `uv`
   - Creates a GitHub Release with auto-generated notes (which also creates the tag)
   - Attaches the built distribution files
   - Publishes to PyPI using Trusted Publishing
4. If unchanged, does nothing (safe for other commits to main)

## What Gets Published

- **GitHub Release**: Created with auto-generated release notes and attached distribution files
- **PyPI**: Package published with Trusted Publishing (no API tokens needed)

## Troubleshooting


**Tag already exists**:
```bash
git tag -d v0.2.0
git push origin :refs/tags/v0.2.0
```

**Workflow didn't trigger**:
- Ensure the tag name starts with `v` (e.g., `v0.2.0`)
- Check the Actions tab for any errors


## Security

- All GitHub Actions are pinned to commit SHAs
- PyPI publishing uses Trusted Publishing (OIDC), not API tokens
- No secrets should be stored in the repository

