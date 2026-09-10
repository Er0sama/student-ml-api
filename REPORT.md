# Assignment Report — student-ml-api

Repository: `https://github.com/Er0sama/student-ml-api`
Registry: `ghcr.io/er0sama/student-ml-api`

Viva answers are in [VIVA.md](VIVA.md).

---

## Part 6 — Deliberate CI failure

The health assertion was changed to `assert data["status"] == "wrong"` and
pushed to the open pull request.

**Result: pull request CI failed.** Run `34439612151`:

```
tests/test_app.py::test_health FAILED                                    [ 25%]
>       assert data["status"] == "wrong"
E       AssertionError: assert 'healthy' == 'wrong'
FAILED tests/test_app.py::test_health - AssertionError: assert 'healthy' == 'wrong'
========================= 1 failed, 3 passed in 0.16s ==========================
```

Two things are worth noting. The `Docker build validation` job reported
`skipping` rather than running, because it declares `needs: test` and a failed
dependency short-circuits it. That saves roughly 20 seconds of build time on
every broken pull request. Secondly, the merge button was blocked, because
`Unit tests` is a required status check under branch protection.

The assertion was then restored and committed as `fix: correct health endpoint
test`. Both jobs passed on the next run.

## Part 7 — Branch protection settings on `main`

| Setting | Value | Reason |
|---|---|---|
| Require a pull request before merging | Enabled | Blocks direct pushes, forces the review path |
| Required approvals | 1 | A second pair of eyes before code enters `main` |
| Require status checks to pass | Enabled | A red pipeline cannot be merged |
| Required checks | `Unit tests`, `Docker build validation` | Both CI jobs must be green |
| Require branches to be up to date | Enabled | Prevents two individually-green branches breaking `main` together |
| Require conversation resolution | Enabled | Review comments cannot be silently ignored |
| Allow force pushes | Disabled | History on `main` stays immutable |
| Allow deletions | Disabled | `main` cannot be removed accidentally |
| Enforce for administrators | Enabled | The rules apply to the repository owner too |

The last one matters most on a solo repository. Without it, the owner can
bypass every rule above, and the protection becomes decorative.

*Note: on a single-owner repository the required approval is satisfied by
disabling that one rule, since GitHub does not allow self-approval. This is
recorded here as a deliberate, documented deviation rather than an oversight.*

## Part 8 — Merge strategy

**Selected: squash and merge.**

Each feature branch here represents one logical unit of work, split across
several small commits made while developing. Squashing gives `main` a history
where one commit equals one feature, which makes the log readable and makes
`git revert` a single safe operation. The individual development commits remain
visible in the pull request itself, so nothing is lost.

Merge commits were rejected because they clutter the history of a small project
with noise. Rebase merging was rejected because it replays every intermediate
commit onto `main`, including work-in-progress states that never passed CI on
their own.

The effect is visible in this repository. Pull request #1 contained ten commits,
including the deliberately broken test and its fix. On `main` that became a
single commit, `fa0bcc7`, while the full development history remains readable in
the pull request itself.

### Review response

Pull request #1 received six automated review comments. Three identified real
defects and were fixed in `ef8b777` before merging:

- `/predict` returned HTTP 500 rather than 400 for a JSON body that parsed but
  was not an object. A list such as `["value"]` satisfied the `in` membership
  check and then raised `TypeError` on subscript. A fifth test now covers it.
- The CI smoke-test container was removed only on the success path, so a failed
  health check leaked a container into subsequent steps. Cleanup is now trapped
  on exit.
- The OCI `created` label used the repository's last-updated timestamp, which
  can differ from the build time for the same commit. It now uses
  `github.run_started_at`.

Merging was initially blocked by the `required_conversation_resolution` rule
while these threads were open, which is the rule working as intended.

## Part 10 — Local build and run

```bash
docker build -t student-ml-api:1.0.0 .
docker run -d --name student-ml-api -p 5000:5000 student-ml-api:1.0.0
curl http://localhost:5000/health
```

Response:

```json
{"application":"student-ml-api","status":"healthy","version":"1.0.0"}
```

The version comes from the `VERSION` file, which is read at import time, so the
container cannot report a version that disagrees with the artifact.

## Part 11 — Image and container inspection

| Item | Value |
|---|---|
| Container ID | `24f5ef1407a1` |
| Image ID | `efd074f58995` |
| Exposed port | `5000/tcp`, published as `0.0.0.0:5000->5000/tcp` |
| Running command | `gunicorn --bind 0.0.0.0:5000 app:app` |
| Working directory | `/app` |

`docker logs student-ml-api` confirms the bind address:

