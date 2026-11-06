# AI as a shared software delivery resource

Presenter and reference guide. Prepared 6 November 2026.

The deck contains 20 timed slides and three reference slides. Use PowerPoint Presenter View for notes. The proposed practices and maturity rubric are recommendations for discussion, not findings validated by the cited research. The topic-change rationale reflects the supplied team position, without a local workload or wellbeing study.

## Running the 30-minute session

### 1. AI as a shared software delivery resource (0.75 minutes)

Open with the idea that AI deserves a place in the team’s way of working: a defined purpose, approved access, a budget and an accountable human. “One resource” means one coordinated project capability. The project may use several approved models and tools. Today is about how the delivery team works with that capability. The dedicated session on AI for project management covers status reporting, schedule support and related PM tasks. This session refers to that work without repeating it.

### 2. Why the topic changed (1.25 minutes)

Read the original title exactly. Explain that the topic change reflects the team’s current assessment supplied for this presentation. No local capacity or wellbeing dataset was provided. Do not present the absence of a current problem as proof that AI eliminates burnout. A shorter drafting task may release time, but it may also increase the volume that reviewers must process. The practical response is to protect review capacity and use verified savings for quality, learning or recovery before increasing commitments. Capacity forecasting and AI support for PM tasks remain in the other dedicated session.

### 3. The operating problems (1.25 minutes)

These observations come from the session brief, not a formal audit. Ask participants to recognize the pattern without identifying individuals. Tool variety can be useful, but unmanaged variety makes learning and cost control difficult. A harness is the surrounding setup that gives AI its context, tools, permissions and checks. Sharing only a prompt often fails to reproduce the result because this setup differs. The rest of the session translates the reported problems into small team agreements.

### 4. Software development evidence is mixed (1.5 minutes)

All headline evidence here concerns software developers. Cui and colleagues study randomized access to a coding assistant across Microsoft, Accenture and a Fortune 100 company. Their pooled task-completion estimate is positive, while individual experiments are noisy. METR studies experienced maintainers working on their own mature repositories and finds a slowdown with early-2025 tools. The studies use different outcomes, work and tools, so neither supplies a universal delivery multiplier. METR’s February 2026 follow-up does not provide a reliable current effect estimate. Evaluate current team workflows through acceptance and review, including quality and rework.

### 5. Maturity is a team capability (1.5 minutes)

DORA provides a useful foundation for maturity conversations because it examines the organizational system around the tools. It does not validate the five-level rubric on the next slide. That rubric is a proposed workshop aid for this team. Avoid labeling a team mature because it owns enterprise licenses or uses autonomous agents. Ask for observable evidence in each dimension, such as an approved tool list, a maintained workflow, a reviewer record or an attributable cost report. Different dimensions may sit at different stages.

### 6. A proposed maturity rubric (1.5 minutes)

Use the rubric across five dimensions: tool access, knowledge reuse, task design, output assurance and cost/value. Score each dimension at the highest stage supported by recent examples. Do not average away a serious gap in review or access control. For example, a team might have repeatable development workflows but individual budgeting. Ask what evidence would move one weak dimension forward over the next month. All stage labels and scoring rules are proposals for this session, drawing on DORA, NIST and FinOps principles.

### 7. One project capability, several approved tools (1.5 minutes)

The PMO helps convene the agreement and makes ownership visible. It does not need to approve every prompt. Product, engineering and QA retain professional accountability. “One capability” means consistent governance with room for justified specialist tools. Give exceptions an owner, purpose and review date. Separate tool access decisions from output acceptance. A tool may be approved for confidential code under an enterprise agreement but inappropriate for customer personal data. Keep the operating agreement brief and close to the work. These arrangements are proposed practices, informed by the cited guidance.

### 8. A shared prompt needs a shared harness (1.5 minutes)

