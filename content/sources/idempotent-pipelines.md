---
slug: idempotent-pipelines
title: "Making data pipelines safe to rerun"
publisher: "Mentor platform (original draft)"
authority_tier: community
volatility: stable
domain: data_engineering
subtopic: "reliability"
jurisdiction: global
licence: "Original text written for this project. Unreviewed draft."
reviewer: null
published_date: 2026-10-14
last_reviewed: null
---
# Making data pipelines safe to rerun

A pipeline is idempotent when running it twice for the same input leaves the same result as running it once. It is the property that turns a 3am failure into a retry instead of a clean-up.

## Why it matters

Jobs fail halfway, schedulers retry, and people rerun a day to fix a bug. If a rerun appends the same rows again, totals double and nobody notices until a report is wrong.

## Common techniques

Write to a partition or a date range and replace it as a whole, rather than appending. Use a merge (upsert) keyed on a stable business key when rows can be updated. Keep raw inputs immutable so any output can be rebuilt. Write to a staging location first and swap it in when the job has succeeded, so readers never see a half-written result.

## Things that quietly break it

Using the current time inside the transformation, so a rerun produces different values. Generating random identifiers during the load. Reading from a source that has changed since the first run without recording the extract time. Deleting and reloading without a transaction, which exposes an empty table to readers.

## Backfills

Design for backfills from the start: parameterise the job by a date range, make the output for each range independent, and test a backfill on a copy before running it in production. Check the result by reconciling row counts and key totals against the source.
