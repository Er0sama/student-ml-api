# Viva Preparation — student-ml-api

Answers to the fifteen questions listed in the assignment. Each answer states
the principle first, then how it shows up in this repository.

---

### 1. Why should developers avoid directly pushing to `main`?

`main` is the branch every other process trusts. Tags are cut from it, images
are built from it, and deployments come from it. A direct push bypasses every
guard at once: no review, no CI, no discussion, and no record of why the change
was made beyond a single commit message.

The deeper problem is that a broken `main` blocks the whole team, not just the
author. Anyone who branches during the broken window inherits the breakage.
Forcing changes through a pull request means the default state of `main` is
always a state that passed its tests.

In this repository, branch protection makes this a rule rather than an
agreement, so it survives someone being in a hurry at 5pm.

---

### 2. What is the purpose of a Pull Request beyond simply merging code?

Merging is the least interesting thing a pull request does. Its real value:

- **It is a review surface.** A diff with line comments is where design
  problems get caught while they are still cheap to fix.
- **It is the automation trigger.** CI attaches to the pull request, so the
  verdict arrives before the merge rather than after it.
- **It is a durable record.** Six months later the pull request explains *why*
  a change was made. `git blame` only shows what changed.
- **It is a quality gate.** Checklists and required checks encode team
  standards so they do not depend on someone remembering.

A pull request converts an individual's change into a team decision.

---

### 3. Why should CI execute before a PR is merged?

Because the cost of a defect grows sharply the further it travels. Caught on a
pull request, a failing test is one author fixing their own branch while the
context is fresh. Caught after merge, it is a broken `main` blocking everyone,
plus a revert, plus a re-fix.

Running CI before merge also keeps the signal clean. If `main` only ever
receives changes that passed, then a red `main` genuinely means something is
wrong, rather than being background noise people learn to ignore.

This exercise demonstrates the point deliberately in Part 6: a broken assertion
was pushed, the pull request went red, and merging was correctly blocked until
the fix landed.

---

### 4. What is the difference between a Docker image and a container?

An **image** is a static, immutable, layered filesystem plus metadata such as
the entrypoint, exposed ports and working directory. It is a build artifact
sitting on disk or in a registry, doing nothing.

A **container** is a running instance of that image. It adds a writable layer
on top and gets its own process namespace, network and lifecycle.

The relationship is class to object. One image spawns many containers, each
independent. Deleting a container leaves the image untouched, which is exactly
why the rollback in Part 20 was instant: the 1.0.0 image was still present in
the registry, so restoring the old version was a matter of starting a different
container, not rebuilding anything.

---

### 5. Why should Docker images be versioned?

Without a version, you cannot answer the only question that matters during an
incident: *what exactly is running right now?*

Versioning provides:

- **Identity.** `1.0.0` and `1.1.0` are distinguishable artifacts.
- **Rollback.** You cannot go back to a version you never named.
- **Correlation.** A tag connects a running container to a git tag, a merge
  commit and a pull request.
- **Reproducibility.** Staging and production can be proven to run the same
  bytes.

In an MLOps context this matters twice over, because both the application code
and the model can change independently.

---

### 6. Why is `latest` insufficient for production traceability?

`latest` is a mutable pointer, not a version. It is simply whichever image was
pushed most recently, so its meaning changes underneath you.

The practical failures:

- Two machines pulling `latest` a week apart run different code while both
  claim to run `latest`.
- You cannot roll back, because there is no name for the previous thing.
- A pull is not reproducible, so an incident cannot be replayed.
- The tag carries no information about which commit produced it.

`latest` is a convenience for humans experimenting locally. Production should
pin an immutable version tag, or better, a digest.

---

### 7. Why should the same Docker artifact be promoted rather than rebuilt?

Because a rebuild is not guaranteed to produce the same thing. Between two
builds a base image can be patched, a transitive dependency can publish a new
release, and a system package can shift. The result is that the artifact you
tested is not the artifact you shipped.

Build once, then promote the identical image through staging and production.
Testing then means something, because the bytes that passed the tests are the
bytes that serve traffic. It is also faster, since promotion is a retag rather
than a full build.

This is why the release workflow builds exactly once and pushes that same image
under several tags.

---

### 8. What is the purpose of a container registry?

A registry is the distribution layer for images, the way a package index is for
libraries. It provides:

- **Central storage** so a build machine and a runtime machine need no direct
  relationship.
- **Versioned distribution** through tags.
- **Content addressing** through digests, which are immutable.
- **Access control** over who may push and pull.
- **Deduplication**, since shared layers are stored once.

Part 17 demonstrates the value directly. The local image was deleted, pulled
back from the registry, and run successfully without any source code present.

