# 0007. Knowledge, voice and fingerprint: decisions made in Phase 2

Date: 2026-10-14
Status: accepted

## Context

Phase 2 adds the Mentor Encyclopedia with cited retrieval, the Natural Voice writing layers, the Writing Fingerprint and Studio drafting. These choices shape trust in the product.

## Decisions

**Content is untrusted data, and a human decides about anything suspicious.** Every document is sanitised on ingestion: invisible characters, hidden HTML comments and active markup are removed, and anything that could close one of our prompt delimiters is escaped. A scan then looks for phrases that read as instructions to a model. A document with such findings stays a draft, and an admin must tick an acknowledgement to activate it. A filter cannot tell a good article about prompt injection from an attack, so it does not try. Changed content returns to draft.

**Shared content is admin-write, enforced by the database.** `sources` and `chunks` have row-level security: everyone signed in reads active sources, and only a transaction marked admin (`app.is_admin`, set only by code that has checked the role, or by trusted jobs) can write. Drafts and retired sources are invisible to ordinary sessions. In production the runtime role should lose write access on these tables once an admin role exists (Phase 4).

**Authority is honest.** Source metadata includes an authority tier, volatility, jurisdiction, licence and reviewer. The 15 starter documents are original, unreviewed drafts, so they are tagged `community`, the lowest weight, until an expert reviews them and promotes them. The UI labels them "Draft, not yet expert-reviewed".

**Retrieval is hybrid and fused.** Full-text search (an OR query over significant words) and pgvector cosine search each return 30 candidates, merged by reciprocal rank fusion, re-ranked, and weighted by authority and a freshness factor that decays at a rate set by volatility. A vector hit must reach a minimum similarity, no more than three chunks come from one source, and the top six go to the model. Embeddings come from the `embedding` route, which only OpenAI serves today (Anthropic has no embeddings API). If it is unavailable, ingestion stores chunks without vectors, retrieval falls back to full text, and the admin page can embed them later.

**The cross-encoder reranker is optional.** The spec asked for one in the worker. It pulls in PyTorch, which is heavy for a service that has no corpus yet. The default is a lightweight keyword reranker behind the same interface; set `RERANKER=cross_encoder` and install `sentence-transformers` to switch. Reranking runs in the API process because it is on the answer's critical path.

**Citations are checked, not trusted.** Retrieved text is wrapped as delimited data with ids such as S1. The reply is checked afterwards for ids that were never supplied. Time-sensitive questions instruct the model to state an as-of date, which the API also returns.

**Natural Voice is a quality aid, and thresholds live in one file.** `voice/config.yaml` holds channel norms, modes and every lint threshold. The lint is deterministic and takes milliseconds. Question restatement and redundant conclusion use lexical overlap, not embedding similarity as the spec suggested, to keep the lint free of API calls. The lint reports the sentences that failed, so a rewrite can be targeted. It is never an AI-detector score and is not used as one.

**A rewrite must survive three checks or the original ships.** First, numbers, versions, dates, URLs, code blocks and mid-sentence names must be unchanged. Second, a small model judges whether any claim was lost or added, and the check fails closed if it cannot answer. Third, the lint must actually improve. A known limit: a new name at the very start of a sentence cannot be told from an ordinary capitalised word by the deterministic check, so the claim-level judge is what catches it. Safety, crisis and refusal text is never rewritten.

**Drafts check themselves for invention.** Studio warns when a draft contains numbers, dates, versions or links the user never supplied. Lint on drafts ignores the brief, because a draft naturally echoes it.

**The fingerprint describes style and never copies it.** Writing samples are encrypted with the same separate key as sensitive memories. The user must confirm each sample is their own writing. Features are stylometric and numeric. The voice card is built from a template, and the user can replace it with their own words. Edits to Studio drafts feed the fingerprint only with consent. The whole fingerprint can be deleted as one unit. Similarity to the user's style is only reported when the text is long enough to measure.

## Consequences

An admin has real work to do: read flagged sources and review the starter content before the product leans on it. Embeddings depend on an OpenAI key until a second embeddings provider is added. The lint's English-language heuristics will need tuning on real writing, and the evaluation suite (Phase 3) is where that tuning should be measured.
