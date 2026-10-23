# Synthetic data provenance

Every public workbook and data export is generated from fictional inputs. The generator uses NumPy's seeded random number generator with seed `42`, fixed vocabularies and declared distributions. It does not open `data/raw`, load private analytical outputs, learn coefficients from company records, resample company rows, or replace real identifiers with aliases.

The fictional company labels and `MPC`/`MPT` codes demonstrate entity-aware keys. Customer/supplier/product identifiers, dates, prices, quantities and balances are fabricated by the generator. Generic geography and product-category words are schema examples, not evidence of a real relationship or actual company performance.

```sh
python -m src.generate_sample_data
python -m src.export_outputs --sample
```

Run from the repository root after installing `requirements.txt`. The public pipeline reads only `data/sample/` and writes only `outputs/sample/`; the dashboard/sample chart workflow consumes those generated outputs. Company source records and derived findings belong only in ignored private paths. The local real-data reproduction guide and reports are excluded from publication.

Default generator settings: `{"companies": 2, "product_lines": 5, "products_per_line_per_company": 4}`. The publication audit regenerated all source sheets and compared their cell values to the delivered samples. It also rebuilt public pipeline outputs in an isolated sample-only fixture. Library/font versions can cause small fitted-forecast or rendered-chart differences; fixture forecasts remain synthetic. The Group JSON generation timestamp is expected to change.

`data/sample/SYNTHETIC_PROVENANCE.json` records the generator and delivered sample hashes. These hashes verify the reviewed snapshot; rerun the publication review after changing generated examples. Public data is for demonstration and has no factual interpretation as employer/customer activity.
