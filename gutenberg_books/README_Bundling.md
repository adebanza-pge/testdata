# Bundling Logic – Design & Implementation
_Last updated: 2025-08-14 21:35_

## 0) Purpose (Why Bundling?)
When a crew is already dispatched to an **anchor** work order (WO) in a given area, we surface **candidate** WOs close by and due soon. If added to the same trip, the crew avoids an extra mobilization (drive + setup), saving **time** and **cost** without delaying high‑priority work.

---

## 1) Clear Definitions
**Anchor WO**  
A WO actively planned or soon to be executed (default: **Due in the next 21 days**), **not Critical**, with an active status (`Open`, `Assigned`, `In Progress`, `Deferred`).

**Candidate WO**  
A WO in the **same area** and **within a look‑ahead window** (default: **≤ 180 days** after the anchor’s due date), also with an active status. Guardrails avoid unsafe pull‑ins (see §4).

**Area / Proximity**  
Default radius = **5 miles** straight‑line (Haversine). You can replace with **routing time** via Bing/Azure Maps in dense cities.

---

## 2) Tunable Parameters (What‑If friendly)
| Parameter | Meaning | Default |
|---|---|---|
| `AnchorDays` | Anchor due‑soon window (days) | **21** |
| `LookaheadDays` | Candidate due‑by window relative to anchor | **180** |
| `RadiusMiles` | Search radius around anchor (miles) | **5** |
| `AvgSpeedMph` | In‑area travel speed (mph) | **25** |
| `OverheadHoursPerTrip` | Avoided fixed time per extra trip (hr) | **0.6** |
| `CrewHourlyRate` | Loaded labor rate ($/hr) | **150** |
| `HighWindowDays` | Only allow **High** priority if due in ≤ this (days) | **30** |
| `EarlyPenaltyPerDay` | Soft penalty for very early pull‑ins (hr/day) | **0.005** |

These map directly to **Power BI What‑If parameters** (§7).

---

## 3) Required Fields (WorkOrders)
- `WorkOrderID` (text) — unique WO key  
- `DueDate` (date)  
- `Latitude`, `Longitude` (number)  
- `Region` (text). If absent, derive a **GeoCell**: `ROUND(Lat, 0.02) & ',' & ROUND(Lon, 0.02)`  
- `Status` (Open/Assigned/In Progress/Deferred/Closed)  
- `Priority` (Low/Medium/High/Critical)

Optional: `Commodity`, `AssetType`, `AssignedCrewID`, `HCA_Flag`

---

## 4) Exact Formulas & Guardrails
**Distance (miles)** — Haversine:
```
d = 2R * asin( sqrt( sin²((lat2-lat1)/2) + cos(lat1)cos(lat2)sin²((lon2-lon1)/2) ) )
```
with `R = 3958.8 mi` and angles in **radians**.

**Travel time (hr)**  
`TravelTime = DistanceMiles / AvgSpeedMph`

**Time saved (hr)** from bundling a candidate with an anchor:  
`TimeSaved_Hours = OverheadHoursPerTrip + TravelTime`

**Cost saved ($)**  
`CostSaved_USD = TimeSaved_Hours * CrewHourlyRate`

**Early pull penalty (hr)**  
`EarlyDays = MAX(0, CandidateDaysUntilDue - HighWindowDays)`  
`Penalty = EarlyPenaltyPerDay * EarlyDays`

**BundleScore (rank)**  
`BundleScore = MAX(0, TimeSaved_Hours - Penalty)`

