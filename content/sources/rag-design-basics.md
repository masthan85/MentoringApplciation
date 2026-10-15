---
slug: rag-design-basics
title: "Designing retrieval-augmented generation that stays accurate"
publisher: "Mentor platform (original draft)"
authority_tier: community
volatility: moderate
domain: genai
subtopic: "retrieval"
jurisdiction: global
licence: "Original text written for this project. Unreviewed draft."
reviewer: null
published_date: 2026-10-14
last_reviewed: null
---
# Designing retrieval-augmented generation that stays accurate

Retrieval-augmented generation gives a model relevant passages at question time instead of relying on what it memorised.

## Quality starts with the content

Use sources you trust and keep their dates and owners. Chunk by meaning, such as headings, rather than at arbitrary lengths. Remove duplicates and out-of-date material.

## Retrieve well

Combine keyword search with vector search, because each finds things the other misses. Filter by metadata such as topic and jurisdiction. Retrieve more candidates than you need and re-rank them, then pass only the best few to the model.

## Keep the model honest

Mark retrieved text as data, not instructions. Ask the model to cite the passages it uses, and check that each citation points to something that was really supplied. Tell it to say so when the material does not answer the question.

## Measure retrieval separately

Check whether the right passage was retrieved before judging the final answer. Many wrong answers are retrieval failures, and fixing them is cheaper than changing the model.

## Watch for stale content

Give each source a review date and a volatility. Prefer recent sources for fast-changing topics and tell the user the date of what the answer relies on.
