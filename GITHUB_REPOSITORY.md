# GitHub repository hand-off

This directory is the upload-ready source for
`https://github.com/rds0001/risk-weighted-assets-python`.

## Publication boundary

Included are the installable source, complete synthetic reference resources, tests,
documentation, governance files and CI. Build outputs are deliberately not committed:
GitHub Actions rebuilds, validates and retains wheel and sdist artifacts from the exact
commit.

Excluded are construction scaffolds, downloaded third-party publications, real or
confidential bank data, virtual environments, caches, `dist/`, `build/` and egg metadata.
No PyPI token or other repository secret is required for this stage.

## Initial upload

After reviewing the staged tree:

```bash
cd /mnt/d/40_projects/etc/rwa/python-lib-github
git init -b main
git config user.name "RiskDataScience GmbH"
git config user.email "riskdatascience@web.de"
git config core.fileMode false
git add --all
git ls-files -z | xargs -0 git update-index --chmod=-x
git commit -m "Initial risk-weighted-assets Python library"
gh auth status
gh repo create rds0001/risk-weighted-assets-python \
  --public \
  --source=. \
  --remote=origin \
  --push \
  --description "Auditable CRR III RWA, capital, IRRBB and ICAAP Python reference library"
```

For version 1.1.0, merge the reviewed change and require a green CI run before creating
tag `v1.1.0`. Publishing that GitHub Release triggers the separately controlled PyPI
Trusted-Publishing workflow; an existing PyPI version can never be overwritten.

## First CI run

```bash
RUN_ID="$(gh run list \
  --repo rds0001/risk-weighted-assets-python \
  --workflow ci.yml \
  --limit 1 \
  --json databaseId \
  --jq '.[0].databaseId')"
gh run watch "$RUN_ID" \
  --repo rds0001/risk-weighted-assets-python \
  --exit-status
```

Step 11 is complete only when all five Python jobs and the distribution job are green,
the build artifact is downloadable, the default branch is `main`, and the local worktree
is clean.
