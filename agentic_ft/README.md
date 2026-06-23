# Agentic Fine-Tuning Pipeline

Collect trajectories for fine-tuning an open-source LLM on agentic coding tasks.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  orchestrator (orchestrate.ps1)                     │
│  ─────────────                                      │
│  Loops: pick task → run opencode → log → evaluate   │
└──────┬──────────────────────────────────────────────┘
       │
       ├──→ opencode (uses Qwen3-Coder-30B-A3B)
       │     builds project in workspace
       │     saves trajectory to data/trajectories/
       │
       └──→ judge (DeepSeek-R1-Distill-70B @ Q4_K_M)
             served by llama.cpp server → judge_eval.py
             evaluates trajectory → data/evaluations/
```

## Components

| Component | Model | Role |
|---|---|---|
| **Coder** | Qwen3-Coder-30B-A3B (Q4) | Coding agent — used by opencode CLI |
| **Judge** | DeepSeek-R1-Distill-70B (Q4_K_M) | Evaluator — served as local API |
| **Orchestrator** | — | Continuous loop: build → log → judge → repeat |

## Setup

### 1. Install dependencies

```powershell
pip install requests
```

### 2. Download models (via Ollama)

```powershell
ollama pull qwen3-coder-30b-a3b
ollama pull deepseek-r1-distill-70b
```

Or via llama.cpp GGUF:

```powershell
huggingface-cli download TheBloke/DeepSeek-R1-Distill-70B-GGUF `
  deepseek-r1-distill-70b-q4_k_m.gguf --local-dir C:/models
```

### 3. Start the judge server

```powershell
cd scripts
.\serve_judge.ps1
```

Or if using Ollama for the judge:

```powershell
ollama run deepseek-r1-distill-70b
```

(Then update judge_api_url in pipeline.yaml)

### 4. Configure opencode

Edit `config/opencode.json` to set your coder model provider.

### 5. Start the pipeline

```powershell
cd scripts
.\orchestrate.ps1
```

The pipeline runs continuously, shuffling tasks between cycles.

## Running Options

```powershell
# Run N builds then stop
.\orchestrate.ps1 -MaxBuilds 10

# Run only tasks matching a stack (react, node, python, ml)
.\orchestrate.ps1 -TaskFilter "react"

# Skip judge evaluation (useful for testing)
.\orchestrate.ps1 -NoJudge

# Custom config file
.\orchestrate.ps1 -ConfigFile "../config/my_config.yaml"
```

## Task Definitions

Tasks are in `tasks/*.jsonl` — each line is a JSON task object:

```json
{
  "id": "unique_task_id",
  "task": "Prompt to give the coding agent",
  "description": "Human-readable summary",
  "stack": "react|node|python|ml",
  "difficulty": "easy|medium|hard",
  "tags": ["tag1", "tag2"],
  "eval_criteria": ["criterion1", "criterion2"]
}
```

## Output Structure

```
data/
├── trajectories/       # Raw trajectory JSON per build
├── evaluations/        # Judge evaluation JSON per build
├── dpo_pairs/
│   ├── good/           # High-scoring trajectories (score >= 8)
│   └── bad/            # Low-scoring trajectories (score < 4)
└── stats_*.json        # Pipeline run statistics
```

## DPO Pair Collection

The pipeline automatically creates DPO training pairs:
- **Good** trajectories: score >= 8/10 → saved to `dpo_pairs/good/`
- **Bad** trajectories: score < 4/10 or failed after retries → saved to `dpo_pairs/bad/`
- Same task will have both good and bad runs — use these as contrastive pairs

## Offline Fine-Tuning (Post-Collection)

After 3 weeks of data collection:

1. Pair good/bad trajectories by task_id
2. Format into DPO dataset
3. LoRA fine-tune Qwen3-Coder-30B-A3B
4. Evaluate on held-out HumanEval/MBPP

See `config/pipeline.yaml` for LoRA hyperparameters.
