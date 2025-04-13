# 🧭 Chat Navigator — Branching Memory System for AI Conversations

A proof-of-concept (POC) system that reimagines how long-form chat conversations can be **navigated**, **branched**, and **summarized** to support exploratory thinking and idea evolution.

---

## 🌌 What Is It?

Most chat UIs are linear, throwaway, and context-heavy. This tool changes that.

> ✦ **Chat Navigator** is a chat augmentation system that:
> - Tracks every message as a node in a tree
> - Detects topic shifts and generates summaries
> - Allows **branching off** from any point in the conversation
> - Supports **subtree pruning**, merging, and reindexing
> - Builds a flat, fast, UI-optimized **chat + summary trace map**

It's not just a chatbot UI. It's a **cognitive branching system**.

---

## 💡 Use Case

For engineers, researchers, strategists, and thinkers who want to:

- Experiment with alternate solutions without biasing the LLM
- Review idea evolution over long sessions
- Prune and restructure their conversations like code
- Summarize or "collapse" sections of discussion into digestible chunks

---

## 🧱 Architecture

- **Backend**: Python, SQLAlchemy, FastAPI
- **LLM Integration**: OpenAI / LangChain
- **Core Data Models**:
  - `messages`: flat list with parent/child linkage
  - `summaries`: spans with start/end nodes, summary tree projection
- **Tree Structures**:
  - `message_index`: message tree built from link table
  - `summary_index`: tree of summaries projected over message graph
- **Dispatcher Pattern**: All mutations (add, branch, delete, summarize) routed through typed handlers

---

## ✨ Key Features

- ✅ Add message (user or AI)
- ✅ Detect topic shift → auto-generate summary
- ✅ Branch from any message and isolate new line of thought
- ✅ Delete branch (subtree deletion)
- ✅ Summarize unsummarized segments
- 🧪 Experimental: merge and split summaries

---

## 🧪 Status

This is a work-in-progress, backend-first POC.

- Frontend is minimal or stubbed (planned for completion post-Golden Week)
- Summary merging, UI navigation, and full reindexing support are under design
- Designed with long-term extensibility, versioning, and visual traceability in mind

---

## 🔭 Future Vision

Imagine Git, but for AI conversations — a system where you don't just *chat*...

> You explore.  
> You branch.  
> You trace your thoughts across time.

---

## 🚀 Get Involved

Want to contribute or extend this?
Open a discussion or issue — especially if you're interested in:

- React/JS frontend integration
- Context-aware pruning or UI-driven summarization
- Git-style diffing and merging of conversation branches

---

## 🧠 Author

Built in stolen hours by an engineer with AI dreams.

