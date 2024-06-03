## Setting up your dev environment

1. Install poetry

   ```
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. Install dependencies, including testing

   ```
   poetry install -E test
   ```

## Running tests

We use pytest to run our tests. To run:

```
poetry run pytest
```

## Linting

We use pre-commit hooks to manage linters. To install, run:

```
pre-commit install
```
