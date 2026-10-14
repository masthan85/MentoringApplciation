---
slug: slowly-changing-dimensions
title: "Modelling history with slowly changing dimensions"
publisher: "Mentor platform (original draft)"
authority_tier: community
volatility: stable
domain: data_architecture
subtopic: "modelling"
jurisdiction: global
licence: "Original text written for this project. Unreviewed draft."
reviewer: null
published_date: 2026-10-14
last_reviewed: null
---
# Modelling history with slowly changing dimensions

In dimensional modelling, a dimension describes things like customers or products. Their attributes change, and you decide whether reports should show the world as it is now or as it was at the time.

## The common types

Type 1 overwrites the old value. It is simple and loses history, which is fine for corrections. Type 2 adds a new row for each change, with valid-from and valid-to dates and a current flag, so facts join to the attribute as it was at the time. Type 3 keeps a limited history in extra columns, such as the previous value.

## Choosing

Ask which questions need history. If the business asks how many customers were in a region at the end of last year, you need type 2 on region. If an attribute is only ever shown as current, type 1 is enough. Keep type 2 for the few attributes that need it, because every extra tracked attribute multiplies rows and complexity.

## Practical points

Use a surrogate key for each version of a row, and keep the business key alongside it. Make the load idempotent, so a rerun does not create duplicate versions. Test for overlapping date ranges and gaps. Late-arriving changes need a plan, because they mean rewriting validity ranges.
