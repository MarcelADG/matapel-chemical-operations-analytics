# Opening inventory and fulfilled-row service analysis

The public case study demonstrates quantity reconstruction, date eligibility, source-line review and uncertainty using an independent seeded simulation. All rows, quantities, dates, policies and counterparties are fictional. No private file, business total, fitted distribution or company-derived coefficient is read by the generator. Only aggregate results are exported.

The scenario is set in 2024 to illustrate historical operations review. It was prepared as a retrospective portfolio demonstration. It is not evidence of a deliverable supplied during an internship or of measured employer impact.

## Reproduction

From the repository root with Python 3.10 or later:

```bash
python -m src.supply_service_demo
python -m unittest discover -s tests -v
```

The module uses only the Python standard library. The existing workbook/forecast pipeline has its own requirements. The new module reads `sql/06_synthetic_supply_service.sql`, generates its scenario in memory and writes to `outputs/sample/supply_service/`. It has no input-file option. An alternative output directory can be used to compare deterministic regeneration without modifying repository results.

## Definitions and limits

- Quantity position is opening quantity plus positive receipts plus already-negative issues through the scenario cutoff. Warehouse and SKU units remain distinct; public totals are grouped by physical unit. No stock value, DIO or working-capital savings is estimated.
- Purchasing minimums are current company/SKU/unit references. They are aggregated at that scope rather than repeated per warehouse. The current reference date is later than the stock cutoff and is explicitly a review comparison, not a historical policy backtest or automatic order instruction.
- Service measures include positive fulfilled export rows with usable order, recorded-promise and actual dates. The event must fall inside the review window, with actual and promise no earlier than order. Missing/invalid dates and excluded rows are visible.
- Lateness is actual date after the recorded promise. The denominator is eligible fulfilled export rows, not all requested demand or all orders. Revised promises, cancellations and zero-delivery orders are not supplied; the measure is not OTIF or fill rate.
- Distinct source lines can share an order/receipt/item/warehouse key. They are preserved rather than deduplicated on an unproven key. Return-quantity identities are reviewed separately; an inconsistent net field is not silently repaired or used to count lost sales.
- The interval resamples order clusters within flow/month, preserving rows of the same order together. It is a percentile bootstrap for the observed row-weighted late share. It does not eliminate selection bias, account for every dependence pattern or establish calibrated future risk.

The generated [report and chart](../outputs/sample/supply_service/README.md), CSV tables, aggregate JSON and hash manifest are linked together. The manifest records the seed, code hashes, output hashes and checks. Independent hand-calculated tests cover cutoff, signs, company/SKU policy scope, date exclusions, grain collisions, return exceptions and cluster resampling.