Use a team repository or governed knowledge space. Each reusable asset should carry an owner, version, purpose, permitted data class and last evaluation date. Share sanitized examples rather than confidential chat histories. A short prompt may work well with one environment and fail with another because file access, tools or model behavior differs. Re-run representative checks when any important part changes. This is a proposed team convention rather than a requirement to buy an orchestration platform. A simple script and a maintained checklist can be enough.

### 9. The AI task brief (1.5 minutes)

Planning here concerns the AI work package inside delivery, rather than general project scheduling. A product owner may ask AI to identify ambiguous acceptance criteria from specified documents. A developer may ask it to propose a localized change against a failing test. QA may ask for risk-ranked test ideas. In every case, decide the size of the output and the review method before starting. If no competent reviewer or suitable check exists, restrict the task to exploration or seek expertise. Avoid open-ended requests to build an entire system or write a complete specification.

### 10. Product owners (1.5 minutes)

Use approved research and product constraints. AI can suggest patterns, but it cannot turn synthetic personas into customer evidence. The product owner validates a requirement with the appropriate stakeholder and separates source statements from assumptions. Ask for alternatives and disconfirming evidence when evaluating a proposed feature. Keep traceability from each acceptance example to the source requirement. If the sources disagree, the useful result is an explicit question for resolution rather than an invented policy. The example request is a starting pattern, not an evaluated template.

### 11. Developers (1.5 minutes)

Begin with a precise failure or requirement. Ask for the relevant code paths and a plan before a wide change. Inspect the actual diff and execute appropriate tests in a controlled environment. A model saying that tests passed is not execution evidence. Require commands and results or a clearly stated inability to run them. Keep external dependencies, credentials and production actions under the team’s existing controls. The number of generated lines is a poor success measure. The useful result is a change the team can understand, maintain and safely accept. Code review includes understanding the change, not only checking that tests pass.

### 12. QA (1.5 minutes)

The test oracle is the basis for deciding whether behavior is correct. Derive it from approved requirements, invariants or expert judgment. If AI writes both the feature and tests from one ambiguous prompt, the tests can confirm the same misunderstanding. QA should independently challenge the assumptions and include negative paths, permissions, boundary conditions and realistic failure modes. Run the tests rather than treating generated cases as evidence of coverage. A second model may offer useful criticism, but it does not establish independent truth. Keep a human decision for acceptance.

### 13. One feature across the team (1.5 minutes)

Walk through a simple feature without inventing the business rule. Suppose the source material disagrees about whether an address can change after dispatch. AI flags the contradiction and cites both locations. The product owner resolves it with the business. The developer then uses the approved decision to implement a bounded change. QA derives expected behavior independently and adds a case where dispatch status changes during the edit. Everyone shares the decision record rather than forwarding a long chat. This scenario is illustrative and is not a measured case study.

### 14. Review before acceptance (1.75 minutes)

A draft idea and an authorization change should not receive the same review. Scale checking to impact, reversibility and uncertainty. Read the content or diff, verify important claims and execute the relevant checks. AI critique can assist but cannot be the sole approval. A CHI 2025 survey found an association between confidence in AI and less reported critical thinking. This is self-reported association, not proof of causal skill loss. It reinforces the practical need for explicit review responsibilities. The three review categories on this slide are a proposed team policy.

### 15. Reading fatigue is an output-design problem (1.5 minutes)

Huge output shifts effort from generation to reading. A summary helps navigation but cannot replace reviewing critical evidence or code. Agree output limits before generation and allow exceptions when the work justifies them. For code, use logical scope and reviewer comprehension rather than a universal line limit. For documents, keep an authoritative source and publish changes to it instead of repeatedly regenerating a long document. Measure review waiting time and rework to discover whether the limit helps. These are proposed working practices, not a study-derived universal threshold.

### 16. Budget and value (1.5 minutes)

Finance and technical owners should agree a practical allocation rule for shared subscriptions and platform costs. Track direct spend separately from the human effort estimate to avoid false precision. Compare workflows on accepted outcomes of similar scope and quality. Cheap tokens can still create expensive review work. Start with inexpensive approaches for simple tasks and escalate model capability when evaluation shows a benefit. Never weaken data protection to reduce price. The controls on this slide are a proposed application of FinOps principles, not vendor pricing advice.

