# Cover Storage — Index

## Overview

Локальное хранение обложек по metacritic_slug; сбой скачивания не валит карточку; путь для API `/api/v1/media/covers/{slug}`. Родитель: [Phase_3_catalog-covers](../INDEX.md).

## Goals

### Business

- **Primary Business Objective**: UI не зависит от TTL CDN Metacritic.
- **Success Metrics**: Файл на volume или cover_url null.
- **Parent Alignment**: scraping-resilience обложки.

### Technical

- **Primary Technical Objective**: packages/adapters/media CoverStorage.
- **Implementation Scope**: Отдача HTTP — Epic 4 API; здесь save/load filesystem.
- **Quality Standards**: Нет SSRF (не скачивать произвольный URL из query API).

## Status

- [ ] Not Started
- [ ] In Progress
- [x] Completed
- [ ] Blocked

## Dependencies

- media.* settings; Catalog вызывает save.

## Deliverables

CoverStorage интерфейс, volume path, тесты битых байт, ключ slug.
