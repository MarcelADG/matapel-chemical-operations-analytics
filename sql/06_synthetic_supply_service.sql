-- Independently invented demonstration. All quantities retain their source sign.
CREATE VIEW quantity_position AS
SELECT sku,warehouse,uom,
 SUM(CASE WHEN direction='Opening' THEN quantity ELSE 0 END) opening_quantity,
 SUM(CASE WHEN direction='In' THEN quantity ELSE 0 END) received_quantity,
 SUM(CASE WHEN direction='Out' THEN quantity ELSE 0 END) issued_signed_quantity,
 SUM(quantity) closing_quantity
FROM inventory WHERE event_date<=(SELECT cutoff FROM settings)
GROUP BY sku,warehouse,uom;

CREATE VIEW policy_reference_review AS
WITH company_item_unit AS (
 SELECT sku,uom,SUM(closing_quantity) closing_quantity
 FROM quantity_position GROUP BY sku,uom
)
SELECT q.*,p.minimum_level,p.reference_date,
 CASE WHEN p.sku IS NULL THEN 'missing_reference'
      WHEN q.closing_quantity<p.minimum_level THEN 'below_current_reference'
      ELSE 'at_or_above_current_reference' END review_status
FROM company_item_unit q LEFT JOIN policy p ON p.sku=q.sku AND p.uom=q.uom;

CREATE VIEW service_review AS
WITH dated AS (
 SELECT *,CAST(julianday(actual_date)-julianday(order_date) AS INTEGER) lead_days,
 CAST(julianday(actual_date)-julianday(recorded_promise) AS INTEGER) delay_days
 FROM service
),reasoned AS (
 SELECT *,CASE
 WHEN actual_date IS NULL OR order_date IS NULL OR recorded_promise IS NULL
   OR julianday(actual_date) IS NULL OR julianday(order_date) IS NULL OR julianday(recorded_promise) IS NULL THEN 'missing_or_invalid_date'
 WHEN actual_date<(SELECT window_start FROM settings) THEN 'before_review_window'
 WHEN actual_date>(SELECT cutoff FROM settings) THEN 'after_cutoff'
 WHEN lead_days<0 THEN 'receipt_before_order'
 WHEN recorded_promise<order_date THEN 'promise_before_order'
 WHEN gross_quantity IS NULL OR gross_quantity<=0 THEN 'nonpositive_original_quantity'
 ELSE 'eligible' END reason FROM dated
)
SELECT *,CASE WHEN reason='eligible' THEN 1 ELSE 0 END eligible,
 CASE WHEN delay_days>0 THEN 1 ELSE 0 END late FROM reasoned;
