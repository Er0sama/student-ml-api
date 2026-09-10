# Assignment Report — student-ml-api

Repository: `https://github.com/Er0sama/student-ml-api`
Registry: `ghcr.io/er0sama/student-ml-api`

Viva answers are in [VIVA.md](VIVA.md).

---

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

*(Completed as the failures are reproduced. See below.)*

