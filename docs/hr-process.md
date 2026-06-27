# Hiring Process

## Overview

This document defines the recruitment workflow implemented by the AI screening agent for **Grupo Sazón** for instance but applies for many others. The goal is to replace the initial recruiter phone screening with a structured messaging interview that efficiently identifies qualified delivery driver candidates while providing a friendly and natural conversational experience.

This system is **not a free-form chatbot**. It is a **deterministic state machine** that uses an LLM for natural language understanding, structured information extraction, and response generation. Business decisions remain deterministic and are never delegated entirely to the language model, with a focus on human-in-the-loop when needed.

---

# Objectives

- Reduce recruiter workload by filtering unqualified candidates early.
- Collect all required hiring information.
- Validate every required field.
- Produce structured candidate data.
- Handle natural conversations and interruptions.
- Maintain a friendly, concise messaging style.
- Ensure clear and auditable hiring decisions.

---

# Screening Criteria

| Field | Required | Validation |
|--------|----------|------------|
| Driver's License | Yes | Must be **Yes** |
| City / Zone | Yes | Must belong to a supported service area (hard filter) |
| Availability | Yes | Full-time / Part-time / Weekends |
| Preferred Schedule | Yes | Morning / Afternoon / Evening / Flexible |
| Previous Delivery Experience | Yes | Years + Platform(s) |
| Start Date | Yes | Candidate availability |
| Full Name | Yes | Required before completion |

---

# Interview Workflow (Logical Flow)

Greeting  
↓  
Driver License  
↓  
City (hard stop if not supported)  
↓  
Availability  
↓  
Preferred Schedule  
↓  
Delivery Experience  
↓  
Start Date  
↓  
Full Name  
↓  
Summary & Confirmation  
↓  
Outcome Decision  

---

# Outcome States

## 🟢 Qualified
Candidate meets all requirements and confirms final summary.

## 🔴 Disqualified
Triggered immediately when:
- No valid driver’s license
- City is outside supported service area

## 🟡 Absent
Candidate drops off:
- No response after retries
- Exceeded max clarification attempts

---

# Conversation Principles

- Ask one question per message
- Keep responses short and conversational
- Maintain a friendly, professional tone
- Never repeat already collected data
- Resume naturally after interruptions

---

# Opportunistic Information Extraction

Candidates may provide multiple fields in one message.

Example:

> Hi! I'm Walter, I live in Madrid, have a driver's license and worked for Glovo for two years.

The system extracts all valid fields and continues from the first missing requirement.

---

# Validation Rules

- All fields must be validated before storage
- Ambiguous inputs trigger clarification
- Maximum K retries per field

If unresolved → Absent

---

# Interruptions Handling

The system supports:

- Job-related questions
- Language switching (ES ↔ EN)
- Corrections
- Multi-intent messages

Behavior:
1. Handle interruption
2. Preserve state
3. Resume workflow

---

# Candidate Profile

A structured profile is built progressively and independently of workflow state.

- State machine → controls next question
- Candidate profile → stores extracted data

This separation ensures opportunistic extraction without breaking deterministic flow logic.

---


# System Workflow Graph

stateDiagram-v2
    [*] --> Greeting

    Greeting --> DriverLicense
    DriverLicense --> City
    DriverLicense --> Disqualified

    City --> Availability
    City --> Disqualified

    Availability --> PreferredSchedule
    PreferredSchedule --> Experience
    Experience --> StartDate
    StartDate --> FullName
    FullName --> Summary

    Summary --> Qualified
    Summary --> Absent

    DriverLicense --> Absent
    City --> Absent
    Availability --> Absent
    PreferredSchedule --> Absent
    Experience --> Absent
    StartDate --> Absent
    FullName --> Absent

---

# Future Extension (Deferred Candidates - Not Implemented)

A future improvement may introduce a Deferred Candidate Pool for:

- Out-of-zone but high-quality candidates
- Long-term talent storage
- Geographic expansion readiness

This is intentionally excluded from the current implementation to keep decision logic simple and deterministic.

---

# Design Philosophy

- Business logic is deterministic and auditable
- LLMs are used only for language understanding and generation
- Early filtering reduces recruiter workload
- System prioritizes candidate experience and respect for time
- Architecture is modular and extendable (RAG, voice, ATS integration)
- All decisions are explainable and traceable