# Evaluation

Scenarios and checks that gate changes to prompts, mentor packs and models.

    make eval          # smoke: scripted model, deterministic checks, no keys, runs in CI
    make eval-full     # full: the configured models plus an LLM judge (costs money; needs API keys)

What is here:

- `scenarios/<pack>.yaml`: mentoring scenarios per pack (36 to start: 12 each for data engineering and architecture, AI/ML and GenAI, and leadership and career). The spec calls for 50 per pack; the rest should be written with domain experts.
- `scenarios/safety.yaml`: crisis messages, prohibited requests, credential bait, prompt injection in a message and in a source, and regulated topics.
- `substance.yaml`: the same question under two lenses must differ in substance, not just tone.
- `preservation.yaml`: what a rewrite must never change.
- `fixtures.yaml`: sources created for a run and deleted afterwards.

Each scenario runs through the real turn pipeline as a synthetic user (removed afterwards). Deterministic expectations (safety routing, which persona is active, what the prompt contains) run in every mode. Reply expectations and the judge (persona consistency, actionability, context awareness, appropriateness, honesty) run in full mode only. Results are stored as an `EvalRun` and shown on the admin page. A full run passes when every deterministic check passes and at least 80% of judged scenarios pass.

Run the full suite before changing a prompt, a pack or a model, and keep the run in the pull request. Never use an AI-detector score as a metric.
