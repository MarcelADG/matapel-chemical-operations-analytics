"""Hand-calculated boundaries and source-independent reproducibility checks."""
import json,tempfile,unittest
from pathlib import Path
from src.supply_service_demo import analyze,cluster_interval,make_scenario,generate,percentile

class SupplyServiceTest(unittest.TestCase):
    def setUp(self):
        self.inventory=[{'sku':'DEMO-SKU','warehouse':'DEMO-WH','uom':'KG','event_date':d,'direction':k,'quantity':q} for d,k,q in [('2023-12-31','Opening',100),('2024-07-10','In',40),('2024-08-31','Out',-25),('2024-09-01','Out',-70)]]
        self.policy=[{'sku':'DEMO-SKU','uom':'KG','minimum_level':120,'reference_date':'2024-09-15'}]
        self.row={'flow':'Supplier receipt','event_id':'DEMO-EVENT','order_id':'DEMO-ORDER','receipt_id':'DEMO-RECEIPT','supplier_id':'DEMO-SUPPLIER','sku':'DEMO-SKU','warehouse':'DEMO-WH','order_date':'2024-07-01','recorded_promise':'2024-07-04','actual_date':'2024-07-06','gross_quantity':10,'return_quantity':2,'net_quantity':8}
    def run_case(self,rows):return analyze(self.inventory,rows,self.policy,draws=200)
    def test_opening_signed_outflow_and_cutoff(self):
        r=self.run_case([self.row]);self.assertEqual(r['positions'][0]['closing_quantity'],115);self.assertEqual(r['positions'][0]['issued_signed_quantity'],-25)
    def test_current_policy_is_company_sku_not_repeated_per_warehouse(self):
        self.inventory.append({'sku':'DEMO-SKU','warehouse':'DEMO-WH-SECOND','uom':'KG','event_date':'2023-12-31','direction':'Opening','quantity':10})
        r=self.run_case([self.row]);self.assertEqual(r['current_reference_review'],[{'review_status':'at_or_above_current_reference','sku_unit_rows':1}])
    def test_exact_lateness_and_lead(self):
        r=self.run_case([self.row])['service_monthly'][0];self.assertEqual((r['late_share'],r['lead_days_median'],r['lead_days_p90']),(1,5,5))
    def test_missing_promise_does_not_become_ontime(self):
        r=self.run_case([{**self.row,'recorded_promise':None}]);self.assertEqual(r['service_monthly'],[]);self.assertEqual(r['eligibility_exclusions'][0]['reason'],'missing_or_invalid_date')
    def test_zero_quantity_excluded(self):
        r=self.run_case([{**self.row,'gross_quantity':0}]);self.assertEqual(r['service_monthly'],[])
    def test_after_cutoff_excluded(self):
        r=self.run_case([{**self.row,'actual_date':'2024-09-01'}]);self.assertEqual(r['eligibility_exclusions'][0]['reason'],'after_cutoff')
    def test_return_error_visible_without_repair(self):
        r=self.run_case([{**self.row,'net_quantity':9}]);self.assertEqual(r['quantity_quality'][0]['return_identity_exception_rows'],1);self.assertEqual(r['service_monthly'][0]['eligible_export_rows'],1)
    def test_different_lines_same_candidate_key_retained(self):
        r=self.run_case([self.row,{**self.row,'event_id':'DEMO-SECOND','gross_quantity':20,'net_quantity':18}]);self.assertEqual(r['source_line_grain_review']['rows_in_collision_groups'],2);self.assertEqual(r['service_monthly'][0]['eligible_export_rows'],2)
    def test_cluster_bootstrap_resamples_orders_together(self):
        rows=[{'order_id':'A','late':0}]*8+[{'order_id':'B','late':1}]*2;lo,hi,n=cluster_interval(rows,draws=500);self.assertEqual((lo,hi,n),(0,1,2))
    def test_linear_percentile(self):self.assertEqual(percentile([0,10,20],.9),18)
    def test_reproducible_public_aggregates_no_event_level_export(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            generate(Path(a),draws=200);generate(Path(b),draws=200)
            fa={p.name:p.read_bytes() for p in Path(a).iterdir()};fb={p.name:p.read_bytes() for p in Path(b).iterdir()};self.assertEqual(fa,fb)
            self.assertFalse(any('positions' in n or 'event' in n for n in fa));self.assertFalse(json.loads(fa['provenance.json'])['event_level_inputs_exported'])

if __name__=='__main__':unittest.main()
