# student-ml-api

A small prediction API used to build out a full release pipeline: feature branch,
pull request, CI, review, merge, version tag, automated Docker build, published
image.

The prediction is `value * 2`. The point is everything around it.

## Endpoints

| Method | Path       | Returns                                    |
|--------|------------|--------------------------------------------|
| GET    | `/health`  | Status, application version, model version |
| POST   | `/predict` | `{"input": n, "prediction": n * 2}`        |

```bash
curl http://localhost:5000/health
{"application":"student-ml-api","application_version":"1.1.0","model_version":"model-1","status":"healthy"}

curl -X POST http://localhost:5000/predict -H 'Content-Type: application/json' -d '{"value":21}'
{"input":21,"prediction":42}
```

`/predict` returns 400 for a missing field, a non-numeric value, or a body that
is not a JSON object.

## How changes reach main

Nothing is pushed to `main` directly. Branch protection rejects it, including for
the repository owner, and that was tested rather than assumed.

```
feature branch -> pull request -> CI -> review -> squash merge -> tag -> release
```

Two workflows, deliberately separate:

- **`ci.yml`** runs on every pull request. Tests, then builds the image and
  smoke tests the running container. It never pushes anything. A pull request is
  a proposal, not a release.
- **`release.yml`** runs only on a `v*.*.*` tag. Tests again, then builds once
  and publishes. The version is derived from the tag name, so `v1.1.0` becomes
  `1.1.0`. The build fails if the tag disagrees with the `VERSION` file.

Squash merge, so one feature is one commit on `main`. The development history
stays readable in the pull request.

## Releases

Images are published to `ghcr.io/er0sama/student-ml-api`, public.

| Version | Tags                              | Merge commit | Pull request |
|---------|-----------------------------------|--------------|--------------|
| 1.0.0   | `1.0.0`, `fa0bcc7`                | `fa0bcc7`    | #1           |
| 1.1.0   | `1.1.0`, `latest`, `a85bb7c`      | `a85bb7c`    | #2           |

Every image also carries its commit in an OCI label, so a running container can
be traced back to source without consulting the registry:

```bash
docker inspect <container> --format '{{index .Config.Labels "org.opencontainers.image.revision"}}'
```

## Run it

```bash
docker run -d --name student-ml-api -p 5000:5000 ghcr.io/er0sama/student-ml-api:1.1.0
curl http://localhost:5000/health
```

Rolling back is pulling the older tag. No rebuild, no source, no dependency
install:

```bash
docker rm -f student-ml-api
docker run -d --name student-ml-api -p 5000:5000 ghcr.io/er0sama/student-ml-api:1.0.0
```

The 1.0.0 image was untouched when 1.1.0 shipped, which is the whole reason this
works.

## What broke, and why

Four failures, documented because the interesting part of a pipeline is what it
catches.

**Tests passed locally, failed in CI.** The first CI run never ran a test. It
died collecting them with `ModuleNotFoundError: No module named 'app'`. Locally
we had been running `python -m pytest`, which quietly puts the working directory
on the path. CI runs bare `pytest`, which does not. Fixed with a `pytest.ini`
that sets `pythonpath`, so both invocations behave the same. A local pass proves
less than it appears to.

**A test asserted the wrong thing, on purpose.** Changed the health assertion to
expect `"wrong"`, pushed, and the pull request went red with
`assert 'healthy' == 'wrong'`. The merge button was blocked. The Docker job did
not even run, because it depends on the test job. Restored the assertion and it
went green.

**The Docker build failed while every test passed.** Added `COPY tests/ ./tests/`
to the Dockerfile. `tests` is listed in `.dockerignore`, so it is not in the
build context and the copy cannot succeed. The pull request failed on the build
job alone, with the test job green above it, which is the clearest possible proof
that the two gates are independent. Locally the error names the cause outright:

```
COPY failed: file not found in build context or excluded by .dockerignore: stat tests/: file does not exist
```

CI uses BuildKit and phrases it less helpfully as `"/tests": not found`, which is
worth knowing before you spend ten minutes checking whether the directory exists.

**The container ran fine and served nothing.** Bound the app to `127.0.0.1`
instead of `0.0.0.0`. The container stayed up, the port mapping was correct,
`docker ps` looked healthy, and `curl` from the host got a connection reset.
Inside a container, loopback is the container's own loopback. Requests arriving
through the published port hit the external interface, where nothing was
listening. The only visible clue was one line in `docker logs`. Running the same
request from inside the container succeeded, which is what confirmed it.

A fifth one, found by accident and worth more than the others: while reproducing
the bind failure, the broken container was mapped to a port another container
already held. Docker refused to start it, and the `curl` that followed returned a
healthy response from the old container. A pass against the wrong process looks
exactly like a pass.

## Repository

```
app.py                        Flask application
tests/test_app.py             Five tests
Dockerfile                    Pinned base, deps before source, gunicorn
.dockerignore                 Keeps .git, tests and caches out of the image
VERSION                       Single source of the version number
pytest.ini                    Import path, so bare pytest works
.github/workflows/ci.yml      Pull request validation
.github/workflows/release.yml Tagged release and publish
REPORT.md                     Assignment write-up
VIVA.md                       Viva question answers
```

## Local development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest
.venv/bin/python app.py
```
