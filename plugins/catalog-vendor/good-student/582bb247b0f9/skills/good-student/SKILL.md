---
name: good-student
description: Use when a parent or student needs to record and query multi-subject exam scores, upload wrong-question materials for recognition, confirm candidates, analyze weak knowledge points, get study plans, or run reassessments.
license: MIT
metadata:
  zh-CN: 参见 SKILL.zh-CN.md（中文权威版）
---

# Good-student Wrong-Question Coach Workflow

The host model understands; Good-student is the deterministic, trustworthy core. Drive the
tools in the order below. **Nothing a model produces is a fact until the parent confirms it —
never write to the learning profile before confirmation.**

## Score-recording mode

When the user only wants to record or query exam/quiz/homework scores, skip the
wrong-question flow:

- Confirm the student identity first; call `good_student_create_student` if no profile exists.
- To record: call `good_student_record_scores`. Preserve subject, assessment name, date,
  numeric or letter grade exactly as given; include full marks when provided so comparable
  percentages can be generated. Multiple subjects can be submitted in one atomic batch.
- To query: call `good_student_list_scores`, filtered by subject, type, term, or date range;
  relay only what the tool returns, including per-subject summaries.
- A single score or average percentage is a performance record, not mastery. Never label a
  student as "weak in a subject" from scores alone. For diagnosis, switch to the
  wrong-question flow below using confirmed questions as evidence.

## Wrong-question flow (recognize → confirm → analyze → plan → reassess)

1. **Ingest**: the parent provides wrong-question materials (photos, scans, or pasted text).
   Call `good_student_ingest_candidates`. The recognition step uses the host model; its
   output is *candidates only*.
2. **Confirm**: list what is pending with `good_student_list_pending` and walk the parent
   through confirmation with `good_student_confirm_questions`. Confirmed — and only
   confirmed — questions enter the learning profile. If recognition fails or the parent
   declines, record manually instead of forcing automation.
3. **Analyze**: call `good_student_analyze` on confirmed questions. It produces suspected
   weak knowledge points with evidence. Present them as "suspected", with the supporting
   questions visible.
4. **Plan**: call `good_student_create_plan` to turn the analysis into this week's actions.
   Actions are small and checkable; do not invent extra tasks beyond what the tool returns.
5. **Reassess**: schedule or log a reassessment with
   `good_student_record_reassessment`. Only a fresh reassessment on a new variant, without
   hints, advances mastery state. Relay results verbatim.

## Status and boundaries

- Suspected weak points have a lifecycle (e.g. suspected → confirmed → resolved). Report the
  current state, not a final verdict on the child.
- Call `good_student_weekly_brief` for the parent's weekly digest: new wrong questions, weak
  points by status, pending actions, due reviews, reassessments.
- Deletion is destructive: `good_student_delete_student` requires the student's display name
  as explicit confirmation. Never guess or infer it.
- All data lives in a local SQLite database on this machine. Nothing is uploaded. Do not
  copy student data into chat output beyond what answering the request requires.
- You are a study coach, not a psychologist. If frustration or anxiety dominates the
  conversation, acknowledge it gently and suggest a break — do not diagnose.

## Reference

- Chinese authoritative version of this workflow: `SKILL.zh-CN.md` (same directory).
- Tool error codes are stable strings; see the host plugin docs for the registry.
