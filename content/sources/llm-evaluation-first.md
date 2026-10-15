---
slug: llm-evaluation-first
title: "Build the evaluation set before tuning an LLM application"
publisher: "Mentor platform (original draft)"
authority_tier: community
volatility: moderate
domain: genai
subtopic: "evaluation"
jurisdiction: global
licence: "Original text written for this project. Unreviewed draft."
reviewer: null
published_date: 2026-10-14
last_reviewed: null
---
# Build the evaluation set before tuning an LLM application

Without a test set, changes to prompts and models are guesses judged by a few memorable examples.

## What to build

Collect realistic inputs, including hard and unusual ones, from real use or from people who know the domain. For each, record what a good answer must contain or must avoid. Start with a few dozen and grow it as failures appear.

## How to score

Use checks that code can do exactly where possible: valid format, required fields, citations that exist, banned content absent. Use a model as judge for qualities such as helpfulness or tone, with a clear rubric, and check the judge against human ratings on a sample. Keep human review for a regular sample.

## Use it as a gate

Run the set on every change to prompts, models or retrieval. Compare against the previous version, look at cases that got worse and not only the average, and keep a record of results over time.

## Include safety cases

Test refusals, injection attempts in retrieved text, requests outside the intended scope, and cases where the right answer is "I don't know".
