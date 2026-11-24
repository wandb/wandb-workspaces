"""Copy the view spec schema from wandb/core into schema/viewspec/.

The schema lives in the private wandb/core repo, in packages/wandb-schemas.
This repo is public, so the build and tests read the committed copy, and
only a maintainer with read access to wandb/core runs this to move it to a
newer core commit:

    uv run python scripts/sync_schema.py --ref <core commit sha>

It downloads with your `gh` login and records the commit it copied in
schema/viewspec/SOURCE.json.
"""

import argparse
import base64
import json
import pathlib
import subprocess

REPO = "wandb/core"
SOURCE_DIR = "packages/wandb-schemas/viewspec/generated"
FILES = {
    # The read contract: what load accepts, including legacy shapes.
    "viewspec.schema.json": "read",
    # The write contract: the only shape a client may save.
    "viewspec.lean.schema.json": "write",
}
DEST = pathlib.Path(__file__).resolve().parent.parent / "schema" / "viewspec"


def gh_api(path):
    out = subprocess.run(
        ["gh", "api", path], check=True, capture_output=True, text=True
    ).stdout
    return json.loads(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ref", required=True, help="wandb/core commit sha")
    args = parser.parse_args()

    commit = gh_api(f"repos/{REPO}/commits/{args.ref}")
    sha = commit["sha"]

    # Download and parse every file before writing any, so a failed download
    # cannot leave files from different core commits on disk.
    downloaded = {}
    for name in FILES:
        blob = gh_api(f"repos/{REPO}/contents/{SOURCE_DIR}/{name}?ref={sha}")
        if blob.get("encoding") == "base64" and blob.get("content"):
            data = base64.b64decode(blob["content"])
        else:
            # Files over 1 MB come back without content; fetch the blob.
            data = base64.b64decode(gh_api(blob["git_url"])["content"])
        json.loads(data)
        downloaded[name] = data

    DEST.mkdir(parents=True, exist_ok=True)
    for name, data in downloaded.items():
        (DEST / name).write_bytes(data)

    source = {
        "repo": REPO,
        "path": SOURCE_DIR,
        "commit": sha,
        "committedAt": commit["commit"]["committer"]["date"],
        "files": FILES,
    }
    (DEST / "SOURCE.json").write_text(json.dumps(source, indent=2) + "\n")
    print(f"Copied {', '.join(FILES)} from {REPO}@{sha[:12]} to {DEST}")


if __name__ == "__main__":
    main()
