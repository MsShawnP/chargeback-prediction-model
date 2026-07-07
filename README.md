# Chargeback Prediction Model

A predictive model proving that retailer chargebacks aren't random — they're the scheduled consequence of specific, fixable data deficiencies — and ranking those root causes by prevention value in dollars.

**Live:** https://chargeback.lailarallc.com

## What it does

Takes a brand's chargeback history, product data, and EDI records and:

1. Harmonizes opaque, retailer-specific chargeback reason codes into uniform root-cause archetypes across retailers
2. Reconstructs data-quality state at shipment time (not today's state) to correctly attribute chargebacks to their upstream causes
3. Trains an interpretable model scoring chargeback probability per shipment, with SHAP attribution so every risk score names the specific data condition driving it
4. Scores upcoming purchase orders to flag high-exposure shipments before they leave the dock
5. Produces a ranked remediation roadmap: root causes ordered by prevention value, with dollar estimates

Built against Cinderhaven, a synthetic ~$25M specialty food brand used across the Lailara portfolio.

## Why it matters

Chargebacks are typically written off as a cost of doing business with national retailers — a line item finance absorbs and operations shrugs at. This model turns that write-off into a controllable expense: it quantifies exactly how much of the chargeback bill is preventable, names the upstream data conditions responsible, and prices each fix. Instead of disputing chargebacks after the money is gone, a brand can rank remediation work by dollar return and intervene before shipment.

## Quick start

```bash
pip install -r requirements.txt

# Configure database access (optional — pipeline runs on parquet fixtures without it)
cp .env.example .env    # set DATABASE_URL

# Run the full pipeline (steps 01-07: extract -> harmonize -> features ->
# model -> score -> roadmap -> export)
python run_pipeline.py

# Tests
python -m pytest
```

The interactive frontend lives in `frontend/`:

```bash
cd frontend
npm install
npm run dev      # Vite dev server
npm run build    # production build
```

Written deliverables (methodology, tearsheet, prevention roadmap) are Quarto documents in `quarto/`.

## Tech stack

- **Pipeline:** Python — pandas, scikit-learn, SHAP, pyarrow, joblib
- **Data source:** Postgres (Cinderhaven Data Platform on Fly.io, via `flyctl proxy`); parquet fixtures for offline runs
- **Reporting:** Quarto with Plotly charts
- **Frontend:** React 19 + TypeScript + Vite, deployed to Cloudflare Workers via Wrangler
- **Testing:** pytest (pipeline), Vitest + Testing Library (frontend)

## Project structure

```
run_pipeline.py       End-to-end pipeline runner (steps 01-07)
config.yml            Engagement metadata
src/pipeline/         Numbered pipeline steps + supporting modules
src/harmonization/    Retailer reason-code -> root-cause archetype mapping
scripts/              Synthetic training data + sample JSON generators
quarto/               Methodology, tearsheet, and roadmap documents
frontend/             React risk-ledger / simulator UI
output/               Model artifacts and exported frames
tests/                pytest suite (fixture-based)
```

## Portfolio context

Part of the Lailara LLC analytics portfolio. Bridges the Product Data Health Audit (finds the data problems) and Retailer Deduction Recovery (disputes chargebacks after arrival) by proving the causal link and quantifying the prevention opportunity.

## License

MIT — see [LICENSE](LICENSE).

---

Built by [Lailara LLC](https://lailarallc.com) — data hygiene and analytics consulting for specialty food brands scaling into national retail.
