"""Independently fictional opening-stock and fulfilled-row service demonstration.

Reads method SQL only. No company files, fitted parameters or real records are
read. The generated scenario is illustrative and makes no business-impact claim.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,random,sqlite3,statistics
from collections import defaultdict
from datetime import date,timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CLASSIFICATION='SYNTHETIC: independently invented demonstration, not company results'
SEED=723091
WINDOW_START='2024-07-01'
CUTOFF='2024-08-31'

def percentile(values,q):
    a=sorted(values)
    if not a:return None
    t=(len(a)-1)*q;i=int(t)
    return a[i]+(a[min(i+1,len(a)-1)]-a[i])*(t-i)

def cluster_interval(rows,draws=1200,seed=SEED+17):
    """Resample order clusters; statistic remains fulfilled-row late fraction."""
    clusters=defaultdict(list)
    for r in rows:clusters[r['order_id']].append(int(r['late']))
    groups=[clusters[k] for k in sorted(clusters)]
    if not groups:return (None,None,0)
    rng=random.Random(seed);boot=[]
    for _ in range(draws):
        selected=[groups[rng.randrange(len(groups))] for _ in groups]
        boot.append(sum(sum(g) for g in selected)/sum(len(g) for g in selected))
    return percentile(boot,.025),percentile(boot,.975),len(groups)

def make_scenario(seed=SEED):
    rng=random.Random(seed);inventory=[];service=[];policy=[]
    for i in range(18):
        sku=f'DEMO-SKU-{i+1:03d}';uom=['KG','LITRE','PIECE'][i%3]
        policy.append({'sku':sku,'uom':uom,'minimum_level':rng.randrange(150,600),'reference_date':'2024-09-15'})
        for w in ['DEMO-WH-A','DEMO-WH-B']:
            balance=rng.randrange(80,350)
            inventory.append({'sku':sku,'warehouse':w,'uom':uom,'event_date':'2023-12-31','direction':'Opening','quantity':balance})
            for month in range(1,10):
                received=rng.randrange(20,140);issued=rng.randrange(0,min(balance+received,170)+1)
                inventory.extend([
                    {'sku':sku,'warehouse':w,'uom':uom,'event_date':f'2024-{month:02d}-05','direction':'In','quantity':received},
                    {'sku':sku,'warehouse':w,'uom':uom,'event_date':f'2024-{month:02d}-20','direction':'Out','quantity':-issued}])
                balance+=received-issued
    for flow,n in [('Customer delivery',80),('Supplier receipt',40)]:
        for month in [7,8,9]:
            count=n if month<9 else 6
            for i in range(count):
                actual=date(2024,month,rng.randrange(1,29));lead=rng.randrange(0,38 if flow=='Supplier receipt' else 16)
                order=actual-timedelta(days=lead);promise=order+timedelta(days=max(0,lead+rng.choice([-8,-3,0,0,4,9])))
                qty=rng.randrange(5,120);returned=0 if rng.random()>.1 else rng.randrange(1,qty+1)
                service.append({'flow':flow,'event_id':f'DEMO-{flow[0]}-{month:02d}-{i:03d}',
                  'order_id':f'DEMO-{flow[0]}-ORDER-{month:02d}-{i//2:03d}',
                  'receipt_id':f'DEMO-{flow[0]}-RECEIPT-{month:02d}-{i:03d}',
                  'supplier_id':f'DEMO-SUPPLIER-{i%5+1:02d}' if flow=='Supplier receipt' else None,
                  'sku':f'DEMO-SKU-{i%18+1:03d}','warehouse':['DEMO-WH-A','DEMO-WH-B'][i%2],
                  'order_date':order.isoformat(),'recorded_promise':promise.isoformat(),'actual_date':actual.isoformat(),
                  'gross_quantity':qty,'return_quantity':returned,'net_quantity':qty-returned})
    # Deliberate review cases: source-line collisions are not silently deduplicated.
    source=next(r for r in service if r['flow']=='Supplier receipt')
    split={**source,'event_id':'DEMO-SPLIT-LINE','gross_quantity':17,'return_quantity':0,'net_quantity':17};service.append(split)
    service.extend([
      {**source,'event_id':'DEMO-MISSING-PROMISE','recorded_promise':None},
      {**source,'event_id':'DEMO-REVERSED-DATE','order_date':'2024-08-15','actual_date':'2024-07-14'},
      {**source,'event_id':'DEMO-RETURN-EXCEPTION','net_quantity':source['net_quantity']+2}])
    return inventory,service,policy

def analyze(inventory,service,policy,cutoff=CUTOFF,window_start=WINDOW_START,draws=1200):
    con=sqlite3.connect(':memory:');con.row_factory=sqlite3.Row
    con.executescript('''CREATE TABLE settings(cutoff TEXT,window_start TEXT);
      CREATE TABLE inventory(sku TEXT,warehouse TEXT,uom TEXT,event_date TEXT,direction TEXT,quantity REAL);
      CREATE TABLE service(flow TEXT,event_id TEXT,order_id TEXT,receipt_id TEXT,supplier_id TEXT,sku TEXT,warehouse TEXT,order_date TEXT,recorded_promise TEXT,actual_date TEXT,gross_quantity REAL,return_quantity REAL,net_quantity REAL);
      CREATE TABLE policy(sku TEXT,uom TEXT,minimum_level REAL,reference_date TEXT);''')
    con.execute('INSERT INTO settings VALUES(?,?)',(cutoff,window_start))
    for table,records in [('inventory',inventory),('service',service),('policy',policy)]:
        if not records:continue
        keys=list(records[0]);con.executemany(f'INSERT INTO {table}('+','.join(keys)+') VALUES('+','.join('?' for _ in keys)+')',[[r[k] for k in keys] for r in records])
    con.executescript((ROOT/'sql/06_synthetic_supply_service.sql').read_text())
    get=lambda query:[dict(r) for r in con.execute(query)]
    positions=get('SELECT * FROM quantity_position ORDER BY uom,sku,warehouse')
    unit_summary=get('SELECT uom,SUM(opening_quantity) opening_quantity,SUM(received_quantity) received_quantity,SUM(issued_signed_quantity) issued_signed_quantity,SUM(closing_quantity) closing_quantity FROM quantity_position GROUP BY uom ORDER BY uom')
    policy_summary=get('SELECT review_status,COUNT(*) sku_unit_rows FROM policy_reference_review GROUP BY review_status ORDER BY review_status')
    raw=get('SELECT * FROM service_review');valid=[r for r in raw if r['eligible']==1]
    monthly=[]
    for key in sorted({(r['flow'],r['actual_date'][:7]) for r in valid}):
        rows=[r for r in valid if (r['flow'],r['actual_date'][:7])==key]
        lo,hi,nclusters=cluster_interval(rows,draws=draws)
        monthly.append({'flow':key[0],'month':key[1],'eligible_export_rows':len(rows),'order_clusters':nclusters,'late_export_rows':sum(r['late'] for r in rows),'late_share':sum(r['late'] for r in rows)/len(rows),'order_cluster_bootstrap_low':lo,'order_cluster_bootstrap_high':hi,'lead_days_median':statistics.median(r['lead_days'] for r in rows),'lead_days_p90':percentile([r['lead_days'] for r in rows],.9)})
    quantities=get('SELECT flow,COUNT(*) source_rows,SUM(CASE WHEN ABS(gross_quantity-return_quantity-net_quantity)>0.0001 THEN 1 ELSE 0 END) return_identity_exception_rows FROM service GROUP BY flow ORDER BY flow')
    collisions=get('''SELECT COUNT(*) collision_groups,COALESCE(SUM(n),0) rows_in_collision_groups FROM
      (SELECT COUNT(*) n FROM service GROUP BY flow,order_id,receipt_id,sku,warehouse HAVING COUNT(*)>1)''')[0]
    exclusions=get('SELECT flow,reason,COUNT(*) export_rows FROM service_review WHERE eligible=0 GROUP BY flow,reason ORDER BY flow,reason')
    con.close()
    return {'positions':positions,'inventory_by_unit':unit_summary,'current_reference_review':policy_summary,'service_monthly':monthly,'quantity_quality':quantities,'source_line_grain_review':collisions,'eligibility_exclusions':exclusions}

def checks(result,inventory,service):
    rows=result['positions'];monthly=result['service_monthly']
    return {
      'quantity_rollforward_exact':all(abs(r['opening_quantity']+r['received_quantity']+r['issued_signed_quantity']-r['closing_quantity'])<1e-9 for r in rows),
      'closing_stock_nonnegative':all(r['closing_quantity']>=0 for r in rows),
      'outflows_keep_negative_sign':all(r['quantity']<=0 for r in inventory if r['direction']=='Out'),
      'after_cutoff_activity_exists_and_is_excluded':any(r['event_date']>CUTOFF for r in inventory) and sum(r['closing_quantity'] for r in rows)==sum(r['quantity'] for r in inventory if r['event_date']<=CUTOFF),
      'separate_units_preserved':{r['uom'] for r in result['inventory_by_unit']}=={'KG','LITRE','PIECE'},
      'service_months_only_july_august':{r['month'] for r in monthly}=={'2024-07','2024-08'},
      'bootstrap_contains_observed_share':all(0<=r['order_cluster_bootstrap_low']<=r['late_share']<=r['order_cluster_bootstrap_high']<=1 for r in monthly),
      'repeated_order_clusters_retained':all(r['order_clusters']<r['eligible_export_rows'] for r in monthly),
      'return_identity_exception_visible':sum(r['return_identity_exception_rows'] for r in result['quantity_quality'])==1,
      'source_line_collisions_visible':result['source_line_grain_review']['collision_groups']>=1,
      'invalid_dates_are_excluded':any(r['reason']=='receipt_before_order' for r in result['eligibility_exclusions']),
      'all_identifiers_fictional':all(r['sku'].startswith('DEMO-') and r['event_id'].startswith('DEMO-') for r in service),
    }

def write_csv(path,rows):
    if not rows:return
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def svg_chart(rows):
    width,height=820,390;parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">','<rect width="100%" height="100%" fill="white"/>','<g font-family="Arial,sans-serif" fill="#203247">','<text x="35" y="30" font-size="19" font-weight="bold">Synthetic recorded-promise lateness</text>','<text x="35" y="55" font-size="13">Invented fulfilled rows; whiskers resample orders. This is not OTIF.</text>']
    y=lambda p:310-210*p
    for tick in [0,.25,.5,.75,1]:parts.extend([f'<line x1="70" y1="{y(tick)}" x2="790" y2="{y(tick)}" stroke="#E2E7EC"/>',f'<text x="24" y="{y(tick)+4}" font-size="12">{tick:.0%}</text>'])
    for i,r in enumerate(rows):
        x=135+i*175;top=y(r['late_share']);color='#285C85' if r['flow']=='Customer delivery' else '#B96C30';lo=y(r['order_cluster_bootstrap_low']);hi=y(r['order_cluster_bootstrap_high'])
        parts.extend([f'<rect x="{x-30}" y="{top}" width="60" height="{310-top}" fill="{color}"/>',f'<line x1="{x}" y1="{lo}" x2="{x}" y2="{hi}" stroke="#203247" stroke-width="2"/>',f'<line x1="{x-7}" y1="{lo}" x2="{x+7}" y2="{lo}" stroke="#203247"/>',f'<line x1="{x-7}" y1="{hi}" x2="{x+7}" y2="{hi}" stroke="#203247"/>',f'<text x="{x}" y="{min(top,hi)-10}" text-anchor="middle" font-size="13">{r["late_share"]:.1%}</text>',f'<text x="{x}" y="335" text-anchor="middle" font-size="12">{r["flow"]}</text>',f'<text x="{x}" y="353" text-anchor="middle" font-size="12">{r["month"]}</text>'])
    return ''.join(parts)+ '</g></svg>'

def generate(output,draws=1200):
    inventory,service,policy=make_scenario();result=analyze(inventory,service,policy,draws=draws);qa=checks(result,inventory,service)
    if not all(qa.values()):raise AssertionError(qa)
    output.mkdir(parents=True,exist_ok=True)
    for key in ['inventory_by_unit','current_reference_review','service_monthly','quantity_quality','eligibility_exclusions']:write_csv(output/(key+'.csv'),result[key])
    # Only aggregated results are published. Generated event-level inputs stay in memory.
    public={k:v for k,v in result.items() if k!='positions'}
    public.update(data_classification=CLASSIFICATION,scenario_cutoff=CUTOFF,service_window_start=WINDOW_START,bootstrap_draws=draws,interpretation='Recorded-promise timing among fulfilled export rows. No official stock balance, fill rate, lost sales, net profit or causal improvement claim.')
    (output/'review.json').write_text(json.dumps(public,indent=2,sort_keys=True)+'\n');(output/'service_lateness.svg').write_text(svg_chart(result['service_monthly']))
    table='| Flow | Month | Rows | Late share | Order-cluster interval | P90 lead days |\n|---|---|---:|---:|---|---:|\n'
    for r in result['service_monthly']:table+=f'| {r["flow"]} | {r["month"]} | {r["eligible_export_rows"]} | {r["late_share"]:.1%} | {r["order_cluster_bootstrap_low"]:.1%}–{r["order_cluster_bootstrap_high"]:.1%} | {r["lead_days_p90"]:.1f} |\n'
    report=f'''# Synthetic supply and service review

{CLASSIFICATION}. All records, quantities, dates, policies and counterparties are invented from seed {SEED}. No company file or company aggregate is read or used to fit the scenario. Outputs contain aggregates only.

![Synthetic service comparison](service_lateness.svg)

{table}
The interval is a percentile bootstrap over order clusters within each flow/month, with {draws} draws. The statistic remains late fulfilled export rows divided by eligible fulfilled export rows. Repeated rows of an order are resampled together. Intervals describe this invented observed population and do not fix selection bias or establish future service probabilities.

## Inventory and source controls

Opening quantities plus already-negative outflows and positive inflows reconstruct stock through {CUTOFF}. Quantities stay separated by SKU, warehouse and unit; the published roll-up is by unit. September activity is excluded. The independently invented current policy reference is dated September 15 and is compared at company/SKU/unit scope for review only. It is not historical policy, a warehouse allocation or an automatic order recommendation. Inventory valuation and working-capital savings are not estimated.

Source-line key collisions are retained and reported, including different lines sharing an order/receipt/item/warehouse key. A deliberately inconsistent return identity is visible instead of being repaired silently. Missing promise dates and receipt-before-order rows are excluded from timing denominators. Recorded promises can have been revised; the data does not identify all requested lines, canceled or zero-delivery orders. No OTIF/fill-rate/causal-improvement claim is made.

{sum(qa.values())}/{len(qa)} scenario checks pass. Reproduce from the project root with `python -m src.supply_service_demo`. The generator reads method SQL only and writes these public aggregates; event-level generated inputs are not exported.
'''
    (output/'README.md').write_text(report)
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir()) if p.is_file() and p.name!='provenance.json'}
    manifest={'data_classification':CLASSIFICATION,'seed':SEED,'company_inputs_read':False,'calibrated_to_company_data':False,'event_level_inputs_exported':False,'source':'src/supply_service_demo.py and sql/06_synthetic_supply_service.sql','code_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'sql/06_synthetic_supply_service.sql']},'checks':qa,'files_sha256':hashes}
    (output/'provenance.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'output':str(output),'checks_passed':sum(qa.values()),'checks_total':len(qa),'classification':'synthetic aggregates only'}))
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,default=ROOT/'outputs/sample/supply_service');parser.add_argument('--bootstrap-draws',type=int,default=1200);a=parser.parse_args()
    if a.bootstrap_draws<200:parser.error('Use at least 200 bootstrap draws.')
    generate(a.output_dir.resolve(),draws=a.bootstrap_draws)
