# KurrentDB Process Event Prediction

Train a small language model to predict the next event in financial process workflows using event-sourced data from KurrentDB.

## What It Does

This project demonstrates how event-sourced data naturally fits AI training tasks:

1. **Generates financial process events** - Trade lifecycle, payments, risk management, compliance, and account opening workflows
2. **Fine-tunes a small LLM** - SmolLM2-360M learns to predict "what happens next" in a process
3. **Deploys as an anomaly detector** - An agentic orchestrator monitors event streams and flags anomalies

### Benchmark Results

| Metric | Value |
|--------|-------|
| **Recall** | 100% - Caught every anomaly |
| **Precision** | 58.8% |
| **F1 Score** | 74.1% |
| **Training Time** | 27 minutes |
| **Model Size** | 360M parameters |

## Prerequisites

```bash
# Python 3.10+
pip install torch transformers datasets peft trl accelerate
pip install kurrentdbclient

# Docker (for KurrentDB)
docker --version
```

## Quick Start

### 1. Start KurrentDB

```bash
docker-compose up -d
# Verify: http://localhost:2113
```

### 2. Generate Training Data

```bash
python populate_process_events.py --num-sequences 200
```

Creates ~1,500 training examples from 200 process sequences across 5 workflow types.

### 3. Train the Model

```bash
python train_local.py \
    --model HuggingFaceTB/SmolLM2-360M-Instruct \
    --data output/data/process_prediction_train.jsonl \
    --output ./output/process-model \
    --epochs 3
```

### 4. Run the Benchmark

```bash
python agentic_benchmark.py --model ./output/process-model
```

## Project Structure

```
kurrent_models/
├── populate_process_events.py  # Generate events + training data
├── train_local.py              # Fine-tune with LoRA
├── agentic_benchmark.py        # Anomaly detection benchmark
├── docker-compose.yaml         # KurrentDB container
├── src/
│   ├── events/
│   │   └── process_events.py   # 30+ financial event types
│   ├── process_generator.py    # Sequence generator
│   └── kurrentdb_client.py     # KurrentDB wrapper
└── output/
    ├── data/                   # Training data
    ├── process-model/          # Trained model
    └── reports/                # Benchmark results
```

## Process Workflows

The model learns these financial process patterns:

**Trade Lifecycle**
```
OrderSubmitted → OrderValidated → OrderRouted → OrderFilled → TradeBooked → TradeSettled
```

**Payment Processing**
```
PaymentInitiated → PaymentValidated → PaymentApproved → PaymentExecuted → PaymentCompleted
```

**Risk Management**
```
RiskLimitBreached → RiskAlertCreated → RiskMitigationStarted → RiskAlertResolved
```

**Compliance**
```
ComplianceCheckTriggered → ComplianceFlagRaised → ComplianceReviewCompleted → ComplianceCaseClosed
```

**Account Opening**
```
AccountApplicationSubmitted → AccountKYCStarted → AccountKYCCompleted → AccountOpened
```

## Memory Options

If you run out of GPU memory:

```bash
python train_local.py --batch-size 1 --max-seq-length 256
```

## Built With

- [KurrentDB](https://kurrent.io/) - Event store database
- [SmolLM2](https://huggingface.co/HuggingFaceTB/SmolLM2-360M-Instruct) - Base model
- [TRL](https://huggingface.co/docs/trl) - Training library
- [LoRA](https://arxiv.org/abs/2106.09685) - Parameter-efficient fine-tuning

## License

MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
