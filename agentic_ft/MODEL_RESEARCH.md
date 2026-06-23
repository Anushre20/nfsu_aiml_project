# Model Research for RTX PRO 6000 (96GB VRAM)

> Hardware: NVIDIA RTX PRO 6000 Blackwell — 96 GB GDDR7 ECC, 1,792 GB/s bandwidth, 125 TFLOPS FP16

---

## 1. Models Evaluated

| Model | Type | Total Params | Active Params | Architecture | License | SWE-bench Verified |
|---|---|---|---|---|---|---|
| **Qwen3-Coder-30B-A3B** | MoE | 31.8B | 3.1B | Qwen3 MoE | Apache 2.0 | **70.6%** |
| Qwen2.5-Coder-32B | Dense | 32.8B | 32.8B | Qwen2.5 Dense | Apache 2.0 | ~69% |
| Qwen2.5-Coder-14B | Dense | 14.8B | 14.8B | Qwen2.5 Dense | Apache 2.0 | ~65% |
| Qwen2.5-Coder-7B | Dense | 7.6B | 7.6B | Qwen2.5 Dense | Apache 2.0 | ~58% |
| **DeepSeek-R1-Distill-70B** | Dense | 70B | 70B | Llama-3 Dense | MIT | Reasoner |
| DeepSeek-R1-Distill-Qwen-32B | Dense | 32.8B | 32.8B | Qwen2.5 Dense | Apache 2.0 | Reasoner |
| DeepSeek-Coder-V2-Lite | MoE | 16B | 2.4B | DeepSeek MoE | Apache 2.0 | ~55% |
| DeepSeek-Coder-V2 (236B) | MoE | 236B | 21B | DeepSeek MoE | Apache 2.0 | ~67% |
| Gemma 4 31B | Dense | 31B | 31B | Gemma 4 | Apache 2.0 | ~60% |
| Phi-4 14B | Dense | 14.7B | 14.7B | Phi-4 | MIT | ~62% |
| Mixtral-8x22B | MoE | 141B | 39B | Mixtral MoE | Apache 2.0 | Agentic |
| MiniMax M2.5 | MoE | 228.7B | 10B | MiniMax MoE | Custom | ~60% |
| MiniMax M3 | MoE | 428B | 23B | MiniMax MoE | Custom | ~63% |

---

## 2. VRAM Requirements by Quantization

Formula: `params × bytes_per_param × 1.15` (15% overhead for KV cache + activations)

| Model | FP16 (2B) | Q8 (1B) | Q4_K_M (0.5B) | Q3 (0.375B) | Q2 (0.25B) |
|---|---|---|---|---|---|
| 7B model | **~16 GB** ✅ | ~8 GB | ~4 GB | ~3 GB | ~2 GB |
| 14B model | **~32 GB** ✅ | ~16 GB | ~8 GB | ~6 GB | ~4 GB |
| 31-32B model | **~73 GB** ✅ | ~37 GB ✅ | **~18 GB** ✅ | ~14 GB | ~9 GB |
| 70B model | ~161 GB ❌ | ~80 GB ✅ | **~40 GB** ✅ | ~30 GB ✅ | ~20 GB ✅ |
| 141B Mixtral | ~324 GB ❌ | ~162 GB ❌ | **~81 GB** ✅ | ~61 GB ✅ | ~41 GB ✅ |
| 236B DS-Coder-V2 | ~543 GB ❌ | ~271 GB ❌ | ~136 GB ❌ | ~102 GB ❌ | **~68 GB** ✅ |
| 428B M3 | ~984 GB ❌ | ~492 GB ❌ | ~246 GB ❌ | ~185 GB ❌ | ~123 GB ❌ |

> **Key insight**: On a single 96GB GPU, the largest model you can run at Q4 is ~190B total params. At Q3, ~270B. Models exceeding this (M3 at 428B) do not fit at any practical quantization.

---

## 3. Single Model — What Fits on 96GB

