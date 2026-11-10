"""Check published hashes, event metrics, baseline decisions and local links.

Run from any directory: python scripts/check_evidence.py
This checks the public extracts; use check_run.py for a complete managed run.
"""
from pathlib import Path
import csv, hashlib, json, math, re
ROOT=Path(__file__).resolve().parents[1]
EV=ROOT/'docs/evidence'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
errors=[]; hashed=0; sources=0; decisions=0; disagreement=0; evaluated=0
for p in sorted((EV/'runs').glob('*/manifest.json')):
 m=json.loads(p.read_text()); folder=p.parent
 for relative,digest in m['source_sha256'].items():
  sources+=1
  if sha(ROOT/relative)!=digest: errors.append(f'source hash {relative}')
 for relative,digest in m['published_outputs_sha256'].items():
  hashed+=1
  if sha(folder/relative)!=digest: errors.append(f'output hash {folder.name}/{relative}')
 for ef in folder.glob('*_evaluation.json'):
  e=json.loads(ef.read_text()); met=e['full_sample']['major']; stem=ef.name.removesuffix('_evaluation.json')
  with (folder/(stem+'_events_major.csv')).open() as f: events=list(csv.DictReader(f))
  with (folder/(stem+'_signals_major.csv')).open() as f: signals=list(csv.DictReader(f))
  values={'n_peaks':len(events),'n_unique_detected_peaks':sum(x['detected']=='True' for x in events),'n_signals':len(signals),'n_detected':sum(x['classification']=='detected' for x in signals)}
  for k,v in values.items():
   if met[k]!=v: errors.append(f'{folder.name}/{stem}/{k}: {v} != {met[k]}')
  if signals:
   prec=100*values['n_detected']/len(signals)
   if not math.isclose(prec,met['precision_pct'],abs_tol=1e-10):errors.append(f'precision {ef}')
  evaluated+=1
 for w in folder.glob('*_warning_data.csv'):
  if '_baseline_' in w.name:continue
  with w.open() as f: rows=list(csv.DictReader(f))
  base=w.with_name(w.name.replace('_warning_data.csv','_baseline_rolling_max_warning_data.csv'))
  with base.open() as f: controls=list(csv.DictReader(f))
  assert len(rows)==len(controls)
  threshold=m['config']['threshold_warning']
  for a,b in zip(rows,controls):
   assert a['date']==b['date']
   av=float(a['W_i']); bv=float(b['W_i'])
   assert math.isclose(av,float(a['M_i'])*int(a['C_i']),abs_tol=1e-8,rel_tol=1e-10)
   decisions+=1; disagreement+=(av>threshold)!=(bv>threshold)
link_errors=[]
for p in ROOT.rglob('*.md'):
 if '.git' in p.parts:continue
 for target in re.findall(r'(?<!!)\[[^\]]*\]\(([^ )]+)',p.read_text()):
  if re.match(r'\w+://',target) or target.startswith('#'):continue
  if '<' in target:continue
  path=(p.parent/target.split('#')[0])
  if not path.exists():link_errors.append(f'{p.relative_to(ROOT)} -> {target}')
result={'passed':not errors and not link_errors,'recorded_source_hashes_checked':sources,'published_output_hashes_checked':hashed,'independently_recounted_major_catalog_evaluations':evaluated,'qca_vs_baseline_rows_including_overlapping_runs':decisions,'binary_decision_disagreements':disagreement,'local_markdown_links_checked':True,'errors':errors,'broken_links':link_errors,'scope':'Publication checks plus exact source matches to 20 saved runs; no new fitting or full recomputation of these historical runs.'}
print(json.dumps(result,indent=2))
raise SystemExit(0 if result['passed'] else 1)
