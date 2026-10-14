---
slug: architecture-decision-records
title: "Writing architecture decision records"
publisher: "Mentor platform (original draft)"
authority_tier: community
volatility: stable
domain: general
subtopic: "documentation"
jurisdiction: global
licence: "Original text written for this project. Unreviewed draft."
reviewer: null
published_date: 2026-10-14
last_reviewed: null
---
# Writing architecture decision records

An architecture decision record (ADR) is a short document that captures one significant decision, so that people later can see what was decided and why.

## A simple structure

Title and date. Status: proposed, accepted, or superseded by another record. Context: the problem and the forces at play. Decision: what you are doing, in plain words. Consequences: what becomes easier, what becomes harder, and what you will watch.

## Good habits

Write one decision per record. Include the options you rejected and why, because that is what people most want later. Keep it to one or two pages. Store records with the code, in version control, so they change with it. Never edit an accepted record to change history; write a new one that supersedes it.

## Writing for the reader

The reader may be a new colleague, or you in a year. Avoid jargon the team has not agreed on. State risks honestly. If the decision depends on an assumption, say so, so it can be checked later.