| Model | Best Quant | VRAM | Fits? | Notes |
|---|---|---|---|---|
| **Qwen3-Coder-30B-A3B** | FP16 | ~73 GB | ✅ | Best coder fit at FP16 quality |
| Qwen3-Coder-30B-A3B | Q4_K_M | ~18 GB | ✅ | Much more headroom for context |
| Qwen2.5-Coder-32B | FP16 | ~75 GB | ✅ | Tight but fits |
| Qwen2.5-Coder-32B | Q4_K_M | ~19 GB | ✅ | Comfortable |
| Qwen2.5-Coder-14B | FP16 | ~34 GB | ✅ | Full-param FT possible |
| DeepSeek-R1-Distill-70B | Q4_K_M | ~40 GB | ✅ | Strongest judge option |
| DeepSeek-R1-Distill-70B | Q3_K_M | ~30 GB | ✅ | Lighter, slight quality loss |
| DeepSeek-R1-Distill-Qwen-32B | FP16 | ~75 GB | ✅ | Judge at full precision |
| Gemma 4 31B | FP16 | ~71 GB | ✅ | Apache 2.0, general purpose |
| Gemma 4 31B | Q4_K_M | ~18 GB | ✅ | |
| Phi-4 14B | FP16 | ~34 GB | ✅ | Fits for full-param FT |
| Mixtral-8x22B | Q4_K_M | ~81 GB | ⚠️ Tight | Marginal headroom |
| DeepSeek-Coder-V2-Lite (16B MoE) | FP16 | ~37 GB | ✅ | MoE, efficient at inference |
| DeepSeek-Coder-V2 (236B MoE) | Q2_K | ~68 GB | ✅ | Large but at heavy quantization |
| MiniMax M2.5 (228.7B) | Q2_K | ~66 GB | ✅ | At Q2 only — quality loss |
| MiniMax M2.5 (228.7B) | Q4_K_M | ~115 GB | ❌ | Doesn't fit |
| MiniMax M3 (428B) | Any | >100 GB | ❌ | Doesn't fit at any quant |

---

## 4. Concurrent Models — Coder + Judge on 96GB

Target: Run **coder** and **judge** simultaneously on one GPU.

### Option A: Both at Q4 (Recommended)

| Coder | Judge | Total VRAM | Fits? |
|---|---|---|---|
| **Qwen3-Coder-30B-A3B** @Q4 (~18 GB) | **DS-R1-70B** @Q4_K_M (~40 GB) | **~58 GB** | ✅ Best pair |
| Qwen3-Coder-30B-A3B @Q4 (~18 GB) | DS-R1-Qwen-32B @Q4 (~18 GB) | ~36 GB | ✅ |
| Qwen2.5-Coder-32B @Q4 (~19 GB) | DS-R1-70B @Q4_K_M (~40 GB) | ~59 GB | ✅ |
| Qwen2.5-Coder-14B @Q4 (~8 GB) | DS-R1-70B @Q4_K_M (~40 GB) | ~48 GB | ✅ |

### Option B: Coder at Q4 + Judge at higher precision

| Coder | Judge | Total VRAM | Fits? |
|---|---|---|---|
| Qwen3-Coder-30B-A3B @Q4 (~18 GB) | DS-R1-Qwen-32B @FP16 (~75 GB) | **~93 GB** | ✅ Tight |
| Qwen3-Coder-30B-A3B @Q4 (~18 GB) | Gemma 4 31B @FP16 (~71 GB) | ~89 GB | ✅ |

### Option C: Coder at FP16 + Judge at Q4

| Coder | Judge | Total VRAM | Fits? |
|---|---|---|---|
| Qwen3-Coder-30B-A3B @FP16 (~73 GB) | Qwen2.5-Coder-14B @Q4 (~8 GB) | ~81 GB | ✅ Judge is weaker |
| Qwen3-Coder-30B-A3B @FP16 (~73 GB) | DS-R1-Qwen-32B @Q4 (~18 GB) | ~91 GB | ✅ Tight |
| Qwen2.5-Coder-32B @FP16 (~75 GB) | Qwen2.5-Coder-14B @Q4 (~8 GB) | ~83 GB | ✅ |

