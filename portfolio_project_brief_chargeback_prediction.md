# Portfolio Project Brief: Chargeback Prediction Model

**Working title:** *"Your Chargebacks Aren't Random. They're Scheduled."*

**Repo (recommended):** `chargeback-prediction`

**Status:** Brainstorm / Brief stage
**Tier:** Curated backlog #5 (high-value — the predictive bridge between data quality and financial outcomes)
**Priority:** Build after the pieces ahead of it in the queue. This is the most technically ambitious analytical piece in the portfolio — a genuine predictive model, not a descriptive analysis.

---

### 1. The Pain

Chargebacks and deductions are a chronic margin drain — typically 2–8% of gross revenue for a specialty food brand at retail. They arrive cryptically coded, in volume, on the retailer's schedule. The brand's response is almost always reactive: a chargeback shows up, someone disputes it (or doesn't, because there's no time), and the money is either clawed back or absorbed.

What almost no brand does is connect the chargeback to its cause.

Because here's the thing nobody tells the CEO: **chargebacks aren't random.** They're the predictable downstream consequence of upstream conditions — incomplete product data, GTIN errors, ASN timing problems, labeling mismatches, item setup gaps, a SKU's own history of getting charged back at a particular retailer. The same data deficiencies generate the same chargebacks, quarter after quarter, because the root cause is never addressed. The brand keeps paying the penalty and never fixes the thing causing it.

The deeper problem is timing. By the time a chargeback pattern is visible in the deduction data, months of margin have already leaked. There's no early warning. The brand learns it has a chargeback problem with SKU X at Walmart only after SKU X at Walmart has generated six months of chargebacks. The information arrives too late to prevent anything — it only enables disputing what's already lost.

**Who feels it:**
- **$3M–$10M:** The founder absorbs chargebacks because there's no time to dispute and no idea what causes them. Every deduction is a surprise and a mystery.
- **$10M–$15M:** Chargebacks are now $200K–$800K/year. The CFO sees the total on the P&L but can't predict it, can't prevent it, and can't explain quarter-to-quarter swings.
- **$15M–$20M:** Chargebacks are $400K–$1.5M/year. The brand has hired someone whose entire job is disputing deductions — a purely reactive role. Nobody is working the prevention side, because nobody has connected the chargebacks to their upstream causes.

**How it compounds:** Chargebacks feed the doom loop. A short-ship triggers an OTIF chargeback. A product data error triggers a compliance chargeback that suppresses the item, which hurts velocity, which corrupts the forecast. And because nobody fixes the root cause, the same data problems keep generating the same chargebacks — the brand is on a treadmill, disputing the same deduction types forever instead of eliminating them.

#### The Status Quo

The deductions person (if there is one) works a queue of chargebacks reactively, disputing what they can within the window and absorbing the rest. The CFO sees "deductions: $693K" on the P&L as a single line. Nobody asks "which of our data quality problems caused these, and what would it cost to fix them at the source?" — because nobody has ever connected the upstream data to the downstream penalty. So the prevention conversation never happens.

---

### 2. Why This Piece

**It reframes chargebacks from random cost to predictable, preventable outcome.** This is the hook. Most brands treat chargebacks as weather — something that happens to you. The model proves they're scheduled — the inevitable result of specific, fixable upstream conditions. "Your chargebacks aren't random, they're scheduled" reorganizes how a CEO thinks about a line item they'd written off as uncontrollable.

