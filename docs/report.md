# Evaluation Report

**Run date:** 2026-10-04T04:32:57.574480
**Evaluation date (frozen):** 2026-10-01

## Metrics

| Metric | Value |
|--------|-------|
| Auto-approval precision | 89.5% |
| Escalation recall | 100.0% |
| Hard-case escalation recall | 100.0% |
| Mean retries per case | 0.60 |
| Mean cost per case | €0.0141 |
| Total cost | €0.3531 |

## Issues

### Outcome mismatches (2)

- **scenario_09**: expected auto_approved, got approved_by_human
  (Laura Hoffmann - software_engineer junior)
- **scenario_12**: expected auto_approved, got approved_by_human
  (Carlos Santos - software_engineer medior)

## Known Gaps

### Scenario 21: Contractor with aws_dev

This is a **known limitation**: the system validates against coded rules in validators,
but some policy is prose-only in the handbook (§4.3: contractors never get aws_dev).
- Expected: auto_approved (prose-only rule)
- Actual: auto_approved
- Cost: €0.0098

This gap is flagged in the README as a design limitation.

## Details

| Scenario | Status | Expected | Retries | Cost EUR | Notes |
|----------|--------|----------|---------|----------|-------|
| scenario_01 | auto_approved | auto_approved | 0 | €0.0101 | Eva de Boer - data_analyst junior |
| scenario_02 | auto_approved | auto_approved | 1 | €0.0176 | Marcus Johnson - software_engineer medior |
| scenario_03 | auto_approved | auto_approved | 0 | €0.0100 | Elena Rodriguez - product_manager senior |
| scenario_04 | auto_approved | auto_approved | 0 | €0.0094 | James Chen - finance_officer medior |
| scenario_05 | auto_approved | auto_approved | 0 | €0.0092 | Sophia Laurent - hr_coordinator junior |
| scenario_06 | auto_approved | auto_approved | 0 | €0.0096 | Diego Morales - sales_rep junior |
| scenario_07 | auto_approved | auto_approved | 0 | €0.0099 | Victoria Schmidt - engineering_manager lead |
| scenario_08 | auto_approved | auto_approved | 0 | €0.0100 | Oliver Kim - data_analyst medior |
| scenario_09 | approved_by_human | auto_approved | 3 | €0.0291 | Laura Hoffmann - software_engineer junior |
| scenario_10 | auto_approved | auto_approved | 1 | €0.0169 | Thomas Weber - data_analyst junior |
| scenario_11 | auto_approved | auto_approved | 1 | €0.0189 | Natasha Petrov - product_manager medior |
| scenario_12 | approved_by_human | auto_approved | 3 | €0.0310 | Carlos Santos - software_engineer medior |
| scenario_13 | auto_approved | auto_approved | 1 | €0.0155 | Isabelle Fontaine - finance_officer junior |
| scenario_14 | auto_approved | auto_approved | 1 | €0.0160 | Roland Fischer - sales_rep medior |
| scenario_15 | auto_approved | auto_approved | 1 | €0.0166 | Yuki Tanaka - hr_coordinator medior |
| scenario_16 | approved_by_human | escalated | 0 | €0.0104 | Amir Hassan - software_engineer medior |
| scenario_17 | approved_by_human | escalated | 0 | €0.0099 | Zara Malik - data_analyst junior |
| scenario_18 | approved_by_human | escalated | 0 | €0.0105 | Benjamin Hoffmann - software_engineer senior |
| scenario_19 | auto_approved | auto_approved | 1 | €0.0172 | Rajesh Kumar - software_engineer medior |
| scenario_20 | approved_by_human | escalated | 0 | €0.0104 | Claudia Meyer - data_analyst junior |
| scenario_21 | auto_approved | auto_approved | 0 | €0.0098 | Patrick O'Brien - software_engineer junior |
| scenario_22 | auto_approved | auto_approved | 1 | €0.0175 | Amanda White - software_engineer junior |
| scenario_23 | approved_by_human | escalated | 0 | €0.0098 | Anna Duplicate - software_engineer junior |
| scenario_24 | auto_approved | auto_approved | 1 | €0.0175 | Gregory Wells - product_manager junior |
| scenario_25 | approved_by_human | escalated | 0 | €0.0103 | Stress Test - software_engineer junior |
