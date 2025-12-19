#!/usr/bin/env python3
"""
Local Training Script for Financial Calculation Model
Runs on your local GPU (or CPU with reduced settings)

Training Approach:
- We use SFT (Supervised Fine-Tuning) which teaches the model to produce
  outputs that match our training examples
- The "reasoning" is learned through chain-of-thought examples where we
  show step-by-step solutions
- Event sequences teach temporal and causal relationships
- The model learns to mimic the reasoning patterns in training data

For deeper reasoning training, consider:
- DPO: Train with preference pairs (good vs bad reasoning)
- GRPO: Online RL with reward signals
- Process Reward Models: Reward intermediate steps
"""

import argparse
import json
import sys
from pathlib import Path

# Check for required packages
try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, TaskType
    from trl import SFTTrainer, SFTConfig
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("\nInstall with: pip install torch transformers datasets peft trl accelerate")
    sys.exit(1)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def check_hardware():
    """Check available hardware"""
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"GPU: {gpu_name} ({gpu_mem:.1f} GB)")
        return "cuda"
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        print("Using Apple Silicon MPS")
        return "mps"
    else:
        print("No GPU detected - using CPU (will be slow)")
        return "cpu"


def load_or_generate_data(data_path: str = None, num_portfolios: int = 20):
    """Load existing data or generate new training data"""

    if data_path and Path(data_path).exists():
        print(f"Loading data from {data_path}")
        data = []
        with open(data_path, 'r') as f:
            if data_path.endswith('.jsonl'):
                for line in f:
                    data.append(json.loads(line))
            else:
                data = json.load(f)
        return Dataset.from_list(data)

    print(f"Generating training data from {num_portfolios} portfolios...")

    from data_generator import FinancialEventGenerator
    from tokenizer import TrainingDatasetBuilder, FinancialEventTokenizer

    # Generate events
    generator = FinancialEventGenerator(seed=42)
    events = generator.generate_comprehensive_dataset(num_portfolios=num_portfolios)

    # Convert to training format
    events_dicts = [
        {"event_type": type(e).__name__, "data": json.loads(e.to_json())}
        for e in events
    ]

    tokenizer = FinancialEventTokenizer()
    builder = TrainingDatasetBuilder(tokenizer)
    training_data = builder.build_from_events(events_dicts, output_format="messages")

    print(f"Generated {len(training_data)} training examples")
    return Dataset.from_list(training_data)