**It's the predictive bridge across the portfolio.** Several existing pieces touch chargebacks from different angles; this one connects them causally:
- **Product Data Health Audit (#6)** finds the data quality problems.
- **EDI Pre-flight (#5)** catches EDI errors before they ship.
- **Retailer Deduction Recovery (#4)** disputes chargebacks after they arrive.
- **Chargeback Prediction** is the missing link: it proves that the data quality problems (Product Data Health) *cause* the chargebacks (Deduction Recovery), quantifies the relationship, and turns "you should fix your data" into "fixing this specific data attribute prevents $X in chargebacks next quarter."

**It turns data quality from a soft cost into a quantified ROI.** Every brand intuits that "bad data causes problems." None can put a number on it. This model puts the number on it: this specific data deficiency drives this specific chargeback type at this rate, so fixing it is worth this much. That transformation — from vague "should fix" to quantified prevention ROI — is the practice's core move applied to its highest-value target.

**It's the portfolio's most sophisticated analytical proof.** Most of the portfolio is diagnostic and descriptive. This is genuinely predictive — a model that scores future chargeback risk from current conditions. It demonstrates a capability tier above the rest of the portfolio without abandoning the business framing.

**All-tier.** Every brand at retail gets charged back. The model scales — a $5M brand finds its handful of root causes; a $20M brand finds a richer pattern. The methodology is identical.

---

### 3. The Analysis — What It Reveals

The heart of the piece. The work is in connecting two datasets the brand has never connected: the chargeback outcomes and the upstream data quality conditions that preceded them. The model's real moat isn't the prediction algorithm — it's two unglamorous pieces of engineering: the reason-code harmonization and the point-in-time join.

**Move 1 — The cross-retailer reason-code harmonization engine (the differentiator).**
Retailer chargeback reason codes are not just cryptic — they're intentionally siloed and inconsistent. Walmart's "Code 22," Target's "Vendor Performance," and KeHE's "Admin Fee" can all describe the same underlying root cause, and a single code at one retailer can map to several causes. The harmonization engine collapses hundreds of opaque, retailer-specific codes into uniform, model-ready root-cause archetypes (data compliance error, logistics/overage, ASN timing infraction, item setup gap, pricing discrepancy).

```
Walmart "Code 22"  ─┐
Target "Vendor Perf" ─┼─► [ semantic mapping ] ─► canonical archetypes
KeHE "Admin Fee"   ─┘                              (data error / logistics / ASN timing / …)
```

This is the model's true differentiation. Get the mapping wrong and every downstream prediction is noise. Get it right and disparate retailer penalties become a single, analyzable signal. (This absorbs brainstorm #50 — reason-code classification — as the foundation the model rests on.)

**Move 2 — Point-in-time feature engineering (the time-machine join).**
This is the single biggest analytical risk, addressed head-on. The product master shows *today's* data, not the data state at the moment a shipment went out six months ago. If a brand fixed a case-dimension error in April, a naive join falsely shows June's chargebacks occurring against "clean" data — which breaks the model's logic entirely. The fix: reconstruct the data-quality state at shipment time. Where historical snapshots exist, use them; where they don't, proxy the historical state from EDI exception logs and product-setup modification histories to infer when each discrepancy was introduced and repaired. Capturing this temporal state is what keeps data-correction history from masking past liabilities.

**Move 3 — Explainable predictive modeling.**
Train an interpretable supervised model targeting chargeback probability per shipment, using the harmonized outcomes as the target and the point-in-time data quality conditions as features (completeness score, historical SKU penalty rate at that retailer, ASN transmission delta, GTIN validity, item setup completeness). Black-box models are barred — a CFO won't authorize a data overhaul on a neural net's latent space. The design biases toward explicit, auditable feature attribution (tree-based with SHAP-style attribution is the likely direction; settled in planning) so every risk score comes with a plain-language operational explanation: *missing net-weight attribute → Walmart logistics audit → 78% probability of a compliance fine within 14 days.*

**Move 4 — Forward risk scoring.**
Score upcoming, un-shipped purchase orders against the model before they leave the dock. Dollarize each: Risk Exposure = Invoice Value × Predicted Chargeback Probability. Isolate the high-exposure fulfillment runs so the team can intervene upstream — fix the data, correct the ASN, hold the shipment — before the penalty is triggered.

**Move 5 — The capital-allocation prevention roadmap.**
Roll per-SKU risk into an executive priority list ranked not by data volume but by *financial recovery value*. "These four root causes drive 60% of your chargebacks. Fixing them prevents an estimated $443K/year. Here's the order, by prevention value." This is the output that turns the model into a board-ready business case for data governance.

#### The Output

- **The Predictive Exposure Ledger:** an executive view of upcoming shipments marked with risk status and dollar exposure, each flag accompanied by the specific data field triggering it ("missing case dimensions → $4,200 exposure at Walmart").
- **The Data Remediation Business Case:** the prevention roadmap — specific data fixes mapped to projected cash retention, ranked by recovery value, ready for a board or senior-staff meeting.

Delivered in whatever form planning settles on — the analytical substance is the harmonization, the point-in-time join, and the attribution, not the presentation layer.

#### The Margin Math

For a $25M brand with $693K/year in chargebacks, the preventable portion broken into root-cause groups, each tied to a specific fix:

| Root Cause Group | Historical Loss | Preventable | Actionable Data Resolution |
|------------------|:---------------:|:-----------:|----------------------------|
| Logistics attribute mismatches | $240K | $168K | Update case dimensions/net weight in GDSN |
| EDI sequence & timing gaps | $180K | $126K | Adjust ASN transmission automation triggers |
| Item setup incompleteness | $140K | $84K | Populate missing state-level pricing/tax indices |
| Other / legitimate | $120K | $32K | Mostly legitimate; sharpen dispute strategy |
| **Total** | **$693K** | **~$443K** | **~1.5–2 points of net margin** |

- **Preventable is permanent.** ~60% of chargebacks trace to a handful of fixable root causes. Fixing the upstream data stops the recurrence — unlike disputing, which recovers some of one quarter's loss and then resets.
- **Recovery vs. prevention economics:** recovery is reactive, partial, and forever; prevention is one-time and eliminates the recurrence. The model shifts the brand off the dispute treadmill.
- **The forecast cleanup:** fewer data-error chargebacks → fewer item suppressions → protected velocity → cleaner forecast. The doom-loop connection again.

**Total estimated value: ~$443K/year** in preventable chargebacks at a $25M brand — most of it permanent rather than the partial, recurring recovery that disputing alone delivers.

#### Before / After

- **Before:** Chargebacks arrive cryptically coded. The deductions person disputes what they can. The CFO sees "$693K" and shrugs — it's the cost of doing business. The same data problems generate the same chargebacks next quarter. The treadmill never stops.

- **After:** The model flags that 60% of chargebacks trace to four data quality root causes. The brand fixes those four things once. Chargebacks drop by an estimated $443K/year — permanently, not via disputing. The risk score flags new chargeback-prone shipments before they ship, so the team intervenes upstream. The treadmill stops.

#### Who Else Sees This?

- **Primary:** CFO (owns the deduction line), COO/ops (owns the data quality that drives it), the deductions person (gets a prioritized, attributed view instead of a blind queue).
- **Secondary:** CEO (sees a written-off cost become controllable), the data/IT lead (gets a quantified ROI for the data cleanup they've been asking budget for).
- **How it gets shared:** The CFO sees "$443K of this $693K is preventable, here are the four causes" and immediately funds the data fix. The attribution turns a cost center into a project with a business case.

---

### 4. Technical Notes

Deliberately deferred — this brief scopes the *what* and *why*; the *how* gets worked out in planning. At a high level: the piece is a supervised prediction problem (harmonized chargeback outcomes as the target, point-in-time data quality conditions as features) running on the Cinderhaven Data Platform, which already holds the deduction, product data, EDI, and shipment marts the model needs. The hard parts are the two pieces of engineering that constitute the moat — the cross-retailer reason-code harmonization (Move 1) and the point-in-time "time-machine" join (Move 2) — plus the attribution layer. Model choice serves interpretability: black-box models are barred because a CFO needs to see *why* a SKU is high-risk, not just that it is; a tree-based model with explicit feature attribution (SHAP-style) is the likely direction. Specifics scoped in planning.

---

### 5. Skills Demonstrated

- **Predictive modeling** — the portfolio's first genuine forward-looking prediction (vs. descriptive/diagnostic analysis). Demonstrates a capability tier above the rest.
- **Feature engineering from data quality** — translating messy upstream data conditions into model features. This is the work that connects "bad data" to "financial outcome."
- **Causal attribution** — not just predicting chargebacks but explaining which condition drives each type. The interpretability is the value.
- **The reframe** — turning a written-off cost into a quantified, controllable, preventable one. The practice's signature move on its highest-value target.

---

### 6. Foot-in-the-Door Offering

- **Offering name:** Chargeback Prevention Diagnostic
- **Format:** Fixed-fee 3–4 week engagement
- **Price range:** $20K–$30K
- **What the client gets:**
  1. Chargeback risk model built on their actual deduction and data quality history
  2. Root-cause attribution — which data quality issues drive which chargeback types, with dollar relationships
  3. Per-SKU/retailer risk scores
  4. Prevention roadmap — the root causes ranked by prevention value
  5. The business case for the data fixes ("fix these four things, prevent $443K/year")
  6. A sharpened dispute strategy for the chargebacks that remain
- **Why this piece sells it:** The reframe — "your chargebacks are predictable and 60% are preventable" — is a claim no other consultant makes, and the model proves it on the brand's own data. The pitch writes itself: *"Deduction recovery consultants charge a percentage to fight your battles after you've already lost the cash. We build a model that stops the battles from happening — by identifying the four data errors causing 60% of your fines."* The CFO funds it to turn a written-off cost into a controllable one.

#### Client Lift

- **What the client provides:** Chargeback/deduction history (with reason codes), product data (or access to the master), EDI history if available, and shipment data. The chargeback history is usually available but messy; the data quality history may need assembling. One kickoff plus access to the deduction and product data exports.

#### The DIY Defense

- **Nobody has connected the two datasets.** Chargebacks live in remittance data; data quality lives in the product master and EDI logs. Joining them — and attributing a chargeback to the upstream condition that caused it — is the work nobody internal has done, because it spans finance, ops, and data.
- **Reason-code classification is specialized.** Retailer chargeback codes are cryptic and inconsistent across retailers. Mapping them to meaningful, modelable categories requires domain knowledge a general analyst lacks.
- **Prediction requires the historical join at scale.** A spreadsheet can show "we got charged back $X." It can't learn that incomplete case dimensions drive a 3.2x compliance-chargeback rate. That requires the modeled relationship across the full history.

---

### 7. Competitor / Existing Content Scan

- **What exists:**
  - **Deduction management services/software** (iNymbus, deductions specialists) — reactive recovery and dispute automation. They process chargebacks; they don't predict or prevent them from data quality.
  - **Data quality tools** — flag data problems but don't connect them to financial outcomes.
  - **Generic "reduce your chargebacks" content** — trade press tips. Anecdotal, not predictive, not quantified.
- **What's missing:** A predictive model that connects data quality conditions to chargeback outcomes and quantifies the prevention opportunity. Nobody bridges the upstream-data-to-downstream-penalty gap for the mid-market specialty food brand.
- **Your angle:** The predictive reframe + the data-quality-to-chargeback attribution + the quantified prevention roadmap. Recovery services dispute the past; this prevents the future.

---

### 8. Cinderhaven Integration

Cinderhaven's deduction history shows $693K/year in chargebacks across its retailers. The model finds:

- **60% of chargebacks trace to four data quality root causes** — incomplete case dimensions, GTIN mismatches at two retailers, an ASN timing pattern, and a labeling compliance gap on one product line.
- **SKUs with incomplete case dimensions carry 3.2x the compliance-chargeback rate** of clean SKUs.
- **The model predicts next quarter's chargebacks** within a defensible accuracy band, flagging the highest-risk SKU/retailer combinations before they ship.
- **Fixing the top four root causes would prevent an estimated $443K/year** — permanently.

Headline: **$443K of Cinderhaven's $693K chargeback bill wasn't random — it was four fixable data problems generating the same penalties every quarter.**

Runs on the existing Cinderhaven Data Platform — joins `fct_deductions`, the product data marts, EDI history, and shipment data. Consistent with the chargeback figures in Retailer Deduction Recovery and the data quality findings in Product Data Health Audit (the model formalizes the causal link those two pieces imply).

---

### 9. Tactical Notes

- **Lead with "predictable, not random."** The entire piece hinges on the reframe. Open with the claim that chargebacks are scheduled, not random, and let the model prove it. That claim is what makes a CFO read past the first paragraph.
- **Interpretability beats accuracy.** A CFO won't act on a black-box risk score. The model must explain *why* a SKU is high-risk ("incomplete case dimensions") so the brand knows what to fix. An interpretable model with clear attribution is more valuable here than a marginally more accurate opaque one. Bias the whole design toward explanation.
- **Separate preventable from legitimate.** Not all chargebacks are preventable — some are legitimate (a real shortage, a genuine late delivery). The model's value is isolating the *preventable* ones (data-driven) from the *legitimate* ones (operational). Don't overclaim that all chargebacks can be eliminated.
- **Prevention vs. recovery is the strategic framing.** Recovery (disputing) is reactive, partial, and permanent labor. Prevention (fixing the data) is one-time and eliminates the recurrence. The piece should make the case for shifting effort from recovery to prevention — without dismissing recovery, which is still needed for the legitimate-but-disputable chargebacks.
- **The data quality history may be the hard input.** Chargeback history is usually retrievable. The *upstream data quality conditions at the time of each shipment* may not be — the product master shows today's data, not what it was six months ago when the chargeback-generating shipment went out. Reconstructing historical data state is a real challenge; flag it for planning. (May require point-in-time data quality snapshots, or proxying from current state.)

#### The Credibility Marker

Knowing that retailer chargeback reason codes are not just cryptic but *inconsistent* — the same root cause (say, a case-pack discrepancy) gets coded differently at Walmart, UNFI, and KeHE, and a single code at one retailer can map to multiple underlying causes. Understanding that the reason-code-to-root-cause mapping is the unglamorous foundation the whole model rests on — get the classification wrong and the prediction is noise — is the practitioner signal. The deeper marker: recognizing that the product master shows *current* data, not the data state at shipment time, so attributing a six-month-old chargeback to a data condition requires reconstructing what the data looked like then.

#### Data Paranoia / Security

Chargeback history and the data quality problems behind it are sensitive — they expose the brand's operational weaknesses. Cinderhaven's data is synthetic. Engagement uses NDA; the model runs on the brand's own data with nothing retained.

---

### 10. Open Questions (for planning)

- [x] ~~**Historical data state reconstruction.**~~ Resolved in approach: where snapshots exist, use them; where they don't, proxy the data-state-at-shipment from EDI exception logs and product-setup modification histories to infer when discrepancies were introduced and repaired. Addressed directly in the narrative as a feature, not hidden. Exact mechanics scoped in planning.
- [x] ~~**Fold in related brainstorm items?**~~ Resolved: absorb #50 (reason-code classification — it's the harmonization engine, the model's differentiator) and #67 (chargeback spikes — the descriptive version this subsumes). #87 (chargeback→PO join) is a component. Keep #74 (dispute window timers) separate — recovery-side.
- [x] ~~**Model interpretability vs. accuracy.**~~ Resolved: interpretability mandated, black-box models barred. Tree-based with explicit feature attribution is the direction; specifics in planning.
- [ ] **Scope: prediction only, or prediction + prevention workflow?** Portfolio piece predicts and quantifies. The ongoing pre-ship risk-scoring workflow and automated data cleanup are positioned as enterprise integration upsells, not the initial deliverable. Confirm.

---

### 11. Build Estimate

- **Effort level:** Medium-Large — the most ambitious analytical piece in the portfolio. The reason-code classification, feature engineering, historical data reconstruction, and attribution layer are each real work.
- **Time estimate:** To be scoped in planning. The historical-data-state question is the swing factor — if the data state can be reconstructed cleanly, it's medium; if it must be carefully proxied, larger.

#### Out of Scope

- **Real-time pre-ship scoring integration.** The portfolio piece predicts on historical data. Wiring a live pre-ship risk score into the brand's order workflow is engagement/integration work.
- **Dispute automation.** The model identifies which chargebacks are disputable; automating the disputes is deduction-recovery territory (#4).
- **Fixing the data.** The model says what to fix and what it's worth; the actual data remediation is a separate engagement (Product Data Health work).

---

### Relationship to Existing Inventory

| Project | Relationship |
|---------|-------------|
| Retailer Deduction Recovery (#4, built) | **Recovery to this piece's prevention.** Recovery disputes chargebacks after they arrive; this predicts and prevents them. The pair = the complete chargeback strategy. |
| Product Data Health Audit (#6, built) | **Cause to this piece's effect.** The data quality problems that audit finds are this model's predictive features. This piece proves they cause the chargebacks. |
| EDI Pre-flight (#5, built) | **Upstream prevention.** EDI errors are predictive features; Pre-flight catches some before they ship. |
| Contract-to-Cash (#9, built) | Chargebacks are a major gross-to-net leakage component C2C traces; this explains and predicts them. |
| Production Demand Forecast (#4 backlog, briefed) | Doom-loop sibling — data-error chargebacks suppress items, which corrupts velocity and the forecast. |
| Brainstorm #50 Deduction reason-code classification NLP (30) | **Absorbed — the harmonization engine (Move 1), the model's differentiator.** |
| Brainstorm #67 Chargeback spikes by retailer/SKU/reason (29) | **Absorbed — the descriptive version this predictive piece subsumes.** |
| Brainstorm #87 Chargeback line items → original POs (28) | **Component** — the join logic connecting chargebacks to shipments. |
| Brainstorm #74 Chargeback dispute window timers (29) | Keep separate — recovery-side, not prediction. |
| Umbrella (#3, built) | Maps to a decision in the ten-decision framework — "how much of our top-line revenue is being clawed back." |

---

*Brief complete; technical scope to be settled in planning.*
