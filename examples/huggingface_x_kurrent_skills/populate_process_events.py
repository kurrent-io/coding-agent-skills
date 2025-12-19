#!/usr/bin/env python3
"""
Populate KurrentDB with Financial Process Events

Creates realistic financial process sequences and stores them in KurrentDB.
Then generates training data for next-event prediction.

This showcases KurrentDB's strength in event sourcing for financial workflows:
- Trade lifecycle (order → settlement)
- Payment processing (initiation → completion)
- Risk management (breach → resolution)
- Compliance workflow (flag → closure)
- Account management (application → opening)
"""

import argparse
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from process_generator import ProcessEventGenerator, create_prediction_training_data


def populate_kurrentdb(streams: dict, client) -> int:
    """Populate KurrentDB with process event streams"""
    total_events = 0

    for stream_name, events in streams.items():
        for event in events:
            event_data = json.dumps(event["data"]).encode('utf-8')
            client.append_to_stream(
                stream_name=stream_name,
                event_type=event["event_type"],
                data=event_data
            )
            total_events += 1

    return total_events


def main():
    parser = argparse.ArgumentParser(
        description="Populate KurrentDB with financial process events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate 100 process sequences
  python populate_process_events.py --num-sequences 100

  # Generate without KurrentDB (just training data)
  python populate_process_events.py --no-kurrentdb

  # Full pipeline with 500 sequences
  python populate_process_events.py --num-sequences 500
        """
    )

    parser.add_argument(
        "--num-sequences",
        type=int,
        default=200,
        help="Number of process sequences to generate (default: 200)"
    )
    parser.add_argument(
        "--output-dir",
        default="output/data",
        help="Output directory for training data (default: output/data)"
    )
    parser.add_argument(
        "--no-kurrentdb",
        action="store_true",
        help="Skip KurrentDB population (just generate training data)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Financial Process Event Generation")
    print("=" * 60)

    # Generate events
    print(f"\nGenerating {args.num_sequences} process sequences...")
    generator = ProcessEventGenerator(seed=args.seed)
    all_events, streams = generator.generate_dataset(num_sequences=args.num_sequences)

    print(f"Generated {len(all_events)} events in {len(streams)} streams")

    # Count by process type
    process_counts = {"trade": 0, "payment": 0, "risk": 0, "compliance": 0, "account": 0}
    for stream_name in streams:
        for ptype in process_counts:
            if stream_name.startswith(ptype):
                process_counts[ptype] += 1
                break

    print("\nProcess distribution:")
    for ptype, count in process_counts.items():
        print(f"  {ptype}: {count} sequences")

    # Populate KurrentDB
    if not args.no_kurrentdb:
        print("\nConnecting to KurrentDB...")
        try:
            from kurrentdb_client import KurrentDBClient
            client = KurrentDBClient()

            print("Populating KurrentDB streams...")
            total = populate_kurrentdb(streams, client)
            print(f"Stored {total} events in KurrentDB")

        except Exception as e:
            print(f"Warning: Could not connect to KurrentDB: {e}")
            print("Continuing with training data generation only...")

    # Generate training data
    print("\nCreating prediction training data...")
    output_path = Path(args.output_dir) / "process_prediction_train.jsonl"
    training_data = create_prediction_training_data(streams, str(output_path))

    # Show sample
    print("\nSample training examples:")
    print("-" * 40)
    for i, example in enumerate(training_data[:3]):
        user_msg = example["messages"][1]["content"]
        assistant_msg = example["messages"][2]["content"]
        print(f"\nExample {i+1}:")
        print(f"Input: {user_msg[:100]}...")
        print(f"Target: {assistant_msg}")

    print("\n" + "=" * 60)
    print("Generation Complete!")
    print("=" * 60)
    print(f"\nTotal events: {len(all_events)}")
    print(f"Total streams: {len(streams)}")
    print(f"Training examples: {len(training_data)}")
    print(f"Training data saved to: {output_path}")

    print("\nNext steps:")
    print("  1. Train model: python train_local.py --data output/data/process_prediction_train.jsonl")
    print("  2. Evaluate: python evaluate_process_model.py")

    return streams, training_data


if __name__ == "__main__":
    main()