```
[INFO] Starting gunicorn 23.0.0
[INFO] Listening at: http://0.0.0.0:5000 (1)
[INFO] Using worker: sync
[INFO] Booting worker with pid: 7
```

`docker exec -it student-ml-api sh` lands in `/app` containing `VERSION`,
`app.py` and `requirements.txt`. The `tests/` directory and `.git` are absent,
confirming `.dockerignore` is being applied.

## Part 22 — Why publishing images from every pull request is undesirable

- **A proposal is not a release.** A pull request is a request for discussion.
  Publishing from it puts unreviewed code in the place where deployments are
  pulled from.
- **Registry pollution.** Every push to every open branch would create an image.
  Finding the real releases among them becomes guesswork.
- **Version ambiguity.** Pull request builds have no meaningful version, so they
  end up on `latest` or on invented tags, and `latest` stops meaning the newest
  release.
- **Credential exposure.** Publishing requires write credentials. Granting them
  to a workflow that runs arbitrary branch code, including from forks, is a
  serious escalation path.
- **Cost and noise.** Storage and bandwidth for artifacts nobody will deploy.

CI proves the image *can* be built. Only a tag decides that it *should* be
published.

## Part 25 — Docker layer cache comparison

Two rebuilds were performed against a warm cache.

**Build A, only `app.py` modified:**

```
Step 7/11 : COPY requirements.txt .          ---> Using cache
Step 8/11 : RUN pip install --no-cache-dir   ---> Using cache
Step 9/11 : COPY VERSION app.py ./           ---> rebuilt
```

**Build B, only `requirements.txt` modified:**

```
Step 7/11 : COPY requirements.txt .          ---> rebuilt
Step 8/11 : RUN pip install --no-cache-dir   ---> rebuilt (Running in 390bcb4e7664)
Step 9/11 : COPY VERSION app.py ./           ---> rebuilt
```

Layers 1 to 6, the base image, build arguments, labels and `WORKDIR`, were
cached in both builds.

**Why the ordering matters.** Docker invalidates a layer when its inputs change,
and every subsequent layer with it. Source code changes on every commit;
dependencies change rarely. Copying `requirements.txt` alone and installing
before copying source means the expensive install layer survives ordinary code
changes, as Build A shows.

The alternative, `COPY . .` followed by `RUN pip install`, makes the
dependency layer depend on every file in the project. Editing one line of
`app.py` would then reinstall every dependency, on every commit, in every CI
run. Build B is what *every* build would look like.

## Part 26 — Failure analysis

Three failures were reproduced and diagnosed. The first was genuine and was
caught by CI rather than staged.

### Failure 1 — Failed pytest, import error in CI only

| | |
|---|---|
| **Symptom** | All four tests passed locally, but the first CI run failed during collection, before any test executed. |
| **Root cause** | Tests were run locally as `python -m pytest`, which prepends the working directory to `sys.path`. CI runs bare `pytest`, which does not. With no `conftest.py` or path configuration, `app.py` at the repository root was not importable. |
| **Evidence** | `ModuleNotFoundError: No module named 'app'` at `tests/test_app.py:3`, `collected 0 items / 1 error`, exit code 2. Run `34439430980`. |
| **Correction** | Added `pytest.ini` setting `pythonpath = .`, which makes both invocation styles resolve imports identically. |

The lesson is that a local pass is not proof. The two environments differed in
one invocation detail, and only CI ran the command the way a fresh machine would.

### Failure 2 — Failed pytest, incorrect assertion

| | |
|---|---|
| **Symptom** | Pull request CI red, one of four tests failing, merge blocked. |
| **Root cause** | The test asserted a health status of `wrong` while the application correctly returns `healthy`. The test was wrong, not the application. |
| **Evidence** | `AssertionError: assert 'healthy' == 'wrong'`, run `34439612151`. |
| **Correction** | Restored the assertion to `healthy`, committed as `fix: correct health endpoint test`. |

This is the deliberate failure required by Part 6. It also demonstrates the
distinction that matters when a test goes red: the failure identifies a
disagreement between test and code, and deciding which one is wrong is a
judgement the pipeline cannot make for you.

### Failure 3 — Application bound to 127.0.0.1

| | |
|---|---|
| **Symptom** | The container started, stayed healthy and published its port, but `curl http://localhost:5001/health` failed with exit code 56, connection reset by peer. Nothing appeared in the logs, because no request ever arrived. |
| **Root cause** | The server was bound to `127.0.0.1:5000`, which inside a container means the container's own loopback interface. Traffic arriving from the host through the published port targets the container's external interface, where nothing is listening. Docker forwards the packet correctly and the container refuses it. |
| **Evidence** | `docker ps` showed `Up 4 seconds  0.0.0.0:5001->5000/tcp`, so the port mapping was correct. `docker logs` showed `Listening at: http://127.0.0.1:5000`. The decisive test was running the request from inside the container, which succeeded and returned the normal healthy payload while the same request from the host failed. |
| **Correction** | Bind to `0.0.0.0:5000`, which is what the committed `Dockerfile` does. |

