---
slug: data-contracts
title: "Data contracts between producers and consumers"
publisher: "Mentor platform (original draft)"
authority_tier: community
volatility: moderate
domain: data_engineering
subtopic: "contracts"
jurisdiction: global
licence: "Original text written for this project. Unreviewed draft."
reviewer: null
published_date: 2026-10-14
last_reviewed: null
---
# Data contracts between producers and consumers

A data contract is an agreement about the data one team provides to another: its schema, meaning, quality expectations and how changes are communicated. It replaces silent breakage with a visible conversation.

## What a useful contract contains

The schema with types and which fields can be null. The meaning of each field in business terms. The expected freshness and volume. Quality rules that the producer commits to. A named owner and a way to contact them. A versioning rule: what counts as a breaking change, and how much notice consumers get.

## Making it real

A contract nobody enforces is a document. Validate data against the schema when it is produced, fail builds that break it, and alert the owner. Start with the few datasets that cause the most pain, not the whole estate.

## The human side

The hard part is agreeing ownership. Producers often feel that analytics is not their concern. Frame the contract around incidents that cost them time, and keep the first version small enough that they will keep it up to date.

## Evolving a contract

Add fields without breaking consumers. For a breaking change, publish a new version, run both for a deprecation period, and track who still uses the old one before retiring it.
