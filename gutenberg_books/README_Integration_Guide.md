
# Grid Maintenance Prioritization Assistant – Integration Guide

**Last updated:** 20250807_0310

This bundle includes:
- **Data**: work orders, assets (electric + gas with corrosion fields), crews, regions
- **Analytics**: Power BI theme, DAX guidance, Gas Integrity page instructions
- **Automation**: Power Automate flow diagram + reference template
- **ML**: mock labels, training dataset, predictions, and metrics
- **Schemas**: SharePoint List schemas to enable live flows
- **Pitch**: PowerPoint deck for demo

---

## 1) Power BI Setup (Desktop)

1. Open **Power BI Desktop** → **Get Data → Text/CSV** → import all CSVs:
   - `asset_registry.csv`, `work_orders.csv`, `crew_roster.csv`, `crew_schedule.csv`, `regions.csv`
   - Optional: `predictions_gas_corrosion.csv`
2. **Model relationships** (Manage relationships):
   - `work_orders[AssetID]` → `asset_registry[AssetID]` (Many-to-One)
   - `work_orders[Region]` → `regions[Region]` (Many-to-One)
   - `crew_schedule[CrewID]` → `crew_roster[CrewID]` (Many-to-One)
   - `predictions_gas_corrosion[AssetID]` → `asset_registry[AssetID]` (Many-to-One)
3. **Create Measures (DAX)**:
   - `Open WOs = COUNTROWS(FILTER(work_orders, work_orders[Status] <> "Closed"))`
   - `Overdue WOs = COUNTROWS(FILTER(work_orders, work_orders[DaysOverdue] > 0 && work_orders[Status] <> "Closed"))`
   - `High Risk Overdue = COUNTROWS(FILTER(work_orders, work_orders[DaysOverdue] > 5 && work_orders[RiskScore] >= 8 && work_orders[Status] <> "Closed"))`
   - `Avg Days Overdue = AVERAGE(work_orders[DaysOverdue])`
   - Gas page (rubric): see **README_PowerBI_Instructions.md** for `Gas Measures` and visuals.
4. **Import theme**: View → Themes → Browse → `powerbi_theme.json`.
5. **Pages**:
   - **Page 1 – Command Center**: KPIs, map, overdue by region, table
   - **Page 2 – Crew Capacity**: Roster & schedule utilization
   - **Page 3 – Assets & Risk**: Age vs. condition, risk distribution
   - **Page 4 – Gas Integrity**: (from README) ILI & CP monitoring + predictions
6. (Optional) **Copilot in Power BI**: enable Copilot in the Service, and ask:
   - “Show me the top CP Zones by underprotection and overdue work.”
   - “Which regions have the most critical gas WOs this week?”

Publish to Power BI Service if you want to demo sharing and scheduled refresh.

---

## 2) Power Automate Setup (Flows)

### A) High-Risk Overdue Alert (from `power_automate_flow_template.json`)
1. Create a **SharePoint List** named **WorkOrders** using `SPO_Schema_WorkOrders.csv` as a reference for columns.
2. Import your work orders by uploading `work_orders.csv` (or use Power Automate to sync from CSV).
3. In **Power Automate**:
   - Trigger: **SharePoint – When an item is created or modified** (WorkOrders)
   - Condition: `DaysOverdue > 5 AND RiskScore >= 8 AND Status != 'Closed'`
   - If **Yes**: Post Teams message to regional channel → Send email to manager → Update item with `EscalationFlag=true` and `EscalatedAt=utcNow()`
4. Use `flow_diagram.png` as a visual guide.

### B) Weekly CP Underprotection Digest (optional enhancement)
- Trigger: **Recurrence** (weekly, Mon 7 AM)
- Get items: **Assets** list where `CPStatus = Underprotected`
- Group by `Region` and `CPZoneID`
- Action: **Send email (HTML table)** to `regions.Email` with counts and top affected assets

> Use `SPO_Schema_Assets.csv` to create the Assets list and import relevant columns (`CPStatus`, `CPZoneID`, `HCA_Flag`, etc.).

---

## 3) SharePoint Lists (for live demo)

Use these schema files as blueprints to create your lists:
- `SPO_Schema_WorkOrders.csv`
- `SPO_Schema_Assets.csv`
- `SPO_Schema_Regions.csv`
- `SPO_Schema_CrewRoster.csv`
- `SPO_Schema_CrewSchedule.csv`

> Once lists exist, you can point Power BI **Directly** to SharePoint Lists as a source (Get Data → SharePoint Online List), or keep CSV-based for the hackathon.

---

## 4) ML: Predictions & Side-by-Side (Power BI)

1. Join `predictions_gas_corrosion.csv` to `asset_registry` on `AssetID`.
2. Visuals:
   - **KPI**: `AVERAGE(predictions[PredictedRisk_Prob])`
   - **Donut**: count by `PredictedRisk_Bucket`
   - **Scatter**: `CorrosionRiskScore_Rubric` vs `PredictedRisk_Prob`
   - **Map**: color by `PredictedRisk_Bucket`
3. Narrative:
   - Rubric = transparent, adjustable thresholds (see `corrosion_risk_weights.*`)
   - Model = adaptive signal that may re-rank high-risk assets

---

## 5) Copilot Touchpoints

- **Power BI Copilot**: Use NLQ to generate insights, explain KPIs, and write executive summaries.
- **Power Automate Copilot**: Draft flow steps (paste the condition and actions from the guide).
- **Teams Copilot**: Ask “What are the top 5 overdue high-risk WOs in North Bay this week?” and link to the report.

---

## 6) File Index

Data:
- `asset_registry.csv`, `work_orders.csv`, `crew_roster.csv`, `crew_schedule.csv`, `regions.csv`

Schemas (SharePoint):
- `SPO_Schema_*.csv`

BI & Pitch:
- `powerbi_theme.json`, `README_PowerBI_Instructions.md`, `README_Integration_Guide.md`, `pitch_deck.pptx`

Automation:
- `power_automate_flow_template.json`, `flow_diagram.png`

ML:
- `corrosion_risk_weights.csv`, `corrosion_risk_weights.json`
- `labels_gas_corrosion.csv`, `training_dataset_gas.csv`, `predictions_gas_corrosion.csv`, `model_metrics.json`

---

## 7) Demo Script (5 minutes)

1. **Problem (30s):** Backlog, safety, regulatory risk.
2. **Dashboard (2m):** Command Center → drill into a region; show Gas Integrity page.
3. **Automation (1m):** Flow diagram; trigger condition; Teams/email alert.
4. **AI (1m):** Rubric vs. Model view; explain how weights can be tuned; bucketed predictions.
5. **Value (30s):** Faster repairs, lower risk, better planning.

---

Questions? Ping Copilot: *"Summarize this week’s high-risk gas maintenance hotspots."*
