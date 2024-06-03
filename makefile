.PHONY: publish-pypi publish-github publish-all

# Environment variable for version
VERSION ?= $(shell poetry version -s)
GITHUB_VERSION = v$(VERSION)

# Publishing steps:
# 1. Bump version in pyproject.toml, and push changes
# 2. Run the publish commands, e.g. `publish-pypi`

# Publish to PyPI
publish-pypi:
	@echo "Publishing to PyPI..."
	poetry publish --build

# Tag and create a release on GitHub
publish-github:
	@echo "Tagging the release on GitHub..."
	git tag -a $(GITHUB_VERSION) -m "Release version $(GITHUB_VERSION)"
	git push origin $(GITHUB_VERSION)
	@echo "Creating a GitHub release..."
	gh release create $(GITHUB_VERSION) dist/* --notes "Release version $(GITHUB_VERSION)"

# Publish to both PyPI and GitHub
publish-all: publish-pypi publish-github
	@echo "Published to both PyPI and GitHub."