---

## 5. Fine-Tuning Feasibility

### 5.1 Full-Parameter Fine-Tuning

**Requirements** (mixed precision fp16 + 8-bit Adam + gradient checkpointing):
- Weights (fp16): `params × 2`
- Gradients (fp16): `params × 2`
- 8-bit Adam states: `params × 2` (1 byte per state, 2 states)
- Activations + overhead: ~5–15 GB

| Model | Est. GPU VRAM | Fits 96GB? | Notes |
|---|---|---|---|
| **7B** | ~35 GB | ✅ | Comfortable, batch size 8–16 |
| **14B** | ~66 GB | ✅ | Good headroom, batch size 4–8 |
| **32B** | ~150 GB | ❌ | LoRA required, full-param impossible |
| **70B** | ~326 GB | ❌ | LoRA required |

> **Key insight**: 14B is the largest model feasible for full-param FT on a single 96GB GPU. For 30B+ models, use LoRA/QLoRA.

### 5.2 LoRA / QLoRA Fine-Tuning

**Requirements** (Q4 base model + LoRA adapters):
- Base model (Q4): `params × 0.5`
- LoRA weights (rank 16–64): ~0.1–1% of params
- LoRA gradients + optimizer: proportional to LoRA size
- Activations + overhead: ~2–8 GB

| Model | Base VRAM (Q4) | + LoRA | Total | Fits 96GB? |
|---|---|---|---|---|
| **7B** | ~4 GB | + ~1 GB | ~5 GB | ✅ |
| **14B** | ~8 GB | + ~2 GB | ~10 GB | ✅ |
| **30–32B** | ~18 GB | + ~3 GB | **~21 GB** | **✅ Best target** |
| **70B** | ~40 GB | + ~4 GB | ~44 GB | ✅ |
| **141B Mixtral** | ~81 GB | + ~6 GB | ~87 GB | ⚠️ Tight |
| **236B DS-Coder-V2** | ~136 GB (Q4) / ~68 GB (Q2) | + ~6 GB | ~74 GB (Q2) | ⚠️ Q2 quality loss |

### 5.3 Catastrophic Forgetting Risk

| Training Approach | Learnable Params | Forgetting Risk | Best Use Case |
|---|---|---|---|
| **Full-param FT (14B)** | 100% (~14B) | **High** — large update surface | When you have 20K+ diverse trajectories |
| **LoRA (30B MoE)** | ~0.3% (~100M) | **Low** — minimal update surface | 1K–5K trajectories; preserves base knowledge |
| **Full-param FT with data mixing** | 100% | Medium — mitigated by 70/30 mix | Mix collected trajs + 10K general coding data |
| **LoRA + data mixing** | ~0.3% | **Very low** | Safest approach for small datasets |

Mitigation strategies:
- **Data mixing**: Blend collected trajectories with 10–20K diverse coding examples (The Stack, CodeAlpaca)
- **Low learning rate**: 1–5e-5 for full-param, 1–2e-4 for LoRA
- **Elastic Weight Consolidation (EWC)**: Penalize changes to important parameters
- **Early stopping**: Monitor held-out HumanEval/MBPP; stop at first sign of regression
- **Gradual unfreezing**: Start with LoRA, progressively increase rank or switch to full-param

---

## 6. Chosen Architecture

| Role | Model | Quant | VRAM | Rationale |
|---|---|---|---|---|
| **Coder** | **Qwen3-Coder-30B-A3B** | Q4_K_M | ~18 GB | Best SWE-bench (70.6%) among models that fit efficiently; MoE (3B active) = low compute/token; Apache 2.0 |
| **Judge** | **DeepSeek-R1-Distill-70B** | Q4_K_M | ~40 GB | Strongest open reasoning model at this size; distilled R1 reasoning for evaluation quality |
| **Total** | | | **~58 GB** | 38 GB headroom for KV cache, context, system processes |