def train_local(
    model_name: str = "Qwen/Qwen2.5-0.5B-Instruct",
    data_path: str = None,
    output_dir: str = "./output/financial-model",
    num_epochs: int = 3,
    batch_size: int = 2,
    learning_rate: float = 2e-4,
    max_seq_length: int = 512,
    lora_r: int = 16,
    num_portfolios: int = 20,
    use_4bit: bool = False,
):
    """
    Train a financial calculation model locally.

    Args:
        model_name: Base model to fine-tune
        data_path: Path to training data (None to generate)
        output_dir: Where to save the model
        num_epochs: Training epochs
        batch_size: Batch size (reduce if OOM)
        learning_rate: Learning rate
        max_seq_length: Max sequence length (reduce if OOM)
        lora_r: LoRA rank (reduce if OOM)
        num_portfolios: Portfolios to generate if no data
        use_4bit: Use 4-bit quantization (saves memory)
    """

    print("=" * 60)
    print("Local Financial Model Training")
    print("=" * 60)

    # Check hardware
    device = check_hardware()

    # Load data
    dataset = load_or_generate_data(data_path, num_portfolios)
    print(f"Dataset size: {len(dataset)} examples")

    # Split data
    if len(dataset) > 50:
        split = dataset.train_test_split(test_size=0.1, seed=42)
        train_dataset = split["train"]
        eval_dataset = split["test"]
    else:
        train_dataset = dataset
        eval_dataset = None

    print(f"Train: {len(train_dataset)}, Eval: {len(eval_dataset) if eval_dataset else 0}")

    # Load model
    print(f"\nLoading model: {model_name}")

    model_kwargs = {
        "trust_remote_code": True,
        "device_map": "auto" if device == "cuda" else None,
    }

    if device == "cuda":
        model_kwargs["torch_dtype"] = torch.bfloat16
        if use_4bit:
            from transformers import BitsAndBytesConfig
            model_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_quant_type="nf4",
            )
    elif device == "mps":
        model_kwargs["torch_dtype"] = torch.float16
    else:
        model_kwargs["torch_dtype"] = torch.float32

    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs)

    # Configure LoRA
    print("\nConfiguring LoRA...")
    peft_config = LoraConfig(
        r=lora_r,
        lora_alpha=lora_r * 2,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        task_type=TaskType.CAUSAL_LM,
    )

    # Training config
    training_args = SFTConfig(
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        gradient_accumulation_steps=8 // batch_size,  # Effective batch = 8
        learning_rate=learning_rate,
        lr_scheduler_type="cosine",
        warmup_ratio=0.1,
        logging_steps=10,
        save_strategy="epoch",
        eval_strategy="epoch" if eval_dataset else "no",
        max_length=max_seq_length,  # TRL uses max_length not max_seq_length
        packing=False,
        # Memory optimization
        gradient_checkpointing=True if device == "cuda" else False,
        bf16=device == "cuda",
        fp16=device == "mps",
        # Disable hub push for local
        push_to_hub=False,
        report_to="none",
    )

    # Create trainer
    print("\nStarting training...")
    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,  # TRL now uses processing_class instead of tokenizer
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        peft_config=peft_config,
        args=training_args,
    )

    # Train
    trainer.train()

    # Save
    print(f"\nSaving model to {output_dir}")
    trainer.save_model()
    tokenizer.save_pretrained(output_dir)

    print("\n" + "=" * 60)
    print("Training Complete!")
    print("=" * 60)
    print(f"\nModel saved to: {output_dir}")
    print(f"\nTo use the model:")
    print(f'  from transformers import pipeline')
    print(f'  pipe = pipeline("text-generation", model="{output_dir}")')
    print(f'  pipe("Calculate the NPV of...")')

    return trainer


def main():
    parser = argparse.ArgumentParser(
        description="Train financial calculation model locally",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick test (small dataset, fast)
  python train_local.py --num-portfolios 10 --epochs 1

  # Full training with existing data
  python train_local.py --data output/data/financial_calc_train.jsonl

  # Use smaller model for limited GPU
  python train_local.py --model HuggingFaceTB/SmolLM2-360M-Instruct

  # Save memory with 4-bit quantization
  python train_local.py --use-4bit --batch-size 1
        """
    )

    parser.add_argument(
        "--model",
        default="HuggingFaceTB/SmolLM2-360M-Instruct",
        help="Base model (default: HuggingFaceTB/SmolLM2-360M-Instruct)"
    )
    parser.add_argument(
        "--data",
        default=None,
        help="Path to training data (generates if not provided)"
    )
    parser.add_argument(
        "--output",
        default="./output/financial-model",
        help="Output directory (default: ./output/financial-model)"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=3,
        help="Number of epochs (default: 3)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=2,
        help="Batch size - reduce if OOM (default: 2)"
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=2e-4,
        help="Learning rate (default: 2e-4)"
    )
    parser.add_argument(
        "--max-seq-length",
        type=int,
        default=512,
        help="Max sequence length - reduce if OOM (default: 512)"
    )
    parser.add_argument(
        "--lora-r",
        type=int,
        default=16,
        help="LoRA rank (default: 16)"
    )
    parser.add_argument(
        "--num-portfolios",
        type=int,
        default=20,
        help="Portfolios to generate if no data (default: 20)"
    )
    parser.add_argument(
        "--use-4bit",
        action="store_true",
        help="Use 4-bit quantization (saves GPU memory)"
    )

    args = parser.parse_args()

    train_local(
        model_name=args.model,
        data_path=args.data,
        output_dir=args.output,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        max_seq_length=args.max_seq_length,
        lora_r=args.lora_r,
        num_portfolios=args.num_portfolios,
        use_4bit=args.use_4bit,
    )


if __name__ == "__main__":
    main()
