---
title: Web Chatbot Yolo Reliability Cook
date: 2026-06-09
plan: "D:/PHAN LOAI RAC/plans/260609-2238-web-app-chatbot-reliability-first"
---

# Web Chatbot Yolo Reliability Cook

## Context

User confirmed the project still has visible gaps in web/app, chatbot reliability,
and YOLO recognition. Supabase work was paused because cloud should not build on
unstable local UX and AI contracts.

## What Happened

- Created a reliability-first ClaudeKit plan.
- Blocked the Supabase roadmap behind this reliability plan.
- Fixed DeepSeek model override and malformed provider fallback.
- Added timeout/malformed chatbot integration tests.
- Hardened web `agentFetch` timeout/offline/error parsing.
- Added local chat fallback responses so the chat transcript does not hang.
- Added YOLO failure triage and model promotion checklist docs.

## Decisions

- Keep physical camera/Arduino acceptance deferred.
- Do not promote `models/best.pt` from this pass.
- Treat Supabase as a later foundation after web/chatbot/model reliability is clearer.

## Next

- Run visual Playwright review for admin/user routes.
- Decide whether local `operator` and `guest` roles are needed before Supabase Auth.
- Pick priority weak YOLO classes for the next dataset cleanup pass.
