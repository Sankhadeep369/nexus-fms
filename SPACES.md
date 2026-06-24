---
title: NEXUS FMS
emoji: 🏢
colorFrom: indigo
colorTo: cyan
sdk: docker
pinned: false
license: mit
short_description: Facilities management AI assistant — fine-tuned Gemma 3 4B
---

# NEXUS — Facilities Management AI Assistant

This Space hosts the backend API for NEXUS, a domain-specific AI assistant
fine-tuned on facilities management material: AMC contracts, HSE SOPs, HVAC
maintenance records, fire safety NOCs, and vendor comparisons.

**Model:** `MioA9/gemma3-4b-nexus-qlora-v1` (Gemma 3 4B, QLoRA fine-tune, GGUF Q4_K_M)

**Note:** On first cold start the GGUF (~2.5 GB) downloads from HF Hub —
expect 60-90 seconds before the API is ready. Subsequent requests are fast.

## API

- `GET  /health` — liveness check
- `GET  /info`   — model name and context size
- `GET  /suggestions` — 20 curated question chips with cache status
- `POST /chat`   — SSE streaming chat (body: `{"query": "...", "mode": "simple"|"thinking"}`)

## Environment variables (set in Space settings)

| Variable | Required | Description |
| --- | --- | --- |
| `HF_TOKEN` | If model repo is private | HuggingFace token for GGUF download |
| `CORS_ORIGINS` | Yes | Comma-separated frontend origins (e.g. `https://nexus-fms.vercel.app`) |

Source: [github.com/Sankhadeep369/nexus-fms](https://github.com/Sankhadeep369/nexus-fms)
