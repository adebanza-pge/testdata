let
    // ========= Alias your PQ_ parameters (numeric) =========
    r_miles   = Number.From(PQ_RadiusMiles),
    hw_days   = Number.From(PQ_HighWindowDays),
    mph       = Number.From(PQ_AvgSpeedMph),
    overheadH = Number.From(PQ_OverheadHoursPerTrip),
    earlyPenH = Number.From(PQ_EarlyPenaltyPerDay),
    crewRate  = Number.From(PQ_CrewHourlyRate),
    shareFrac = Number.From(PQ_OutageShareFactor),

    // ========= Calendar helpers =========
    UtcNow   = DateTimeZone.UtcNow(),
    Today    = Date.From(UtcNow),

    // ========= Base source (limit to fields we actually need) =========
    // Adjust column names here if your WorkOrders schema differs.
    WO_Base_KeepCols =
        Table.SelectColumns(
            WorkOrders,
            {
                "WorkOrderID","Region","Latitude","Longitude","DueDate","Priority",
                "OutageRequired","CanShareWindow","OutageType","OutageZoneID",
                "ExpectedOutageMinutes","CustomersAffectedEst","Description"
            }
        ),

    // Optional: filter out rows missing core location or due date
    WO_Clean =
        Table.SelectRows(
            WO_Base_KeepCols,
            each [WorkOrderID] <> null and [Latitude] <> null and [Longitude] <> null and [DueDate] <> null
        ),

    // ========= Build Anchor/Candidate prefixed copies =========
    Anchor0 = Table.TransformColumnNames(WO_Clean, each "Anchor" & _),
    Cand0   = Table.TransformColumnNames(WO_Clean, each "Candidate" & _),

    // Add a dummy key for Cartesian join (pairs)
    Anchor1 = Table.AddColumn(Anchor0, "__key__", each 1, Int64.Type),
    Cand1   = Table.AddColumn(Cand0,   "__key__", each 1, Int64.Type),

    // Cartesian join → Anchor × Candidate
    Pairs0 = Table.NestedJoin(Anchor1, {"__key__"}, Cand1, {"__key__"}, "CandTbl", JoinKind.Inner),
    Pairs1 = Table.RemoveColumns(Pairs0, {"__key__"}),

    // Expand all Candidate columns
    Pairs =
        Table.ExpandTableColumn(
            Pairs1, "CandTbl",
            Table.ColumnNames(Cand1),
            Table.ColumnNames(Cand1)
        ),

    // Drop self-pairs and (to reduce size) keep same Region (adjust if you want cross-region)
    PairsFiltered =
        Table.SelectRows(
            Pairs,
            each [AnchorWorkOrderID] <> [CandidateWorkOrderID]
              and [AnchorRegion] <> null and [CandidateRegion] <> null
              and Text.Upper([AnchorRegion]) = Text.Upper([CandidateRegion])
        ),

    // ========= Distance (mi) =========
    WithDist =
        Table.AddColumn(
            PairsFiltered, "DistanceMiles",
            each try fnHaversineMiles([AnchorLatitude], [AnchorLongitude], [CandidateLatitude], [CandidateLongitude]) otherwise null,
            type number
        ),

    // ========= Candidate days until due (relative to Today) =========
    WithDays =
        Table.AddColumn(
            WithDist, "CandidateDaysUntilDue",
            each try Duration.Days(Date.From([CandidateDueDate]) - Today) otherwise null,
            Int64.Type
        ),

    // ========= Window/radius flags =========
    WithinRadius =
        Table.AddColumn(
            WithDays, "WithinRadius",
            each if [DistanceMiles] <> null and [DistanceMiles] <= r_miles then 1 else 0,
            Int64.Type
        ),

    WithinHighWindow =
        Table.AddColumn(
            WithinRadius, "WithinHighWindow",
            each if [CandidateDaysUntilDue] <> null and [CandidateDaysUntilDue] >= 0 and [CandidateDaysUntilDue] <= hw_days then 1 else 0,
            Int64.Type
        ),

    // (Optional prefilter to keep the table light. Comment out if you want all pairs.)
    GuardSmall =
        Table.SelectRows(
            WithinHighWindow,
            each [WithinRadius] = 1 or [WithinHighWindow] = 1
        ),

    // ========= Travel time saved (hrs) & crew labor proxy ($) =========
    // Time saved ≈ overhead for the extra trip avoided + one-way drive time
    AddTimeSaved =
        Table.AddColumn(
            GuardSmall, "TimeSaved_Hours_Est",
            each if [DistanceMiles] = null then null else overheadH + ([DistanceMiles] / mph),
            type number
        ),

    // Penalty (hrs) if candidate is already overdue (encourage urgency)
    AddPenalty =
        Table.AddColumn(
            AddTimeSaved, "Penalty_Hours",
            each if [CandidateDaysUntilDue] <> null and [CandidateDaysUntilDue] < 0
                 then Number.Abs(Number.From([CandidateDaysUntilDue])) * earlyPenH
                 else 0,
            type number
        ),

    // Cost saved proxy ($) if you want a PQ-side placeholder (you can keep using DAX)
    AddCost =
        Table.AddColumn(
            AddPenalty, "CostSaved_USD_Est",
            each if [TimeSaved_Hours_Est] = null then null else [TimeSaved_Hours_Est] * crewRate,
            type number
        ),

    // ========= Outage shareability & avoided minutes/CMI =========
    // Normalize Y/N or True/False
    AddBothNeedOutage =
        Table.AddColumn(
            AddCost, "BothNeedOutage",
            each
                let
                    a = [AnchorOutageRequired],
                    c = [CandidateOutageRequired],
                    Aflag = (a = true) or (a = "Y"),
                    Cflag = (c = true) or (c = "Y")
                in if Aflag and Cflag then 1 else 0,
            Int64.Type
        ),

    AddSameZone =
        Table.AddColumn(
            AddBothNeedOutage, "SameOutageZone",
            each if [AnchorOutageZoneID] <> null and [CandidateOutageZoneID] <> null
                    and Text.Upper([AnchorOutageZoneID]) = Text.Upper([CandidateOutageZoneID])
                 then 1 else 0,
            Int64.Type
        ),

    AddShareable =
        Table.AddColumn(
            AddSameZone, "Shareable",
            each
                let cs = [CandidateCanShareWindow]
                in if [SameOutageZone] = 1 and [BothNeedOutage] = 1 and not (cs = false or cs = "N" or cs = null)
                   then 1 else 0,
            Int64.Type
        ),

    AddOutageMinutesAvoided =
        Table.AddColumn(
            AddShareable, "OutageMinutesAvoided",
            each if [Shareable] = 1 and [CandidateExpectedOutageMinutes] <> null
                 then Number.From([CandidateExpectedOutageMinutes]) * shareFrac
                 else 0,
            Int64.Type
        ),

    AddCustomerMinutesAvoided =
        Table.AddColumn(
            AddOutageMinutesAvoided, "CustomerMinutesAvoided",
            each if [Shareable] = 1 and [OutageMinutesAvoided] <> null and [CandidateCustomersAffectedEst] <> null
                 then Number.From([OutageMinutesAvoided]) * Number.From([CandidateCustomersAffectedEst])
                 else 0,
            Int64.Type
        ),

    // ========= Final column set (tidy & types) =========
    FinalSelect =
        Table.SelectColumns(
            AddCustomerMinutesAvoided,
            {
                // IDs
                "AnchorWorkOrderID","CandidateWorkOrderID",

                // Anchor fields
                "AnchorRegion","AnchorLatitude","AnchorLongitude","AnchorDueDate","AnchorPriority",
                "AnchorOutageZoneID","AnchorOutageRequired","AnchorCanShareWindow","AnchorOutageType","AnchorDescription",

                // Candidate fields
                "CandidateRegion","CandidateLatitude","CandidateLongitude","CandidateDueDate","CandidatePriority",
                "CandidateOutageZoneID","CandidateOutageRequired","CandidateCanShareWindow","CandidateOutageType",
                "CandidateExpectedOutageMinutes","CandidateCustomersAffectedEst","CandidateDescription",

                // Pair metrics
                "DistanceMiles","CandidateDaysUntilDue","WithinRadius","WithinHighWindow",
                "TimeSaved_Hours_Est","Penalty_Hours","CostSaved_USD_Est",

                // Outage metrics
                "SameOutageZone","BothNeedOutage","Shareable",
                "OutageMinutesAvoided","CustomerMinutesAvoided"
            }
        ),

    Typed =
        Table.TransformColumnTypes(
            FinalSelect,
            {
                {"AnchorRegion", type text}, {"CandidateRegion", type text},
                {"AnchorLatitude", type number}, {"AnchorLongitude", type number},
                {"CandidateLatitude", type number}, {"CandidateLongitude", type number},
                {"AnchorDueDate", type date}, {"CandidateDueDate", type date},
                {"AnchorPriority", type text}, {"CandidatePriority", type text},
                {"AnchorOutageZoneID", type text}, {"CandidateOutageZoneID", type text},
                {"AnchorOutageRequired", type any}, {"CandidateOutageRequired", type any},
                {"AnchorCanShareWindow", type any}, {"CandidateCanShareWindow", type any},
                {"AnchorOutageType", type text}, {"CandidateOutageType", type text},
                {"AnchorDescription", type text}, {"CandidateDescription", type text},

                {"DistanceMiles", type number}, {"CandidateDaysUntilDue", Int64.Type},
                {"WithinRadius", Int64.Type}, {"WithinHighWindow", Int64.Type},
                {"TimeSaved_Hours_Est", type number}, {"Penalty_Hours", type number},
                {"CostSaved_USD_Est", type number},

                {"SameOutageZone", Int64.Type}, {"BothNeedOutage", Int64.Type}, {"Shareable", Int64.Type},
                {"OutageMinutesAvoided", Int64.Type}, {"CustomerMinutesAvoided", Int64.Type}
            }
        )
in
    Typed
