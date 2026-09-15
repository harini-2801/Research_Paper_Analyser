# Deployment

Written for: whoever is deploying this, following it step by step.

The system is two pieces. The **API** does the analysis; the **web interface**
displays it. They can run together or apart.

| Setup | What works | What you need |
|---|---|---|
| Vercel alone | Browsing the saved 30-paper analysis | Nothing |
| `rpra serve` locally | Everything | Python 3.10+ |
| Render + Vercel | Everything, publicly | A free Render account |

---

## About keys

**No API key is required.** The default extraction backend is heuristic: rules
and a gazetteer, running offline with no account and no credentials.

An `OPENAI_API_KEY` is optional, and it buys exactly two things: LLM-based
entity extraction as an alternative to the rules, and generated explanations on
contradictions and gaps. Everything else — ingestion, the knowledge graph,
relationship scoring, contradiction detection, gap discovery, the reports — runs
without it.

If you do use one, it is **yours to obtain** from
<https://platform.openai.com/api-keys>, it is billed to your account, and it is
set as an environment variable on the **server**. It is never typed into the web
page, and the page never sends it anywhere.

---

## Deploy the API on Render

### 1. Create the service

From the Render dashboard: **New → Web Service**, then connect the GitHub
repository `harini-2801/Research_Paper_Analyser`.

Render reads `render.yaml` from the repository and fills most of this in. If you
are configuring by hand, these are the settings:

| Setting | Value |
|---|---|
| Name | `rpra-api` (anything) |
| Language / Runtime | **Python 3** |
| Branch | `main` |
| Root Directory | *(leave blank)* |
| Build Command | `pip install --upgrade pip && pip install -e .` |
| Start Command | `uvicorn rpra.server:app --host 0.0.0.0 --port $PORT --workers 1` |
| Instance Type | **Free** is enough |
| Health Check Path | `/api/status` |

### 2. Environment variables

| Key | Value | Required |
|---|---|---|
| `PYTHON_VERSION` | `3.11.9` | Yes |
| `PIP_NO_CACHE_DIR` | `1` | Recommended — keeps the build disk small |
| `OPENAI_API_KEY` | your key | **No.** Only for LLM extraction |

### 3. Deploy and check

The first build takes roughly three to five minutes. When it finishes, open:

```
https://<your-service>.onrender.com/api/status
```

A JSON response with `"status": "idle"` means the API is up.

### Why the build command installs so little

`pip install -e .` installs the **core** dependencies only — about 174 MB.
The transformer stack (`torch`, `transformers`, `sentence-transformers`) is
roughly 2.5 GB installed and does not fit a free instance.

It is genuinely optional. Each use is lazily imported behind a fallback:

| Missing | Falls back to | Consequence |
|---|---|---|
| `sentence-transformers` | Deterministic TF-IDF embeddings | Slightly coarser similarity |
| `transformers` | Numeric claim comparison | No NLI stance signal |
| `openai` | Heuristic extraction | No LLM extraction or explanations |

Measured with exactly this install on the 30-paper corpus: full pipeline in
13 seconds, all 435 document pairs scored.

To use the transformer models instead, change the build command to
`pip install -e ".[ml]"` and move to an instance with at least 2 GB RAM.

### Two things to know about the free plan

**It sleeps.** After 15 minutes idle the instance spins down, and the next
request takes 30–60 seconds to wake it. The web interface will look
unresponsive during that wake-up.

**The filesystem is ephemeral.** PDFs you upload and reports you generate are
lost when the instance restarts. Attach a disk (paid plans) if the corpus needs
to survive.

---

## Point the web interface at it

The Vercel deployment serves the interface only, which is why it shows a saved
analysis and disables **Run analysis**.

Either:

- Click **Connect backend** in the banner and paste your Render URL, or
- Append it to the address: `?api=https://your-service.onrender.com`

CORS is already open on the API, so no configuration is needed on either side.

---

## Or just run it locally

Simplest option, and everything works:

```bash
git clone https://github.com/harini-2801/Research_Paper_Analyser.git
cd Research_Paper_Analyser
pip install -e .

python scripts/make_sample_corpus.py   # or drop your own PDFs into data/papers
rpra serve                             # http://localhost:8000
```

`rpra serve` hosts the API and the interface together, so there is nothing to
connect.

For the transformer models and the test suite:

```bash
pip install -e ".[ml,dev]"
```

---

## Troubleshooting

**Build fails, out of memory or disk.** The build command is installing the ML
extras. It should be `pip install -e .` with no bracket suffix.

**`/api/status` returns 404.** The start command is wrong. It must be
`uvicorn rpra.server:app`, not `main:app` or `app:app`.

**Interface still says "demo data" after connecting.** The API did not respond.
Open `<your-url>/api/status` directly — if it hangs, the free instance is waking
up; wait a minute and retry.

**"Run analysis" reports no PDFs.** The corpus is empty. Upload PDFs through the
interface first; on the free plan they will not survive a restart.

**Everything runs but finds nothing.** Check the backend selector in the left
rail is on *Heuristic* unless you have set `OPENAI_API_KEY` and installed the
`llm` extra.