### 17. The pilot scorecard (1.5 minutes)

Use comparable recent tasks as a baseline and note task complexity, practitioner experience, model and workflow version. Where feasible, compare matched AI-assisted and unassisted tasks, but do not claim causality from an informal pilot. Report medians and the range rather than one success story. A simple effort calculation is baseline human hours minus all human hours in the assisted workflow, including review and rework. Keep tool spend as a separate cost line. These metrics help judge whether gains survive delivery. Do not rank employees by prompt count or generated volume. The SPACE framework supports assessing software productivity through several dimensions, including wellbeing and collaboration. The selected pilot metrics are a local adaptation.

### 18. A 30-day pilot (1.5 minutes)

Select two frequent tasks with clear acceptance conditions and available reviewers. For example, choose requirement ambiguity review and a localized bug-fix workflow. Start with synthetic or appropriately approved data. Agree success conditions before seeing results: a locally chosen improvement in total effort or elapsed time, no unacceptable deterioration in quality, acceptable review demand and spending within the ceiling. Use a small regression set of representative and known-failure cases when changing the shared workflow. The pilot schedule and conditions are proposals, not a promise of improvement.

### 19. The team’s first agreement (1 minutes)

Close the prepared content with concrete choices. The PMO can organize the agreement and ensure the review happens. Product owners, developers and QA should define acceptance in their own professional domains. Give the team permission to stop a workflow that creates more review cost or worse outcomes. The goal is a shared project capability with repeatable value and accountable delivery. Refer questions about AI for PM reporting and scheduling to the separate dedicated session.

### 20. Discussion (3 minutes)

Facilitate one minute per question. Capture a task, acceptance evidence and named owners. If the room is large, request one candidate from product, engineering and QA, then choose a bounded workflow rather than debating tools. If participants raise burnout, acknowledge that local wellbeing and workload evidence should guide the decision. Faster generation alone is insufficient evidence to increase commitments. The reference appendix remains available for questions after the timed session.

## Annotated reading list

### [DORA] DORA (2025). State of AI-assisted Software Development.

