---
slug: data-quality-checks
title: "Data quality checks that earn their keep"
publisher: "Mentor platform (original draft)"
authority_tier: community
volatility: moderate
domain: data_engineering
subtopic: "quality"
jurisdiction: global
licence: "Original text written for this project. Unreviewed draft."
reviewer: null
published_date: 2026-10-14
last_reviewed: null
---
# Data quality checks that earn their keep

Checks are most useful where bad data first enters your control and where a wrong number would be most costly. A hundred generic checks that nobody reads are worth less than ten that block a bad load.

## What to check

Freshness: did the data arrive when expected? Volume: is the row count within a normal range for this day? Uniqueness of keys. Not-null on fields the business depends on. Referential integrity between related tables. Accepted values for categories. Reconciliation: do totals match the source system within an agreed tolerance?

## Where to put them

At ingestion, to catch problems from producers early. After key transformations, to catch your own bugs. On the final tables people use, where a failure should alert the owner and, for critical data, stop publication.

## Make failures actionable

Every check needs an owner, a severity and a note on what to do when it fails. Separate checks that block a load from checks that only warn. Track failures over time: a check that fails every week is either wrong or pointing at a real upstream problem that needs a conversation with the producer.

## Tests are not the same as monitoring

Tests run on known data when code changes. Monitoring watches live data for drift. You need both.