**Guardrails**  
- Never bundle **Critical** candidates.  
- Allow **High** only if `CandidateDaysUntilDue ≤ HighWindowDays` (default 30).  
- Optional gates: require same **Commodity**/**Specialty**; exclude assets requiring permits or outages.

---

## 5) Worked Example
- Anchor: **WO A** (Due in 10 days, lat/lon 37.78/−122.42)  
- Candidate: **WO B** (Due in 70 days, **Priority=Medium**, lat/lon 37.80/−122.45)  
- Distance ≈ **3.2 mi** → Travel time ≈ `3.2/25 = 0.128 hr`  
- **TimeSaved** = `0.6 + 0.128 = 0.728 hr`  
- **Penalty**: `EarlyDays = MAX(0, 70−30) = 40` → `0.005 * 40 = 0.20 hr`  
- **BundleScore** = `MAX(0, 0.728 − 0.20) = 0.528`  
- **CostSaved** = `0.728 * $150 = $109.20` → Good candidate.

---

## 6) Power Query (M): Distance + Pair Building (Step‑by‑Step)

### 6.1 Create Haversine Function
**Power Query → New Source → Blank Query → Advanced Editor**, paste and name `fnHaversineMiles`:
```m
(fnLat1 as number, fnLon1 as number, fnLat2 as number, fnLon2 as number) as number =>
let
  R = 3958.8,
  toRad = (x as number) => x * Number.PI / 180,
  dLat = toRad(fnLat2 - fnLat1),
  dLon = toRad(fnLon2 - fnLon1),
  a = Number.Sin(dLat/2)*Number.Sin(dLat/2) +
      Number.Cos(toRad(fnLat1))*Number.Cos(toRad(fnLat2))*
      Number.Sin(dLon/2)*Number.Sin(dLon/2),
  c = 2 * Number.Atan2(Number.Sqrt(a), Number.Sqrt(1 - a)),
  d = R * c
in
  d
```

### 6.2 Create Anchor & Candidate Queries
- **Duplicate** `WorkOrders` as `WorkOrders_Anchor` → filter:  
  `Status ∈ {{Open, Assigned, In Progress, Deferred}}` and `DueDate` in next `AnchorDays` (e.g., 21).
- Duplicate as `WorkOrders_Candidate` → filter: `Status` active.

> (Optional) If `Region` is missing, add a **GeoCell** column in both.

### 6.3 Merge by Area then Compute Distance
- **Merge** `WorkOrders_Anchor` with `WorkOrders_Candidate` on `Region` (or `GeoCell`), **Left Outer**.  
- **Expand** candidate columns.
- **Add Column → Custom** → `DistanceMiles`:
```m
= fnHaversineMiles([Latitude], [Longitude], [WorkOrders_Candidate.Latitude], [WorkOrders_Candidate.Longitude])
```
- Filter: `DistanceMiles ≤ RadiusMiles`.

### 6.4 Guardrails & Windows
- Filter out **Critical** candidates.  
- Keep **High** only where `CandidateDueDate ≤ Date.AddDays(Date.From(DateTime.LocalNow()), HighWindowDays)`.
- Keep candidates where `CandidateDueDate ≤ Date.AddDays([DueDate], LookaheadDays)`.

### 6.5 Compute Savings & Score
Add custom columns:
```m
TimeSaved_Hours_Est = OverheadHoursPerTrip + ( [DistanceMiles] / AvgSpeedMph )
CostSaved_USD_Est   = [TimeSaved_Hours_Est] * CrewHourlyRate
EarlyDays           = Number.Max(0, Duration.Days([CandidateDueDate] - DateTime.Date(DateTime.LocalNow())) - HighWindowDays)
Penalty_Hours       = EarlyPenaltyPerDay * EarlyDays
BundleScore         = Number.Max(0, [TimeSaved_Hours_Est] - [Penalty_Hours])
```
Rename the final query **`BundleSuggestions`** and **Load**.

> You can optionally create a derived **`BundleSummary`** table via Group By: `AddedWorkOrders`, total time/cost.

---

## 7) Power BI Implementation (Interactive)

### 7.1 What‑If Parameters
Create these in **Modeling → New Parameter** (Fields):
- `RadiusMiles` (1–20, step 0.5, default 5)  
- `LookaheadDays` (30–365, step 15, default 180)  
- `AnchorDays` (7–28, step 1, default 21)  
- `HighWindowDays` (7–60, step 1, default 30)  
- `OverheadHoursPerTrip` (0–1, step 0.1, default 0.6)  
- `AvgSpeedMph` (5–45, step 5, default 25)  
- `CrewHourlyRate` (50–300, step 25, default 150)  
- `EarlyPenaltyPerDay` (0–0.02, step 0.001, default 0.005)

### 7.2 Measures (DAX)
```DAX
Candidate Days Until Due =
VAR cd = SELECTEDVALUE(BundleSuggestions[CandidateDueDate])
RETURN IF(NOT ISBLANK(cd), DATEDIFF(TODAY(), cd, DAY))

TimeSaved (hrs) =
[OverheadHoursPerTrip Value] +
DIVIDE( SELECTEDVALUE(BundleSuggestions[DistanceMiles]), [AvgSpeedMph Value] )

Penalty (hrs) =
VAR EarlyDays = MAX( 0, [Candidate Days Until Due] - [HighWindowDays Value] )
RETURN [EarlyPenaltyPerDay Value] * EarlyDays

BundleScore =
MAX( 0, [TimeSaved (hrs)] - [Penalty (hrs)] )

CostSaved ($) =
[TimeSaved (hrs)] * [CrewHourlyRate Value]

Accepted Total Time Saved (hrs) =
CALCULATE( SUMX( BundleSuggestions, [TimeSaved (hrs)] ),
           BundleSuggestions[Decision] = "Accepted" )

Accepted Total Cost Saved ($) =
CALCULATE( SUMX( BundleSuggestions, [CostSaved ($)] ),
           BundleSuggestions[Decision] = "Accepted" )
```

### 7.3 Visuals
- **Table**: `AnchorWorkOrderID`, `CandidateWorkOrderID`, `DistanceMiles`, `[TimeSaved (hrs)]`, `[Penalty (hrs)]`, `[BundleScore]`, `[CostSaved ($)]`  
- **Map**: anchor + candidates, colored by `Priority` (tooltip: `DistanceMiles`, `[CostSaved ($)]`)  
- **KPIs**: `Accepted Total Time Saved (hrs)`, `Accepted Total Cost Saved ($)`  
- **Slicers**: parameters, Region, Priority, Commodity

---

## 8) Two Power Automate Patterns

### Pattern A — Propose on Assignment (Teams Adaptive Card)
- **Trigger:** SharePoint “WorkOrders” → When item created/modified  
- **Condition:** `Status == "Assigned"` AND `Priority != "Critical"`  
- **Steps:**
  1) Compute **bounding box** around anchor using `RadiusMiles`  
     `dLat = RadiusMiles / 69`  
     `dLon = RadiusMiles / (69 * cos(anchorLat * π / 180))`
  2) **Get items** (OData filter): active status, same Region, `DueDate ≤ addDays(anchor.DueDate, LookaheadDays)`, and lat/lon within the bounding box.
  3) **Filter array**: (a) exclude Critical, (b) if High → `DueDate ≤ addDays(utcNow(), HighWindowDays)`.
  4) **Select** fields; compute Time/Cost/Score with Compose steps; **take top N**.
  5) **Post Adaptive Card**; on **Approve**, write a **BundleSuggestions** row: `AnchorWorkOrderID`, `CandidateList` (JSON string), `Decision="Accepted"`.
  6) (Optional) Trigger the **apply updates** flow to populate `BundleGroupID` in **WorkOrders**.

### Pattern B — Read from PBIX Suggestions
- Keep **BundleSuggestions** computed in the dataset and refreshed on a schedule.
- Flow reads the table (via SharePoint list mirror or Export to CSV), posts the Teams card, and writes back decisions.

---

## 9) Output Schemas & Demo Visuals

**BundleSuggestions** (table/List):  
`AnchorWorkOrderID`, `AnchorDueDate`, `AnchorPriority`, `AnchorRegionOrCell`,  
`CandidateWorkOrderID` **or** `CandidateList` (JSON in approvals flow),  
`DistanceMiles`, `TimeSaved_Hours_Est`, `CostSaved_USD_Est`, `BundleScore`,  
`Decision` (Proposed/Accepted/Rejected), `ProposedDate`, `Approver` (Person)

**BundleSummary** (derived):  
`AnchorWorkOrderID`, `AddedWorkOrders`, `TotalTimeSaved_Hours`, `TotalCostSaved_USD`

**Demo visuals**: “Bundling” report page → Table (sorted by `BundleScore`), Map, KPIs; add What‑If slicers.

---

## 10) Validation & Governance
**Safety/Compliance**: Critical work is never delayed; add permit/outage flags to exclude ineligible jobs.  
**Capacity**: Join to `crew_schedule` and cap accepted bundle hours ≤ available capacity.  
**Metrics**:  
- Adoption: % of anchors with at least one accepted bundle  
- Efficiency: median `TimeSaved_Hours_Est` per accepted bundle  
- Financials: weekly `TotalCostSaved_USD_Est`  
- Quality: revisit and rework rates of bundled jobs

---

## 11) FAQ
- **Why straight‑line distance?** It’s fast and robust in Power BI/Flow. Replace with routing API if needed.  
- **Why a penalty?** To avoid pulling in work *too* early when there’s little marginal value.  
- **Can we force same specialty/commodity?** Yes—add a filter or a gate in Power Query/Flow.

---

## 12) Quick Start (TL;DR)
1) Load `work_orders.csv` and create `BundleSuggestions` in Power Query as above.  
2) Add What‑If parameters + DAX measures.  
3) Build the **Bundling** page (table + map + KPIs + slicers).  
4) Import the Teams **Adaptive Card** approval flow and the **apply updates** flow.  
5) Present KPIs and one approved example.