### Why not alternatives:

- **Full-param FT on Qwen2.5-Coder-32B** → Requires ~150GB — doesn't fit on single 96GB
- **MiniMax M2.5 (228.7B)** → Q4 = 115GB (doesn't fit), Q2 = 66GB (fits but heavy quality loss)
- **MiniMax M3 (428B)** → Doesn't fit at any quantization on single 96GB GPU
- **DeepSeek-Coder-V2 (236B)** → Q2_K fits at ~68GB but 2-bit quantization on 236B dense is unreliable for coding
- **Gemma 4 31B as coder** → Apache 2.0 but not coding-specialized; Qwen3-Coder outperforms by ~10% on SWE-bench

---

## 7. Post-Collection Fine-Tuning Strategy

```
┌──────────────────────────────────────────────────────┐
│               3-Week Data Collection                  │
│  60 tasks × ~5 runs each × various approaches        │
│  ≈ 300 trajectories → ~60 good / ~60 bad DPO pairs   │
└──────────────┬───────────────────────────────────────┘
               ↓
┌──────────────────────────────────────────────────────┐
│             Fine-Tuning (offline)                     │
│                                                      │
│  Option A: LoRA on Qwen3-Coder-30B-A3B (recommended) │
│    - Q4 base + rank 16 LoRA                          │
│    - ~21 GB total → fits easily                      │
│    - Low forgetting risk                             │
│                                                      │
│  Option B: Full-param on Qwen2.5-Coder-14B           │
│    - ~66 GB → fits with headroom                     │
│    - Higher forgetting risk, needs data mixing       │
│    - More capacity to learn new behaviors           │
│                                                      │
│  One or both runs, then compare eval on HumanEval/   │
│  MBPP/SWE-bench Lite to detect regression            │
└──────────────────────────────────────────────────────┘
```

---

## 8. Reference: VRAM Calculation Formulas

```
Inference:
  VRAM ≈ params × bits_per_weight / 8 × 1.15

Fine-tuning (full-param, mixed precision, 8-bit Adam):
  VRAM ≈ params × (2 + 2 + 2) + activations
       = params × 6 + ~5–15 GB

Fine-tuning (full-param, fp32 Adam):
  VRAM ≈ params × (4 + 4 + 8) + activations
       = params × 16 + ~5–15 GB

LoRA on Q4 base:
  VRAM ≈ params × 0.5 + (rank × d_model × 2 × 4) × 1.5
       ≈ params × 0.5 + small overhead

Quantization levels:
  FP16/BF16:  2 bytes/param  (100% quality)
  Q8:         1 byte/param   (~99% quality)
  Q4_K_M:     0.5 byte/param (~95–97% quality)
  Q3_K_M:     0.375 byte/param(~90–93% quality)
  Q2_K:       0.25 byte/param(~80–85% quality)
```

---

## 9. Key References

| Model | Paper / Link |
|---|---|
| Qwen3-Coder | https://github.com/QwenLM/Qwen3 |
| Qwen2.5-Coder | https://github.com/QwenLM/Qwen2.5-Coder |
| DeepSeek-R1 | https://github.com/deepseek-ai/DeepSeek-R1 |
| DeepSeek-Coder-V2 | https://github.com/deepseek-ai/DeepSeek-Coder-V2 |
| MiniMax | https://github.com/MiniMax-AI/MiniMax-01 |
| Gemma 4 | https://ai.google.dev/gemini/gemma |
| RTX PRO 6000 | https://www.nvidia.com/en-us/rtx-pro/ |
| SWE-bench Verified | https://github.com/swe-bench/SWE-bench |
| llama.cpp | https://github.com/ggerganov/llama.cpp |
| bitsandbytes (QLoRA) | https://github.com/TimDettmers/bitsandbytes |
