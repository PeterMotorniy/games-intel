# Embedding Hybrid kNN — Index

## Overview

Канонический hash, вызов embedding API, формула hybrid, запись similar_games для одной игры. Родитель: [Phase_1_similarity-worker](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Похожесть не только cosine, но платформы/жанр/дата.
- **Success Metrics**: Тест формулы на фикстурах векторов.
- **Parent Alignment**: similarity.md hybrid table.

### Technical

- **Primary Technical Objective**: embedding adapter HTTP; SQL Jaccard; release tau.
- **Implementation Scope**: Режимы inline_all vs incremental — следующий шаг, здесь вычислитель score + upsert embedding.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- embeddings settings; games data.

## Deliverables

Hash SHA-256 канона+model+vector_dim; scorer; fake embed tests.
