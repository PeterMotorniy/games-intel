# Game Card — Index

## Overview

Страница карточки игры: полный набор полей, резюме, летсплей-блок (частичный ок), похожие с навигацией. Родитель: [Phase_3_web-catalog](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: Полная информация из ТЗ на одном экране.
- **Success Metrics**: Клик similar открывает другую карточку; нет self.
- **Parent Alignment**: task.md карточка + similar.

### Technical

- **Primary Technical Objective**: pages/game + SimilarList; опциональный invalidate.
- **Implementation Scope**: Монитор не здесь.

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- GET /games/{slug}; list navigation.

## Deliverables

Card page; similar links; partial hydration UI; browser verify.