This failure is worth understanding because every surface-level signal looks
correct. The container is running, the port mapping is right, the image built
cleanly and the application has not crashed. Only the bind address is wrong, and
the only place it is visible is the startup log line.

An additional trap was encountered while reproducing this. The first attempt
mapped the broken container to port 5000, which was still held by the working
container from Part 10. Docker refused to start it, and the subsequent `curl`
returned a healthy response from the *old* container, which looks exactly like
a pass. Publishing to 5001 instead made the real behaviour visible. A green
check against the wrong process is more dangerous than a red one.

## Part 16 — Registry verification (1.0.0)

The release workflow for tag `v1.0.0` (run `34440046729`) derived the version
from the tag and published three tags pointing at one image:

```
ghcr.io/er0sama/student-ml-api:1.0.0
ghcr.io/er0sama/student-ml-api:latest
ghcr.io/er0sama/student-ml-api:fa0bcc7
```

Workflow log confirming the version was derived, not hard-coded:

```
Releasing version 1.0.0
```

**Image digest:** `sha256:4ecd42add56374eb92285952695ac2fb74cdcf6f63678f3156548a86d9e0a5f6`

The package inherits the repository's public visibility, so it can be pulled
anonymously without a token.

## Part 17 — Artifact reproducibility

The local images were deleted, leaving nothing on the build machine:

```bash
docker rm -f student-ml-api
docker rmi -f student-ml-api:1.0.0 ghcr.io/er0sama/student-ml-api:1.0.0
docker images | grep student-ml-api   # no results
```

The image was then retrieved from the registry and started, with no build step
and no source code involved:

```bash
docker pull ghcr.io/er0sama/student-ml-api:1.0.0
docker run -d --name student-ml-api -p 5000:5000 ghcr.io/er0sama/student-ml-api:1.0.0
curl http://localhost:5000/health
```

```
Digest: sha256:4ecd42add56374eb92285952695ac2fb74cdcf6f63678f3156548a86d9e0a5f6
{"application":"student-ml-api","status":"healthy","version":"1.0.0"}
```

The digest of the pulled image matches the digest reported by the workflow that
built it. That equality is the actual proof. It shows the bytes running here are
the same bytes the pipeline tested, rather than a rebuild that merely resembles
them.

## Part 23 — Image metadata

`docker inspect ghcr.io/er0sama/student-ml-api:1.0.0` returns:

```
org.opencontainers.image.title=student-ml-api
org.opencontainers.image.description=Minimal prediction API for the MLOps CI/CD exercise
org.opencontainers.image.version=1.0.0
org.opencontainers.image.revision=fa0bcc7bd832a333147acb8a162795efc6290336
org.opencontainers.image.source=https://github.com/Er0sama/student-ml-api
org.opencontainers.image.created=
```

The `revision` label is the important one. Given only a running container, it
identifies the exact commit that produced the image, without consulting the
registry or the repository.

**A defect was found here.** The `created` label published empty on 1.0.0. The
build argument referenced `github.run_started_at`, which is not part of the
GitHub context, so it expanded to an empty string and silently overrode the
`ARG` default. This is a good illustration of why metadata must be verified on a
pulled artifact rather than assumed from the workflow source. The build did not
fail, CI did not complain, and the label was simply blank. It was corrected in
`2c2788f` on the 1.1.0 branch by generating the timestamp inside the workflow,
and the fix is confirmed against the 1.1.0 image below.

## Part 24 — Commit SHA image tag

Every release also publishes the image under its short commit SHA, verified as
pullable:

```bash
docker pull ghcr.io/er0sama/student-ml-api:fa0bcc7
```

**Why this is useful.** Semantic version tags describe intent, but several
different builds can carry the same intent during development, and `latest`
moves. A commit tag is unambiguous and permanent. It lets you deploy an exact
commit that has no release version yet, for example to reproduce a bug report,
and it gives monitoring and incident tooling a single identifier that maps
directly back to source without a lookup table.

## Part 19 — Release 1.1.0

Tag `v1.1.0` was pushed after the pull request merged, and run `34440414643`
published it. The version was again derived from the tag:

```
Releasing version 1.1.0
```

**Image digest:** `sha256:9ab72b3254e542f70db693217a2d68932b69612291bf543c59c67a5e72ad9c75`

