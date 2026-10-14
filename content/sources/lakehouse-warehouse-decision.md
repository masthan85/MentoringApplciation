---
slug: lakehouse-warehouse-decision
title: "Choosing between a warehouse, a lakehouse and something simpler"
publisher: "Mentor platform (original draft)"
authority_tier: community
volatility: moderate
domain: data_architecture
subtopic: "platform choice"
jurisdiction: global
licence: "Original text written for this project. Unreviewed draft."
reviewer: null
published_date: 2026-10-14
last_reviewed: null
---
# Choosing between a warehouse, a lakehouse and something simpler

Platform choices are expensive to reverse, so start from the problem, not the product category.

## Questions that decide it

What data volumes and types are involved, today and in three years? Is the work mostly SQL analytics, or also machine learning and unstructured data? Who will build and run it, and what skills do they have? What are the governance, security and residency requirements? What does the organisation already pay for and operate well?

## Rough guidance

A managed cloud warehouse suits mostly structured data and SQL-centred teams who want low operational effort. A lakehouse, with open table formats on object storage, suits a mix of analytics and machine learning, or a need to avoid locking data into one engine. For modest data volumes, a well-run relational database may be enough, and complexity you do not need has a running cost in people.

## Compare total cost of ownership

Include compute, storage, egress, licences, the people to operate it and the cost of training. Model a realistic workload, not the vendor's example. Ask what it would take to leave in two years.

## Record the decision

Write an architecture decision record with the options considered, the reasons for the choice and what would make you revisit it.
