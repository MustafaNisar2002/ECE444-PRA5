import os
import logging
import threading
import pickle
from typing import Optional
from flask import Flask, request, jsonify, render_template_string

# ---- Flask app (EB Procfile expects "application:application") ----
application = Flask(__name__)

# ---- Logging ----
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---- Artifact paths (next to this file by default) ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.getenv("MODEL_PATH") or os.path.join(BASE_DIR, "basic_classifier.pkl")
VECTORIZER_PATH = os.getenv("VECTORIZER_PATH") or os.path.join(BASE_DIR, "count_vectorizer.pkl")

logger.info("CWD: %s", os.getcwd())
logger.info("Resolved MODEL_PATH: %s", MODEL_PATH)
logger.info("Resolved VECTORIZER_PATH: %s", VECTORIZER_PATH)

# ---- Globals ----
_loaded_model: Optional[object] = None
_vectorizer: Optional[object] = None
_artifact_lock = threading.Lock()

def _load_artifacts_once() -> None:
    """Lazily load model and vectorizer once per process."""
    global _loaded_model, _vectorizer
    if _loaded_model is not None and _vectorizer is not None:
        return
    with _artifact_lock:
        if _loaded_model is None or _vectorizer is None:
            logger.info("Loading artifacts...")
            if not os.path.exists(MODEL_PATH) or not os.path.exists(VECTORIZER_PATH):
                raise FileNotFoundError("Required .pkl artifacts are missing.")
            with open(MODEL_PATH, "rb") as mf:
                _loaded_model = pickle.load(mf)
            with open(VECTORIZER_PATH, "rb") as vf:
                _vectorizer = pickle.load(vf)
            logger.info("Artifacts loaded.")

def _predict_text(text: str) -> int:
    """Run inference and return the predicted class (0/1)."""
    _load_artifacts_once()
    X = _vectorizer.transform([text])
    y = _loaded_model.predict(X)
    val = y[0]

    # If it's a numpy scalar, unwrap it
    if hasattr(val, "item"):
        val = val.item()

    # If the model returns string labels like "FAKE"/"REAL"
    if isinstance(val, str):
        label = val.upper()
        if label == "FAKE":
            return 1
        if label == "REAL":
            return 0
        # unexpected label
        raise ValueError(f"Unexpected string label from model: {val!r}")

    # Otherwise assume it's already numeric-ish
    return int(val)


# Eager-load in the background (non-blocking)
def _eager_load_background():
    try:
        _load_artifacts_once()
    except Exception as e:
        logger.warning("Background eager load failed: %s", e, exc_info=True)

threading.Thread(target=_eager_load_background, daemon=True).start()

# ---- Simple demo page ----
DEMO_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Fake News Detector — Demo</title>
    <style>
      body { font-family: system-ui, -apple-system, Arial, sans-serif; margin: 2rem; max-width: 720px; }
      textarea { width: 100%; height: 10rem; }
      .card { padding: 1rem; border: 1px solid #ddd; border-radius: 12px; }
      .result { margin-top: .75rem; font-weight: 600; }
      .error { color: #b00020; }
    </style>
  </head>
  <body>
    <h1>Fake News Detector (Demo)</h1>
    <div class="card">
      <form method="post">
        <label for="text">Paste text to classify:</label><br/>
        <textarea id="text" name="text" placeholder="Paste news text here...">{{ text or '' }}</textarea><br/><br/>
        <button type="submit">Predict</button>
      </form>
      {% if pred is not none %}
        <div class="result">Prediction: {{ 'Fake (1)' if pred == 1 else 'Real (0)' }}</div>
      {% endif %}
      {% if error %}
        <div class="result error">Error: {{ error }}</div>
      {% endif %}
    </div>
    <p style="margin-top:1rem;">API: POST JSON to <code>/predict</code> with <code>{"text": "..."}</code>.</p>
  </body>
</html>"""

# ---- Routes ----
@application.get("/")
def health():
    return jsonify({
        "status": "ok",
        "model_loaded": bool(_loaded_model is not None and _vectorizer is not None),
        "model_path": MODEL_PATH,
        "vectorizer_path": VECTORIZER_PATH,
    })

@application.route("/demo", methods=["GET", "POST"])
def demo():
    pred = None
    error = None
    text = ""
    if request.method == "POST":
        text = (request.form.get("text") or "").strip()
        if not text:
            error = "Please provide some text."
        else:
            try:
                pred = _predict_text(text)
            except FileNotFoundError:
                error = "Model artifacts not found on server."
            except Exception as e:
                logger.exception("Demo inference error: %s", e)
                error = "Inference failed."
    return render_template_string(DEMO_HTML, pred=pred, error=error, text=text)

@application.post("/predict")
def predict():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "`text` is required and must be non-empty."}), 400
    try:
        label = _predict_text(text)
        return jsonify({"prediction": label}), 200
    except FileNotFoundError:
        return jsonify({"error": "Model artifacts not found on server."}), 503
    except Exception as e:
        logger.exception("Inference error: %s", e)
        return jsonify({"error": "Inference failed."}), 500

if __name__ == "__main__":
    # Local dev run; in EB, Gunicorn (from Procfile) will host the app
    port = int(os.getenv("PORT", "8080"))
    application.run(host="0.0.0.0", port=port, debug=False)
