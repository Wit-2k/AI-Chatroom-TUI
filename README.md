# AI Discussion Room

A multi-agent AI chatroom where configurable AI personas discuss a user-defined topic in turn, then produce a structured summary. Built on prompt engineering and a state-machine orchestration model.

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Tech Stack](#tech-stack)
4. [Core Technical Challenges](#core-technical-challenges)
5. [MVP Evolution Roadmap](#mvp-evolution-roadmap)
6. [4-Week Development Roadmap](#4-week-development-roadmap)
7. [AI-Assisted Development Tooling](#ai-assisted-development-tooling)
8. [Risk Assessment](#risk-assessment)

---

## Overview

**Core flow:** User inputs a topic → system dynamically configures N AI personas → a discussion-flow engine schedules turn-based speech → after a set number of rounds, a summarization engine fires → final structured conclusion is output.

**Technical essence:** A multi-agent orchestration system driven by prompt engineering and a state machine.

---

## System Architecture

The system follows a frontend/backend separation model with four distinct layers:

### 1. Presentation Layer (Frontend)

- **Role Configuration Panel** — set each persona's name, system prompt, and underlying model (e.g. Role A uses GPT-4o mini, Role B uses Claude Haiku, Role C uses DeepSeek V3).
- **Real-time Discussion Hall** — a group-chat-style UI. AI responses are streamed to the client via **SSE (Server-Sent Events) or WebSocket**, rendered with a typewriter effect.

### 2. Orchestration Layer (Backend)

- **Session Manager** — maintains the state of each discussion: topic, current round number, and speaking order.
- **Multi-Agent Orchestration Engine** — controls who speaks next, when to stop, and when to trigger summarization.

### 3. Model Interaction Layer (LLM Gateway)

- **API Router & Gateway** — unified abstraction over multiple LLM provider APIs, handling authentication, retries, rate limiting, and concurrency.
- **Context Processor** — dynamically assembles the prompt context and handles token-limit overflow.

### 4. Data Layer

- **PostgreSQL** — persistent storage for user configurations and historical session records.
- **Redis** — real-time session state cache and distributed locking for concurrent multi-agent sessions.

---

## Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Frontend | Next.js (React) + TypeScript + Tailwind CSS + shadcn/ui | Currently the strongest combination for AI-generated frontend interfaces; fast to scaffold a modern chat UI |
| Backend | Python 3.10+ + FastAPI | Lightweight, natively async; excellent ecosystem for LLM integration |
| LLM SDK | OpenAI Python SDK | Provider-agnostic via `base_url` override — works with DeepSeek, Qwen, and any OpenAI-compatible API |
| Orchestration | Native state machine (Phase 1) → LangGraph or AutoGen (Phase 2) | Start simple; graduate to a framework when workflow complexity grows |
| Database | PostgreSQL + Redis | PostgreSQL for long-lived data; Redis for ephemeral session state and distributed locks |

**Prerequisite knowledge:**

1. **Python async programming** — `async/await` is required for streaming LLM requests.
2. **SSE (Server-Sent Events)** — understand how the backend pushes a stream and how the frontend consumes it.
3. **Prompt engineering basics** — setting system prompts for personas, enforcing output format, and managing context.
4. **React state management** — `useState`, `useEffect`, `useRef`.

---

## Core Technical Challenges

### 1. Workflow Control & Turn Management

**Problem:** How does each AI know when it is supposed to speak, and how do you prevent it from simply repeating what others said?

**Solutions:**

- **Round-Robin Mode** — the system enforces a fixed speaking order (A → B → C → A → …). Simplest and most predictable.
- **Moderator Mode** — a hidden "moderator agent" dynamically mentions (`@`) a specific persona based on context, producing more human-like discussion. Higher cost and latency.
- **Forced context injection** — before each turn, dynamically synthesize the prompt:
  > *"The topic is [X]. Role A said [A's last message]. Role B said [B's last message]. Now it is your turn as [Role C's persona] to respond..."*

---

### 2. Context Window Management (Token Explosion)

**Problem:** As rounds accumulate, every API call must carry the full history, causing token consumption to grow rapidly and model quality to degrade.

**Solutions:**

- **Sliding window** — only retain the last N complete turns in the context.
- **Memory summarization** — run a lightweight background model (e.g. GLM-4-Flash or a local small model) every few rounds to compress earlier history into a rolling summary. The context becomes `[history summary] + [last N turns in full]`.

---

### 3. Streaming & Concurrency

**Problem:** Waiting for a full AI response before displaying it creates unacceptable latency. At the same time, multiple AIs must not speak simultaneously.

**Solution:**

- Backend uses **asyncio** for all LLM API calls.
- The frontend connects via WebSocket or HTTP SSE. When the current AI's turn-complete event fires, the backend immediately initiates the next AI's request and streams its response token-by-token to the frontend.

---

### 4. Summarization

**Mechanism:**

1. When the configured round limit is reached, the speaking loop halts.
2. The full conversation log (or its rolling summary) is passed to a dedicated **"judge / clerk" summarization agent**.
3. **Prompt design** — instruct the agent to extract:
   - Key points of disagreement between participants
   - Consensus reached during the discussion
   - A final conclusion

---

## MVP Evolution Roadmap

### Phase 1 — Core Validation (2–3 weeks)

**Goal:** Close the end-to-end loop.

- Hard-coded 2–3 fixed personas (e.g. Proponent and Opponent); user only inputs the topic.
- Up to 5 rounds of sequential speech (A → B → A → B → Summary).
- Single-page app, no authentication required.
- **Tech:** Native Python scripting for orchestration logic; single LLM provider (e.g. OpenAI or DeepSeek API) to minimize multi-model complexity.

### Phase 2 — Feature Completeness (~1 month)

**Goal:** Platformize and add flexibility.

- User-configurable personas: custom avatar, name, and system prompt.
- Choice of underlying LLM per persona.
- Configurable round count.
- **Tech:** Refactor the orchestrator using LangGraph or AutoGen; introduce Redis for multi-session concurrency; enhance frontend with typewriter effect and smooth scrolling.

### Phase 3 — Advanced Extensions

**Goal:** Improve discussion quality and practical value.

- **RAG integration** — allow agents to retrieve information from a search engine or a specified document corpus before responding (e.g. a fact-checking agent).
- **Human-in-the-loop** — the user can pause the discussion at any time, inject a message as an "observer", and let the AIs continue from that point.

---

## 4-Week Development Roadmap

> This roadmap targets experienced full-stack developers. It is not intended for beginners.

### Week 1 — Core Logic (Terminal Validation)

**Goal:** Two AIs alternate responses on a given topic in the terminal, with streaming output. No UI yet.

| Days | Tasks |
|---|---|
| Day 1–2 | Set up Python environment; obtain an LLM API key (DeepSeek recommended — very cheap and OpenAI-format compatible); run a simple single-turn conversation test. |
| Day 3–5 | Implement the core `DiscussionEngine` class: conversation history (memory), turn-rotation logic (switch from A to B after each response), prompt assembly, and API request dispatch. |
| Day 6–7 | Convert blocking calls to async (`asyncio`); implement character-by-character terminal printing. |

**Acceptance criterion:** Run the script from the command line, input "Discuss how to lose weight", and observe "Role A (Fitness Coach)" and "Role B (Nutritionist)" alternating for 3 rounds.

---

### Week 2 — Backend Service & API

**Goal:** Wrap the terminal script into standard Web API endpoints.

| Days | Tasks |
|---|---|
| Day 1–2 | Learn FastAPI basics; scaffold the project; define API routes. |
| Day 3–5 | Implement three core endpoints: `POST /api/discussion/start` (initialize a room, return `session_id`), `GET /api/discussion/stream/{session_id}` (SSE stream via `StreamingResponse`), `POST /api/discussion/stop` (force stop). |
| Day 6–7 | Introduce an in-memory dict or Redis to track session state across requests. Test the streaming endpoint with Postman or cURL. |

**Acceptance criterion:** An API request produces a continuous stream of payloads such as:
```json
{"role": "A", "content": "Hello", "status": "speaking"}
```

---

### Week 3 — Frontend UI

**Goal:** A visual "Discussion Hall" and a role-configuration page.

| Days | Tasks |
|---|---|
| Day 1–2 | Initialize the Next.js project; configure Tailwind CSS; build the home page (topic input field and Role A/B/C configuration form). |
| Day 3–5 | Build the Discussion Hall layout: message bubble stream, avatars, and a bottom status bar. |
| Day 6–7 | Connect to the backend `/api/discussion/stream` endpoint; implement the typewriter effect, auto-scroll-to-bottom logic, and Markdown rendering. |

**Acceptance criterion:** Full browser experience from "configure topic → click Start → watch AI avatars light up and type responses character by character."

---

### Week 4 — Summary Agent & Deployment

**Goal:** Add summarization, fix bugs, and ship.

| Days | Tasks |
|---|---|
| Day 1–2 | Add the summarization mechanism in the backend: when the configured round count is reached, trigger a hidden "summary agent" that reads the full conversation log and outputs a structured conclusion. |
| Day 3–4 | Frontend/backend integration testing; handle edge cases (LLM API timeout, user mid-session page refresh); add micro-interaction delays to improve perceived naturalness. |
| Day 5–7 | Deploy: backend to Render or Railway; frontend to Vercel. |

**Acceptance criterion:** A publicly accessible URL that can be shared with others for a live demo.

---

## AI-Assisted Development Tooling

### UI Design — v0.dev or Claude Sonnet

No need to hand-write CSS layouts.

Open [v0.dev](https://v0.dev) (by Vercel) and describe what you need, for example:
> *"I need a multi-AI chat interface. At the top, three AI cards displayed horizontally, each showing a status indicator (Thinking / Idle). Below, a WeChat-style bubble chat stream. Use Tailwind CSS and shadcn/ui components."*

You get production-ready React component code in seconds — paste it directly into your Next.js project.

---

### Backend & Architecture — Cursor / VS Code + AI

- **Backend:** Press `Ctrl+K` and ask:
  > *"Write a FastAPI StreamingResponse endpoint that converts this blocking Python loop into an async SSE push mechanism."*
- **Frontend:** Select flickering code and ask:
  > *"The Markdown stream renderer causes flickering. Add a throttle-buffer to smooth the updates."*

Expected gain: saves ~80% of the time otherwise spent reading docs and debugging syntax errors.

---

### Prompt Writing — ChatGPT / Claude

Do not write system prompts for AI personas from scratch. Ask a model instead:
> *"I'm building a multi-agent debate system. Write three system prompts: one for a sharp, contrarian critic; one for a fence-sitting centrist; one for an enthusiastic advocate. Constrain each response to 100 words and require each to directly rebut the previous speaker's points."*

Use the output verbatim in your system configuration.

---

### Debugging & QA

Do not search Stack Overflow for error messages. Paste the full Python traceback or browser console error — along with the relevant code — directly into your AI assistant, or use `@file` in Cursor:
> *"Why do I get a JSON Parse Error when consuming SSE data?"*

The model will identify exactly which line caused the stream to be truncated.

---

## Risk Assessment

### 1. API Cost (Token Consumption)

Multi-agent conversations are token-intensive by nature.

**Mitigations:**
- Cap the maximum round count during the MVP phase (e.g. limit 5 rounds).
- Implement a token-usage alerting mechanism in the backend.
- Prefer cost-effective models where possible (DeepSeek-V3/R1, Qwen-2.5, etc.).

### 2. Content Controllability (Hallucination & Topic Drift)

AIs may flatter each other, go off-topic, or contradict the original discussion goal.

**Mitigation:** Reinforce the original task in every request's system prompt:
> *"Important: your core task is to discuss [original topic]. Do not deviate from this subject."*

### 3. LLM Provider API Reliability

Domestic and international APIs can rate-limit or time out, breaking the discussion flow mid-session.

**Mitigation:** Implement a fallback mechanism — if the primary model times out, automatically switch to a backup model and continue the session.

---

## Summary

Get the end-to-end flow working first, then iterate. AI-assisted coding tools accelerate implementation significantly, but a solid understanding of the underlying concepts is still essential for effective debugging and design decisions.
