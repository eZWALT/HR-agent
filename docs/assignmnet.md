# FDE Technical Assignment

## Overview

Build an AI-powered candidate screening agent for a fictional client. This assignment evaluates your ability to design a recruitment process, implement it as a conversational AI system, and present your work.

**Time:** Take a few days or a weekend — we're not clock-watching, we care about quality.

---

## The Client: Grupo Sazón

A restaurant chain hiring delivery drivers.

| Detail | Info |
| --- | --- |
| Locations | 45 across Spain and Mexico |
| Applications | ~200/week |
| Current process | 3 recruiters, manual phone screening (~15 calls/day each) |
| Problem | 60% of candidates don't answer calls. 80% of recruiter time goes to unqualified candidates |

**What they need:** An AI agent that screens candidates via messaging — collecting key information, filtering out unqualified applicants, and passing qualified ones to recruiters.

### Screening Criteria

The agent must collect and validate:

| Field | Validation |
| --- | --- |
| Full name | Required |
| Driver's license | Yes/No — disqualify if No |
| City / zone | Must be within service areas |
| Availability | Full-time, part-time, weekends |
| Preferred schedule | Morning, afternoon, evening, flexible |
| Prior delivery experience | Years + platform (Glovo, Uber Eats, etc.) |
| Start date | When can they begin |

---

## Phase 1 — Process Design

Before writing code, design the conversation flow.

**Deliver a 1-2 page document covering:**

- [ ] Conversation stages (order, branching logic)
- [ ] Data fields + validation rules
- [ ] Edge cases:
    - - Candidate stops responding mid-conversation
    - - Invalid or ambiguous answers
    - - Candidate switches language (Spanish ↔ English)
- [ ] Qualified vs. disqualified paths (what happens at each outcome)
- [ ] Message tone and length guidelines (this is messaging, not email)

---

## Phase 2 — Build

### Core Requirements (Chat Agent)

| Requirement | Detail |
| --- | --- |
| Language | Python |
| LLM | Your choice (justify it) |
| Conversation | Natural dialogue following your Phase 1 design |
| Data extraction | Structured JSON output with all screening fields |
| Validation | Reject invalid inputs gracefully, ask again |
| Context | Maintain full conversation history |
| Storage | Save conversations + extracted data as JSON or in DB |
| Summary | Generate post-conversation summary with key data points |
| Error handling | Graceful failures, no crashes on unexpected input |

### Bonus Tiers

Implement as many as you want. Choose what showcases your strengths.

**Great — Add a Voice Agent**

| Requirement | Detail |
| --- | --- |
| Voice interaction | Browser-based voice agent (e.g. ElevenLabs or similar) |
| Same flow | Handles the same screening process via voice |

### Other Bonus Features

Pick any that interest you:

| Feature | What it shows |
| --- | --- |
| **RAG** | Use a provided FAQ knowledge base (company info, job details, common questions) to answer candidate questions |
| **Multi-language** | Detect language, respond in ES or EN. Extra credit: handle code-switching |
| **Sentiment analysis** | Detect frustrated or confused candidates, adjust tone |
| **Analytics** | Conversation metrics: completion rate, drop-off stage, avg duration |
| **Re-engagement** | Follow-up logic when candidate goes silent (timing, message) |
| **Guardrails** | Prevent off-script behavior, handle inappropriate input, data privacy |
| **ATS integration design** | API spec for connecting to an ATS (design only, no need to build) |
| **Tests** | Unit tests, evals, conversation scenario simulations |
| **Deployment design** | How you'd deploy, monitor, and scale this system |

---

## Phase 3 — Presentation (1h, live)

You will present your work to an Orbio engineer. Structure:

| Block | Duration | Focus |
| --- | --- | --- |
| Demo | 15 min | Live walkthrough — happy path + at least one edge case |
| Architecture | 15 min | Code structure, design decisions, why you chose this LLM/stack |
| Discussion | 15 min | What you'd improve with more time. How this scales to 10K candidates/week |
| Q&A | 15 min | Engineer follow-up questions |

**Tips:**

- Show, don't tell — run the agent live
- Be ready to explain trade-offs, not just what you built
- You are expected to use AI for coding, but you are also expected to understand what AI did
- We value honest "I'd do X differently" over pretending it's perfect

---

## Evaluation Rubric

| Area | Weight | What we look for |
| --- | --- | --- |
| Process Design | 25% | Flow logic, edge case coverage, client empathy, completeness |
| Technical Build | 40% | Code quality, LLM integration, structured output, validation, error handling |
| Presentation | 25% | Demo quality, clarity of explanation, trade-off awareness, improvement ideas |
| Bonus Features | 10% | Depth and quality of chosen bonus features |

---

## Deliverables

- **Git repository** with source code
- **Process design document** (Phase 1 output)
- **Short demo video** (5-10 min) — walkthrough of your agent in action
- **README** with:
    - Setup instructions
    - Architecture overview
    - Key design decisions
    - Potential improvements
- **Sample conversations** demonstrating the agent's capabilities

---

## Before You Start

Take a few days or a weekend — we're not clock-watching. Focus on quality over speed, and choose the bonus features that best showcase your strengths.

Good luck.
