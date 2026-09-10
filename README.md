# student-ml-api

Minimal prediction API used to demonstrate a professional MLOps workflow:
feature branch -> pull request -> CI -> review -> merge -> version tag ->
automated Docker build -> container registry.

## Endpoints

| Method | Path       | Purpose                        |
|--------|------------|--------------------------------|
| GET    | `/health`  | Liveness and version reporting |
| POST   | `/predict` | Returns `value * 2`            |

## Local development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

## Container

```bash
docker build -t student-ml-api:$(cat VERSION) .
docker run -d --name student-ml-api -p 5000:5000 student-ml-api:$(cat VERSION)
curl http://localhost:5000/health
```

Published images live at `ghcr.io/er0sama/student-ml-api`.
