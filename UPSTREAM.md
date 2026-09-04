# Upstream provenance

This repository is a private derivative development source for Ren's maintained
`frontend-slides` variant. It preserves the public upstream history while
keeping private changes on a separate branch.

## Source

- Upstream repository: https://github.com/zarazhangrui/frontend-slides
- Upstream branch: `main`
- Current rebase base: `9906a34d640d2111f724544cbc50f7f130569ae1`
- Latest upstream release at branch creation: `v2.1.0`
- Release commit: `24e420e4acef9850505142c449415ac867e43633`
- License: MIT

## Local history

- Previous project-local snapshot matched upstream commit
  `8dca834fc61abc9dd633cbe6a74ed7be3d82a608` byte-for-byte across its 12
  ordinary payload files.
- The previous project-local `.git` directory was incomplete and is not a
  development source.

## Branch policy

- `main` mirrors reviewed upstream history and contains no private behavior
  changes.
- `ren/release-bundling` carries Ren's packaging and release-workflow changes.
- Refresh by fetching `upstream/main`, rebasing the variant branch, rerunning
  its tests, and recording the new base commit here before releasing.
- The private skills hub receives reviewed snapshots pinned to a clean commit;
  it is not the development repository.

## GitHub relationship

GitHub does not provide a private fork of this public repository under the
requested visibility. `ren2019/frontend-slides` is therefore a private derived
repository with full upstream history and an explicit `upstream` remote, not a
GitHub platform fork.
