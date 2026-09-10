import os

from flask import Flask, jsonify, request

APP_NAME = "student-ml-api"

# The served model is versioned independently of the application, so that a
# model swap and a code change can be told apart after the fact.
MODEL_VERSION = "model-1"

with open(os.path.join(os.path.dirname(__file__), "VERSION")) as fh:
    VERSION = fh.read().strip()

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify(
        status="healthy",
        application=APP_NAME,
        application_version=VERSION,
        model_version=MODEL_VERSION,
    )


@app.post("/predict")
def predict():
    payload = request.get_json(silent=True)

    # A JSON array or string is parseable but is not a request object.
    if not isinstance(payload, dict):
        return jsonify(error="request body must be a JSON object"), 400

    if "value" not in payload:
        return jsonify(error="missing required field: value"), 400

    value = payload["value"]
    # bool is a subclass of int, so it has to be rejected explicitly
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return jsonify(error="field 'value' must be a number"), 400

    return jsonify(input=value, prediction=value * 2)


if __name__ == "__main__":
    # 0.0.0.0 so the app is reachable from outside the container
    app.run(host="0.0.0.0", port=5000)