[Read the source](https://dora.dev/research/2025/dora-report/)

Research synthesis and survey evidence. Organizational associations do not establish that a tool causes better delivery. Use it to discuss organizational readiness.

### [CAP] DORA (2025). AI Capabilities Model.

[Read the source](https://dora.dev/ai/capabilities-model/report/)

Research-informed capability guidance, rather than a universal maturity certification. Use it as a companion to the proposed team rubric.

### [FIELD] Cui et al. (June 2025 version). The Effects of Generative AI on High-Skilled Work: Evidence from Three Field Experiments with Software Developers.

[Read the source](https://www.microsoft.com/en-us/research/publication/the-effects-of-generative-ai-on-high-skilled-work-evidence-from-three-field-experiments-with-software-developers/)

Three randomized company experiments, 4,867 developers. Pooled estimate: 26.08% more completed tasks (SE 10.3 percentage points). Individual experiments are noisy. Completion volume does not establish release quality or a universal capacity gain.

### [SPACE] Forsgren et al. (2021). The SPACE of Developer Productivity. ACM Queue 19(1).

[Read the source](https://doi.org/10.1145/3454122.3454124)

Developer productivity framework covering satisfaction and wellbeing, performance, activity, communication and collaboration, and efficiency and flow. Use multiple dimensions rather than code volume alone.

### [METR25] Becker et al. / METR (2025). Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity.

[Read the source](https://arxiv.org/abs/2507.09089)

Randomized trial with 16 experienced developers and 246 tasks. Completion took 19% longer with the studied tools. Narrow population and early-2025 tools.

### [METR26] METR (24 February 2026). We are Changing our Developer Productivity Experiment Design.

[Read the source](https://metr.org/blog/2026-02-24-uplift-update/)

Follow-up suggests potential improvement but selection effects and time measurement issues prevent a reliable current effect estimate. Read alongside the 2025 trial.

### [CHI] Lee et al. (2025). The Impact of Generative AI on Critical Thinking. CHI ’25, Article 1121.

[Read the source](https://doi.org/10.1145/3706598.3713778)

Survey of 319 knowledge workers with 936 examples. Higher AI confidence correlates with less reported critical thinking. Self-report and correlation do not prove cognitive decline.

### [NIST] Autio et al. / NIST (26 July 2024). Generative Artificial Intelligence Profile, NIST AI 600-1.

[Read the source](https://doi.org/10.6028/NIST.AI.600-1)

Voluntary risk guidance. Useful for accountable ownership, evaluation and information integrity. It is guidance, not an AI productivity study.

### [FIN] FinOps Foundation. FinOps for AI (living guidance, accessed 6 November 2026).

[Read the source](https://www.finops.org/framework/technology-categories/ai/)

Practitioner framework for allocation, forecasting and value. Adapt attribution and unit economics to the project. Credit: FinOps Foundation, CC BY 4.0.

### [AGENT] Anthropic (19 December 2024). Building effective agents.

[Read the source](https://www.anthropic.com/research/building-effective-agents)

Vendor engineering essay. Supports simple workflows before complex autonomy. Architectural advice rather than independent comparative evidence.

### [EVAL] Anthropic (9 January 2026). Demystifying evals for AI agents.

[Read the source](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)

Vendor engineering guidance on repeatable evaluation. Use alongside human judgment and tests that assess actual outcomes.

### [OWASP] OWASP (2025 edition). LLM06: Excessive Agency.

[Read the source](https://owasp.github.io/www-project-top-10-for-large-language-model-applications/2_0_vulns/LLM06_ExcessiveAgency.html)

Security guidance for tool permissions and autonomy. Supports least privilege and approval boundaries.

## Starter AI task brief

- Task and human owner:
- Decision or outcome:
- Approved inputs and source versions:
- Known assumptions and questions:
- Included work and exclusions:
- Permitted data and tool actions:
- Output format and size limit:
- Acceptance criteria and required evidence:
- Qualified reviewer:
- Time, spending and retry limits:
- Stop and escalation conditions:
- Final result, review decision and asset version:

## Example role prompts

These are illustrative starter patterns. Evaluate them before reuse and add only approved context.

**Product owner:** Using only the attached approved requirements, identify contradictions and missing decisions. Cite requirement IDs or source locations. Separate facts, assumptions and questions. Return a one-page brief and up to five acceptance examples. Do not invent customer evidence or business rules. Stop if the sources cannot support an answer.

**Developer:** Investigate this reproducible defect in the approved workspace. Explain the relevant code path and propose the smallest coherent change before editing. Stay within the approved scope. Return the diff, rationale, executed checks and any unverified claims. Stop when the agreed retry or time limit is reached. A human reviewer decides whether to merge.

**QA:** From these approved requirements, propose risk-ranked tests with requirement IDs, preconditions and expected results. Identify missing test oracles. Include negative paths and relevant boundaries. Review the implementation separately for risks, but derive expected behavior from the approved requirements. Distinguish proposed tests from tests actually executed.

## Team maturity workshop

Assess each dimension separately using the five stages on slide 6: tool access, shared assets, task design, output assurance, and cost/value. Record the observed stage, a recent evidence link, a gap, an owner and the next action. Do not average scores into a certification or use them to compare employee performance.

## Proposed pilot decision rules

Before the pilot, choose local numerical thresholds for improvement and budget. Track baseline and assisted tasks of comparable scope. Include human briefing, review and rework. Report quality, total spend and review demand. Expand only if the agreed criteria hold. Revise or stop workflows with unacceptable quality, cost or workload. An informal pilot provides local decision evidence rather than a causal estimate.