Registry state verified by pulling each tag and comparing digests:

| Tag | Digest | Note |
|---|---|---|
| `1.0.0` | `sha256:4ecd42ad...` | still pullable, untouched |
| `1.1.0` | `sha256:9ab72b32...` | new release |
| `latest` | `sha256:9ab72b32...` | identical to 1.1.0 |

`latest` and `1.1.0` resolve to the same digest, which confirms `latest` moved
rather than being rebuilt. Publishing 1.1.0 did not modify the 1.0.0 tag in any
way, and that immutability is what makes the rollback below possible.

The `created` label defect from 1.0.0 is confirmed fixed:

```
org.opencontainers.image.created=2026-09-10T05:16:41Z
org.opencontainers.image.version=1.1.0
org.opencontainers.image.revision=a85bb7cb384280273de9cbc0f5e9a0e716ba54e4
```

## Part 20 — Rollback

Version 1.1.0 was deployed and confirmed serving:

```json
{"application":"student-ml-api","application_version":"1.1.0","model_version":"model-1","status":"healthy"}
```

Treating 1.1.0 as faulty, the previous version was restored using only the
registry. No source code was touched and no image was rebuilt:

```bash
docker stop student-ml-api && docker rm student-ml-api
docker run -d --name student-ml-api -p 5000:5000 ghcr.io/er0sama/student-ml-api:1.0.0
curl http://localhost:5000/health
```

```json
{"application":"student-ml-api","status":"healthy","version":"1.0.0"}
```

The container was replaced in well under a second. The 1.0.0 image was already
present in the registry and, in this case, cached locally.

### Why this beats a source-based deployment

A `git clone`, `pip install`, `python app.py` rollback is worse on every axis
that matters during an incident.

- **Speed.** Starting a container that already exists is close to instant.
  Cloning and resolving dependencies takes minutes, and you are spending them
  while the service is degraded.
- **Determinism.** The image is fixed bytes. `pip install` resolves versions at
  the moment you run it, so a rollback performed today can produce a different
  environment than the same commit produced last week. You may not get the thing
  you are trying to roll back to.
- **Number of failure points.** The source path can fail on network access to
  the package index, a yanked package, a compiler missing for a native
  dependency, or a Python version mismatch. Each is a new incident on top of the
  one being fixed.
- **What you are restoring.** Source is an instruction for producing an
  artifact. The image *is* the artifact, including the interpreter, the system
  libraries and the entrypoint. Rolling back source restores only one layer of
  the stack and trusts the rest to be reconstructed identically.
- **Verifiability.** A digest proves you are running the exact build that was
  tested. A commit hash proves only which recipe you followed.

The general principle: during an incident you want to *retrieve* a known-good
artifact, not *manufacture* one.

## Part 21 — Traceability chain for 1.1.0

Every link below was read from the repository and registry, not reconstructed.

```
Pull Request:   #2
Merge Commit:   a85bb7cb384280273de9cbc0f5e9a0e716ba54e4  (a85bb7c)
Git Tag:        v1.1.0
Release Run:    34440414643
Docker Image:   ghcr.io/er0sama/student-ml-api:1.1.0
Commit Tag:     ghcr.io/er0sama/student-ml-api:a85bb7c
Image Digest:   sha256:9ab72b3254e542f70db693217a2d68932b69612291bf543c59c67a5e72ad9c75
```

The chain is also traversable in reverse, which is the direction that matters
during an incident. Given only a running container:

```bash
docker inspect <container> --format '{{index .Config.Labels "org.opencontainers.image.revision"}}'
# a85bb7cb384280273de9cbc0f5e9a0e716ba54e4
```

That commit is the squashed merge of pull request #2, which carries the
description, the review and the CI results for the change. No registry lookup
and no external record are required, because the link travels inside the image.

For completeness, the same chain for 1.0.0:

```
Pull Request:   #1
Merge Commit:   fa0bcc7bd832a333147acb8a162795efc6290336  (fa0bcc7)
Git Tag:        v1.0.0
Release Run:    34440046729
Image Digest:   sha256:4ecd42add56374eb92285952695ac2fb74cdcf6f63678f3156548a86d9e0a5f6
```

## Evidence index

| Requirement | Where |
|---|---|
| Failed CI run | Run `34439612151`, pull request #2's predecessor branch |
| Successful CI run | Run `34439664727` |
| Successful release run | Runs `34440046729` (1.0.0) and `34440414643` (1.1.0) |
| Two documented pull requests | #1 and #2 |
| Release tags | `v1.0.0`, `v1.1.0` |
| Registry tags | `1.0.0`, `1.1.0`, `latest`, plus commit tags |
