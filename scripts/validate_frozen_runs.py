"""Reproduce frozen VIX/VXO runs, compare historical outputs and recount metrics.

Requires an existing audit data directory supplied explicitly; downloads and
server access are never performed. Fresh outputs and input snapshots are saved.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
JOBS = ['vix_2025_default', 'vix_2025_all_bins', 'vxo_2020_default',
        'vxo_2020_all_bins', 'vix_2025_all_bins_ghost', 'vxo_2020_all_bins_ghost',
        'vix_2024_default']


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False, default=str)+'\n')


def warning_table(path):
    return pd.read_csv(path, parse_dates=['date','event_date','date_max_grad'], float_precision='round_trip')


def compare_previous(old, new, index):
    number = 4 if index == 'VIX' else 5
    stem = f'exp{number}_{index.lower()}'
    before, after = warning_table(old/f'{stem}_warning_data.csv'), warning_table(new/f'{stem}_warning_data.csv')
    if before.shape != after.shape or list(before.columns) != list(after.columns):
        raise AssertionError('Warning table structure changed')
    numeric = ['M_i','C_i','W_i','argmax_offset']
    differences = {}
    for column in numeric:
        a,b=before[column].to_numpy(),after[column].to_numpy()
        np.testing.assert_allclose(a,b,rtol=1e-10,atol=1e-8,err_msg=column)
        differences[column]=float(np.max(np.abs(a-b)))
    for column in ['date','event_date','date_max_grad']:
        pd.testing.assert_series_equal(before[column],after[column])
    bm=json.loads((old/f'{stem}_metrics.json').read_text())
    am=json.loads((new/f'{stem}_metrics.json').read_text())
    fields=0
    for section in ['full_sample','after_warmup','endpoint_censored','out_of_sample']:
        left=bm[section]['metrics'] if section=='out_of_sample' else bm[section]
        right=am[section]['metrics'] if section=='out_of_sample' else am[section]
        for severity, values in left.items():
            for key,value in values.items():
                if right[severity][key] != value:
                    raise AssertionError(f'{section}/{severity}/{key}: {value} != {right[severity][key]}')
                fields+=1
    for severity in ['major','lower']:
        a=pd.read_csv(old/f'{stem}_signals_{severity}.csv')
        b=pd.read_csv(new/f'{stem}_signals_{severity}.csv')
        pd.testing.assert_frame_equal(a,b,check_dtype=False)
    return {'warning_rows':len(before),'max_absolute_differences':differences,
            'metric_fields_equal':fields,'episode_ledgers_equal':True,
            'paper_major':am['label_catalogs']['paper']['full_sample']['major'],
            'baseline_disagreement_days':am['baseline']['disagreement_days']}


def execute(name, reference, destination, reuse):
    old=reference/'runs'/name
    previous=json.loads((old/'run_metadata.json').read_text())
    index=previous['index']; cfg=previous['config']
    config_path=destination/'configs'/f'{name}.json'
    dump(config_path,cfg)
    output=destination/'runs'/name
    log=destination/'logs'/f'{name}.log'
    log.parent.mkdir(parents=True,exist_ok=True)
    can_reuse=reuse and (output/'run_metadata.json').is_file()
    if can_reuse:
        meta=json.loads((output/'run_metadata.json').read_text())
        if meta['status']!='completed': raise ValueError(f'{name} is not a completed reusable run')
        for rel,digest in meta['source_sha256'].items():
            if hashlib.sha256((REPO/rel).read_bytes()).hexdigest()!=digest:
                raise ValueError(f'{name} source changed: {rel}; use a fresh destination')
    else:
        experiments='all' if 'ghost' not in name and '2024' not in name else str(4 if index=='VIX' else 5)
        cmd=[sys.executable,str(REPO/'run_experiments.py'),'--index',index,
             '--csv',str(reference/'data'/f'{index}.csv'),'--config',str(config_path),
             '--experiments',experiments,'--labels','both','--baseline','rolling_max',
             '--output',str(output),'--quiet']
        if experiments=='all': cmd.append('--paper-diagnostics')
        with log.open('w') as stream:
            completed=subprocess.run(cmd,cwd=REPO,stdout=stream,stderr=subprocess.STDOUT)
        if completed.returncode: raise RuntimeError(f'{name} failed; see {log}')
    receipt=destination/'evidence'/f'{name}_independent.json'
    checked=subprocess.run([sys.executable,str(REPO/'scripts/check_run.py'),
                            '--run',str(output),'--output',str(receipt)],cwd=REPO,
                           capture_output=True,text=True)
    if checked.returncode:
        raise RuntimeError(f'Independent validation failed: {name}: {checked.stdout} {checked.stderr}')
    return {'name':name,'status':'passed','comparison':compare_previous(old,output,index),
            'independent_receipt':str(receipt.relative_to(destination))}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--reuse-completed',action='store_true')
    args=parser.parse_args()
    reference=args.reference_root.resolve(); destination=args.output.resolve()
    if args.workers<1 or args.workers>4: parser.error('workers must be between 1 and 4')
    destination.mkdir(parents=True,exist_ok=True)
    results=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(execute,name,reference,destination,args.reuse_completed):name for name in JOBS}
        for future in as_completed(futures):
            name=futures[future]
            try: result=future.result()
            except Exception as exc: result={'name':name,'status':'failed','error':str(exc)}
            results.append(result)
            print(json.dumps(result,ensure_ascii=False),flush=True)
            dump(destination/'progress.json',results)
    if any(r['status']!='passed' for r in results):
        raise SystemExit('Some runs failed; inspect progress.json and logs, then use a fresh run directory for failed runs.')
    short=warning_table(destination/'runs/vix_2024_default/exp4_vix_warning_data.csv')
    full=warning_table(destination/'runs/vix_2025_default/exp4_vix_warning_data.csv')
    pd.testing.assert_frame_equal(short,full.iloc[:len(short)].reset_index(drop=True))
    summary={'status':'passed','completed_utc':datetime.now(timezone.utc).isoformat(),
             'runs':sorted(results,key=lambda r:r['name']),
             'causal_prefix':{'compared_rows':len(short),'exactly_unchanged':True},
             'vstoxx':{'status':'unavailable','reason':'Actual daily High data and author snapshot are unavailable'}}
    dump(destination/'validation_summary.json',summary)
    print(f'All {len(results)} runs passed; {len(short)} prior VIX rows unchanged.',flush=True)


if __name__=='__main__': main()
