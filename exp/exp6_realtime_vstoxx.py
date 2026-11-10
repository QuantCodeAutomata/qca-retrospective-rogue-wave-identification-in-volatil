"""Exp6: causal expanding-prefix VSTOXX warning, with explicit ex-post evaluation."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from exp.common import run_realtime_experiment


def run_exp6(highs=None, config=None, output_dir=None, progress=True, *, context=None):
    return run_realtime_experiment('VSTOXX', 6, highs, config, output_dir, progress, context=context)


if __name__ == '__main__':
    from run_experiments import main
    main(default_index='VSTOXX', default_experiments='6')
