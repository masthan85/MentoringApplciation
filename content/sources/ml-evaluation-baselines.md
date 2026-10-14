---
slug: ml-evaluation-baselines
title: "Evaluating a model honestly: baselines and leakage"
publisher: "Mentor platform (original draft)"
authority_tier: community
volatility: stable
domain: ai_ml
subtopic: "evaluation"
jurisdiction: global
licence: "Original text written for this project. Unreviewed draft."
reviewer: null
published_date: 2026-10-14
last_reviewed: null
---
# Evaluating a model honestly: baselines and leakage

A model score means little without something to compare it to and without confidence that the test data was truly unseen.

## Start with a baseline

Before building anything complex, measure a simple baseline: predicting the majority class, last period's value, or a rule a domain expert would write. If a complex model barely beats it, the extra complexity may not be worth the cost of running it.

## Split data the way the model will be used

If the model predicts the future, split by time, training on the past and testing on later data. If the model will see new customers, keep all records of one customer in the same split. Random splits that mix related records give optimistic scores.

## Leakage

Leakage is information in the features that would not be available at prediction time, such as a field filled in after the outcome. Signs include scores that look too good and a feature with surprising importance. Review each feature and ask when it becomes known.

## Choose metrics that match the decision

Accuracy misleads with imbalanced classes. Think about the cost of each kind of error, and report precision and recall, or a cost-based measure. Check performance across important subgroups, and check calibration if the probabilities will be used.
