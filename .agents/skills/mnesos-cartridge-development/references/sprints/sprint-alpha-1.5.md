# MnesOS Alpha-1.5 Sprints Schedule

This document maps out the sprints for the MnesOS Alpha-1.5 development cycle. Each sprint is structured to deliver cohesive, testable progress.

---

## Sprint 1: JavaScript YARE Foundation & Minigame Discovery
**Focus:** Build the core JavaScript YARE syntax and static AST compilation on the backend, update database schemas to store plain-text JS next to compiled specs, and expose minigame configurations in the builder UI.

*   **[MnesOS-260516-12]** YARE – JavaScript Authoring Specification (yare.js)
*   **[MnesOS-260525-05]** Backend – Integrate JS-to-YAML Compilation into Ingestion Pipeline
*   **[MnesOS-260525-07]** Database/Backend – Schema Update for JavaScript YARE (Drafts & CartridgeVersions)
*   **[MnesOS-260525-01]** Frontend – YARE JS Developer Playpen/Testing Pane
*   **[MnesOS-260525-06]** Engine/Frontend – Minigame Registry Discovery and Parameter Directory

---

## Sprint 2: Developer IDE GUI Enhancements
**Focus:** Construct the split-pane builder interface with syntax highlighting, switchable formats (YAML/JS), single-pane download functionality, version publishing to the database, and draft/ZIP exports.

*   **[MnesOS-260507-08]** Builder UI – IDE-lite Split-Pane Layout
*   **[MnesOS-260525-02]** Frontend – Builder UI 4-Pane Enhancements: Format Switching & Syntax Highlighting
*   **[MnesOS-260507-11]** Builder Persistence – Versioned Drafts & ZIP Export
*   **[MnesOS-260525-03]** Frontend – Individual Pane File Export
*   **[MnesOS-260525-04]** Frontend/Backend – Cartridge Version Saving UI and Endpoint

---

## Sprint 3: Gameplay Mini-game Expansion
**Focus:** Finalize standard minigame wrappers, implement graph-level input routing for pending interaction gates, and introduce two new frontend-only mini-games: Articulation Scramble (speech/dialogue) and Reflex Dial (QTE actions/combat).

*   **[MnesOS-260516-10]** Graph – Input Router Node for Pending States
*   **[MnesOS-260525-10]** Frontend – "Articulation Scramble" Speaking Mini-game
*   **[MnesOS-260525-11]** Frontend – "Reflex Dial" Action Mini-game

---

## Sprint 4: Agentic Generation Console ("I'm Feeling Lucky")
**Focus:** Build the multi-agent builder backend (specialist models and translators) and connect them to a focused "I'm Feeling Lucky" developer console where full 4-file cartridges are generated from a single text requirements document.

*   **[MnesOS-260507-09]** Builder Backend – Architect & Specialist Multi-Agent System
*   **[MnesOS-260507-10]** Builder Tools – YARE Translator & Auto-Validator
*   **[MnesOS-260525-08]** Frontend – "I'm feeling Lucky" Console UI
*   **[MnesOS-260525-09]** Backend – "I'm feeling Lucky" Cartridge Generator Agent
