# Release Process

This repository uses a two-stage release process with GitHub Actions.

## Workflows

### 1. **Prepare Release** (`prepare-release.yml`)
Creates a pull request with the version bump.

### 2. **Publish Release** (`publish-release.yml`)
Automatically triggers when a version tag is pushed, builds the package, creates a GitHub release, and publishes to PyPI.

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

### Step 2: Review and Merge

1. Review the PR created by the workflow
2. Ensure the version bump is correct
3. Wait for CI checks to pass
4. Merge the PR to `main`

### Step 3: Create the Tag

You have two options:

#### Option A: Via Git Command Line
```bash
git checkout main
git pull origin main
git tag v0.2.0
git push origin v0.2.0
```

#### Option B: Via GitHub UI
1. Go to **Releases** → **Draft a new release**
2. Click **Choose a tag**
3. Type `v0.2.0` and click **Create new tag: v0.2.0 on publish**
4. The tag field and title will auto-populate
5. Click **Publish release**

### Step 4: Automatic Publishing

Once the tag is pushed, the `publish-release.yml` workflow automatically:

1. ✅ Checks out the code at the tagged commit
2. ✅ Builds the package using `uv`
3. ✅ Generates release notes from commits since the last release
4. ✅ Creates a GitHub Release with the built artifacts
5. ✅ Publishes to PyPI using Trusted Publishing

## What Gets Published

- **GitHub Release**: Created with auto-generated release notes and attached distribution files
- **PyPI**: Package published with Trusted Publishing (no API tokens needed)

## Prerequisites

### PyPI Trusted Publishing

You must configure Trusted Publishing on PyPI:

1. Go to https://pypi.org/manage/project/wandb-workspaces/
2. Navigate to **Publishing** → **Add a new publisher**
3. Configure:
   - **Owner**: `wandb`
   - **Repository name**: `wandb-workspaces`
   - **Workflow name**: `publish-release.yml`
   - **Environment name**: (leave blank)

### GitHub Permissions

The workflows use `GITHUB_TOKEN` which requires:
- **Settings** → **Actions** → **General** → **Workflow permissions**
- Select **Read and write permissions**

## Troubleshooting

**Tag already exists**:
```bash
git tag -d v0.2.0
git push origin :refs/tags/v0.2.0
```

**Workflow didn't trigger**:
- Ensure the tag name starts with `v` (e.g., `v0.2.0`)
- Check the Actions tab for any errors

**PyPI publish fails**:
- Verify Trusted Publishing is configured correctly on PyPI
- Check that `id-token: write` permission is set in the workflow

## Security

- All GitHub Actions are pinned to commit SHAs
- PyPI publishing uses Trusted Publishing (OIDC), not API tokens
- No secrets need to be stored in the repository

