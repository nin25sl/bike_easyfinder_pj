---
title: ADR-003 Infrastructure Provider（選定待ち）
published: 2026-10-04
tags: [adr, infrastructure, pending]
category: ADR
draft: true
---

# ADR-003 Infrastructure Provider（選定待ち）

## 状態

Pending。ローカル縦断MVP完了後に、見積と運用条件を比較して人が承認する。

## 必須条件

- 日本から低遅延なリージョン。
- managed Postgres 16 + PostGIS、保存時暗号化、TLS。
- staging/productionのDB・domain・secret完全分離。
- 日次backup 7世代以上、月次staging restore試験、削除tombstoneの再適用。
- container deployment、health check、structured logs、p95 latency/error/quota監視。
- 月額目標1万円以内。費用alertを80%と100%に設定し、自動の有料上限引き上げを禁止。
- secret managerからApple Maps access tokenを注入でき、開発端末やCIログへ露出しない。

## 比較時に記録する値

月額税込見積、region、PostGIS version、backup/restore RPO・RTO、egress、停止時料金、log保持、削除保証、障害窓口、IaC方式を同じ表で比較する。選定前にproduction相当構成を作らない。

