# Experiments Directory Structure

This directory contains all experiment outputs and results from SentientResearchAgent runs.

## Directory Structure

```
experiments/
├── configs/              # Experiment configuration files
│   └── {name}.yaml      # Named configuration files for reproducibility
├── results/             # Experiment results organized by timestamp
│   └── {timestamp}_{name}/
│       ├── config.yaml  # Configuration used for this run
│       ├── results.json # Final results and metrics
│       ├── traces/      # Detailed execution traces
│       └── logs/        # Execution logs
└── emergency_backups/   # Auto-saved states during crashes
```

## Usage

### Running an Experiment

1. Create or use an existing config in `configs/`
2. Run the experiment:
   ```bash
   python -m sentientresearchagent --config experiments/configs/my_experiment.yaml
   ```
3. Results will be saved to `results/{timestamp}_my_experiment/`

### Analyzing Results

Use the utility scripts in the `scripts/` directory:
- `aggregate_results.py` - Compile results across multiple runs
- `clean_old_experiments.py` - Remove old experiment data
- `archive_experiment.py` - Archive important experiments

### Best Practices

1. **Name your experiments**: Use descriptive names for configs and runs
2. **Document parameters**: Include comments in config files
3. **Regular cleanup**: Use cleanup scripts to manage disk space
4. **Archive important results**: Move significant results to a permanent location

## Git Ignore

This entire directory is ignored by git to prevent accidental commits of large result files.
To save specific results, copy them to a different location or create a separate results repository.