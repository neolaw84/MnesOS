# MnesOS AI Knowledge Map & Router

Welcome, autonomous agent. To maintain strict documentation integrity and prevent context window exhaustion, do not perform unguided file searches. Use your file reading tools to view only the specific markdown files listed below that directly match your assigned task domain. 

Before you finish any coding or development task, you must ensure the resulting branch remains mergeable under this repository's CI rules. That means you should validate the relevant local checks needed for a successful PR to `dev`, and you must not leave changes in a state that would fail the `main` promotion rules documented in `development/ci-cd.md`.

*(Note: Paths below are relative to the directory containing this index file).*

## 1. Project Structure & Workflows
If you need to locate where components live, or run tests/builds:
* **Directory Map & Architecture Layout**: Read `development/directory-map.md`
* **CI/CD Pipelines, Make Commands, & Validation Rules**: Read `development/ci-cd.md`

## 2. Design Philosophy & Engine Architecture
If you are implementing engine features, graph nodes, state routing, or interpreter logic:
* **AI Engineering Philosophy & Core Principles**: Read `design/philosophy.md`
* **Comprehensive Engine Architecture & Contracts**: Read `design/architecture.md`
* **Architecture Decision Records (ADR) & Rationale**: Read `design/decisions.md`
* **YARE Language Specification**: Read `yare-specification.md`
* **YARE-to-Tool Bridge Specification**: Read `design/yare-bridge.md`

## 3. Cartridge & User Guides
If you are crafting game content, writing YARE rules, or guiding player interactions:
* **Cartridge Developer Guide**: Read `guides/cartridge-developer-guide.md`
* **Player Guide**: Read `guides/player-guide.md`
