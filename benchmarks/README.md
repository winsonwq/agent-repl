# Benchmarks

Run the token/context comparison:

```bash
python -m pip install -e '.[benchmark]'
python benchmarks/token_cost.py
```

The script overwrites `results/token-cost.json` and `results/token-cost.md` deterministically for the available tokenizer. Checked-in results use `tiktoken cl100k_base`.

The benchmark compares one real unified Skill with a declared fixture of seven deliberately small scattered CLI guides. It measures text presented to a model, not runtime CPU, API billing, model accuracy, or latency. Use the output to find architectural break-even points and context regressions, not to claim provider-independent token counts.
