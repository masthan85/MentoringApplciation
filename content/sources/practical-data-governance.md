---
slug: practical-data-governance
title: "Starting data governance without a big programme"
publisher: "Mentor platform (original draft)"
authority_tier: community
volatility: moderate
domain: data_architecture
subtopic: "governance"
jurisdiction: global
licence: "Original text written for this project. Unreviewed draft."
reviewer: null
published_date: 2026-10-14
last_reviewed: null
---
# Starting data governance without a big programme

Governance works when it helps people use data with confidence. It fails when it is a set of documents with no owners.

## Begin with ownership

Name an accountable owner for each important dataset: someone who can say what it means and who decides who may use it. Without owners, every other control stalls.

## A small set of practices

Keep a catalogue of the critical datasets with owner, description, sensitivity and where they come from. Classify data by sensitivity and apply simple rules for each class. Record lineage for the numbers the business relies on, so a wrong figure can be traced. Define retention for personal data and delete on schedule.

## Fit into delivery

Attach checks to the way teams already work: review in pull requests, tests in pipelines, access requests through the existing tools. Controls that need a separate process get bypassed.

## Measure whether it helps

Track how long it takes to find and get access to data, how often a dataset has a named owner, and how many incidents trace back to unclear definitions.
