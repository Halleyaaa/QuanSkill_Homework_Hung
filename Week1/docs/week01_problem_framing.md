# Week 1 – Problem Framing (Customer Support Assistant)

> Evidence labels: **O** = Observed, **E** = Estimated, **A** = Assumed, **U** = Unknown.
> Scenario (A): the Tier-1 customer-support team of a mid-sized online retailer. No real company data has been collected yet.

## 1. Problem statement (no technology named)

Tier-1 support agents re-answer the same product and policy questions every day by manually searching several scattered sources
(help-center pages, an internal wiki, past tickets) and checking that the answer matches the current policy. This slows the first reply
(current time per ticket: **U**, not yet measured) and lets answers differ between agents. The team needs a way to find and verify the
correct answer for repeated questions faster, without lowering answer correctness. **(A)**

## 2. Primary target user

**Tier-1 support agent** (Role) at a mid-sized online retailer handling about 900 repeated-question tickets per month in the helpdesk (Context),
who needs to send a verified, policy-correct reply in about 6 minutes or less without searching several documents by hand (Goal). **(A)**

| Role | Who |
| --- | --- |
| Primary user | Tier-1 support agent |
| Beneficiary | Customers (and agents, who do less repetitive searching) |
| Buyer | Head of Customer Support / Operations |
| Approver | Support operations manager, with Security / Compliance |
| Engineering stakeholder | AI/software engineer and helpdesk-integration owner |

## 3. Current workflow (A, confirm by shadowing agents)

1. Customer message arrives and is assigned to an agent.
2. Agent reads the message and identifies the intent.
3. **Agent searches help center, wiki and past tickets for the answer. ← highest friction**
4. **Agent verifies the answer against the current policy (or asks a colleague). ← high friction**
5. Agent writes or edits the reply.
6. Agent sends the reply, sets tag and status.
7. Customer reopens the ticket if the answer was wrong or incomplete.

## 4. Baseline

- **B₀ = average handle time on repeated-intent tickets** = (Σ tᵢ) ÷ n, tᵢ = minutes of agent working time from first open to reply sent.
- Measurement plan: sample n = 50 closed tickets from the top intents; use helpdesk timestamps; validate by shadowing 5 agents; report mean, median and p90.
- Status: **not yet measured (U)**. Planning value B₀ = 14 min/ticket **(A)**.
- Technical baseline to add later: keyword search over the same documents, scored on the same test questions.

## 5. AI suitability and capability

- Capability: **Retrieval + Generation** (grounded drafting). Prediction is not needed; Action is excluded from the MVP. **(A)**
- Why not rules only: customers phrase the same question in many ways; answers live in unstructured documents.
- Why not full automation: a wrong policy statement is costly; an agent reviews every draft.

## 6. Minimum Useful MVP

Given an agent's natural-language question about return, shipping or warranty policy (one product area, one language), the system should retrieve the
relevant approved passages and draft a short cited answer, or say it cannot answer when the evidence is insufficient, producing a cited draft reply
for the Tier-1 support agent to review and send.

## 7. Data / knowledge

| Item | Status |
| --- | --- |
| Sources: help-center articles, return/shipping/warranty policy documents, reply macros | Documents exist (A) |
| Quality: possibly outdated or duplicated | U |
| Access: read-only export from support operations | A |
| Sensitivity: policy documents low; tickets contain personal data, so excluded from the MVP | A |

## 8. Success metrics and acceptance criteria (thresholds A, to be agreed with the support manager)

| Type | Metric | Target |
| --- | --- | --- |
| User / business | Handle time per repeated-intent ticket | ≤ 6 min vs B₀ |
| AI quality | Correct and supported answers on a 100-question golden set; Recall@5 of the correct passage | ≥ 90%; ≥ 0.85 |
| Operational | p95 response time; cost per answered question | ≤ 8 s; ≤ $0.02 |

**Critical (must pass before any pilot):**
C1. Zero unsupported or contradicting policy claims on 30 high-risk questions.
C2. Abstain or escalate on ≥ 95% of 20 out-of-scope questions.
C3. No customer personal data in any output.

## 9. User interface and deployment

- UI: web side-panel next to the helpdesk; question in, cited draft out; copy, helpful / not helpful with reason, escalate. No automatic sending.
- Development: containerised app on a small approved document set with an evaluation script.
- Production direction: internal service behind company sign-in, with logging and monitoring, later linked to the helpdesk.

## 10. Constraints, risks and non-goals

**Constraints:** approved and current documents only; no personal data to external services without approval; runs beside the existing helpdesk; 4-week build by one engineer (all A).

| Risk | Mitigation |
| --- | --- |
| R1. Unsupported or wrong policy answer (hallucination) | Answer only from retrieved passages, show citations, abstain below an evidence threshold, agent reviews, critical tests C1–C2 |
| R2. Outdated or contradictory documents | Record owner and last-updated date, exclude stale files, freshness check before each release, report conflicts to owner |

**Non-goals:** no auto-send or actions such as refunds; no multi-language, voice, dashboards or web search in the MVP.

## 11. Expected value (E, from Assumed inputs)

- Minutes saved = 900 × (14 − 6) = 7,200 min/month = **120 h/month**
- Simple labor value = 120 × $28 = **$3,360/month** (not ROI: build/run costs, adoption and rework are not included)

## 12. Assumption register

| Assumption | Risk | How we will test it | Status |
| --- | --- | --- | --- |
| A1. ≥ 50% of tickets are repeated questions answerable from approved documents | **High** – value case collapses if false | Label 100–200 recent tickets by intent; check whether the answer exists in the knowledge base | U |
| A2. Repeated tickets take ~14 min, and search/verify is the largest part | Medium | Time-and-motion sample of 50 tickets; 5 shadowing sessions; compute B₀ | A |
| A3. Agents will trust and use cited drafts | Medium | 2-week pilot with 5 agents: adoption rate, edit rate, interviews | A |

## 13. Workflow-interview questions (no AI mentioned)

1. Walk me through the last customer question you handled, from arrival to closing. What did you do at each step?
2. Which part took the most time or effort, and what made it hard?
3. Where do you look for an answer, and what do you do when sources disagree or look outdated?
4. How often does the same question come up in a normal day? Can you show me a recent example?
5. What happens when an answer is late or wrong, who notices, and what does it cost?

## 14. Evidence status summary

- **Observed:** none yet.
- **Assumed:** scenario, 900 tickets/month, T₀ = 14 min, T₁ = 6 min, $28/h, thresholds, document availability.
- **Estimated:** $3,360/month value.
- **Unknown:** repetition rate, real baseline, document quality, agent adoption.

**Chain:** Pain → User → Workflow → Baseline → AI Opportunity → MVP → Measure → Value