---

### 9. What is the difference between the CI workflow and release workflow?

They differ in trigger, responsibility and side effects.

| | CI | Release |
|---|---|---|
| Trigger | Pull request to `main` | Push of a `v*.*.*` tag |
| Runs | Tests, build validation | Tests, build, publish |
| Side effects | None | Pushes to the registry |
| Frequency | Every commit on a pull request | Once per release |

CI answers "is this change safe to merge?" Release answers "publish this
approved commit as a distributable artifact." Keeping them separate means a
proposal cannot accidentally become a release.

---

### 10. Why should registry credentials be stored as secrets?

A workflow file is committed source code. Anything written into it is visible to
everyone with repository access, is copied into every clone and fork, and stays
in git history forever, so deleting the line later does not remove it.

Secrets are stored encrypted, injected only at run time, masked in logs, and
can be rotated without touching code. This repository goes one better and uses
the automatically provisioned `GITHUB_TOKEN`, which is scoped to the single
repository and expires when the job ends, so there is no long-lived credential
to leak in the first place.

---

### 11. How can you identify which source-code commit produced a Docker image?

Three mechanisms are used here, and they reinforce each other:

1. **OCI labels baked in at build time.** The commit SHA is written into
   `org.opencontainers.image.revision`, so `docker inspect` on any pulled image
   reveals its origin.
2. **A commit-specific image tag.** Every release also publishes the image under
   its short commit SHA.
3. **The tag and merge commit chain.** The git tag points at the merge commit,
   which points at the pull request.

The first is the strongest, because the metadata travels inside the image
itself and survives retagging.

---

### 12. Why does Docker layer ordering affect CI/CD performance?

Each instruction creates a layer, and layers are cached. When one layer is
invalidated, every layer after it is rebuilt regardless of whether its own
inputs changed.

Dependencies change rarely; source code changes constantly. So the expensive,
stable step must come before the cheap, volatile one. The measured result from
Part 25 in this repository:

| Change | Result |
|---|---|
| `app.py` edited | `pip install` served from cache |
| `requirements.txt` edited | `pip install` re-executed |

The wrong ordering, `COPY . .` before installing, would invalidate the pip
layer on every single commit, adding that cost to every pull request.

---

### 13. How would you rollback from version 1.1.0 to 1.0.0?

Stop the current container and start the previously published image:

```bash
docker stop student-ml-api && docker rm student-ml-api
docker run -d --name student-ml-api -p 5000:5000 ghcr.io/er0sama/student-ml-api:1.0.0
curl http://localhost:5000/health
```

No git operations, no rebuild, no dependency installation. The 1.0.0 artifact
was never modified when 1.1.0 was published, so it is still exactly the image
that was tested and released. Recovery time is a pull and a start.

Afterwards you would fix forward, releasing a 1.1.1 through the normal pull
request path rather than leaving production pinned to an old version.

---

### 14. What is the relationship between a Git tag and a Docker image tag?

They are two ends of the same link. The git tag names a commit in source
history. The image tag names the artifact built from that commit. The release
workflow is what binds them, deriving `1.0.0` from `v1.0.0` by stripping the
prefix, so the two can never drift apart through a typo.

The correspondence is deliberate but not automatic. Git tags are movable
pointers in a repository, image tags are movable pointers in a registry, and
only a disciplined pipeline keeps them in agreement. This repository also fails
the build if the `VERSION` file disagrees with the pushed tag.

---

### 15. In an MLOps system, what additional problems arise when the application version and model version change independently?

This is the question that separates MLOps from ordinary software delivery. A
conventional service has one thing to version. An ML service has at least three:
code, model weights, and training data.

The problems that follow:

- **Version identity breaks down.** "Version 1.1.0" is ambiguous once the same
  code can serve different models. A prediction is only reproducible if both are
  pinned, which is why `/health` in version 1.1.0 reports `application_version`
  and `model_version` separately.
- **The compatibility matrix grows.** Any model can in principle be served by
  any code version, and not all combinations are valid. A model expecting new
  input features will fail silently or loudly against older code.
- **Rollback becomes ambiguous.** If quality drops, was it the code or the
  model? Rolling back the container reverts both, which may be more than you
  wanted.
- **Failures become silent.** Broken code raises an exception. A degraded model
  returns confident, plausible, wrong answers, and nothing crashes.
- **The artifact is no longer self-contained.** Weights are usually too large
  for an image, so they are fetched at run time, which reintroduces exactly the
  external dependency containers were meant to remove.

The usual response is to version and track them separately, record both in
every prediction log, and monitor prediction quality rather than only uptime.
