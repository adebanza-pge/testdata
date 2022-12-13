import { Function, OntologyEditFunction, LocalDate, UserFacingError, Filters, Double, Integer, Edits} from "@foundry/functions-api";
import { Objects, ObjectSet, EormKeyRiskIndicator, EormRiskKRI, EormKriActualTarget, EormKriAnnualTarget } from "@foundry/ontology-api";

export class editKRIFunctions {

    @Edits(EormKeyRiskIndicator)
    @OntologyEditFunction()
    public editKRI(kri: EormKeyRiskIndicator,
                   validFrom: LocalDate,
                   validUntil: LocalDate,
                   reportingFrequency: string,
                   reporter: string,
                   status: string,
                   kriDescription: string): void {
        const kriObject = kri;

        kriObject.validFrom = validFrom;

        kriObject.validUntil = validUntil;

        if (reportingFrequency === "Annual" || reportingFrequency === "Quarterly" || reportingFrequency === "Monthly"){
            kriObject.rptFreq = reportingFrequency;
        }
        else {
            throw new UserFacingError("Reporting Frequency must be Annual, Quarterly, or Monthly. Not: " + reportingFrequency);
        }
        
        kriObject.reporter = reporter;

        if (status === "Active" || status === "Inactive" || status === "In Development") {
            kriObject.status = status;
        }
        else {
            throw new UserFacingError("Status must be Active, Inactive, or In Development. Not: " + status);
        }

        kriObject.kriDesc = kriDescription;
    }

    @Edits(EormKeyRiskIndicator)
    @OntologyEditFunction()
    public createNewKRI(riskID: string,
                        newKRIName: string,
                        newReporter: string,
                        newStatus: string,
                        newRptFreq: string,
                        newDesc: string,
                        newValidFrom: LocalDate,
                        newValidUntil: LocalDate): void {

        //check if KRI name exists
        const krisWithThisNameAndRisk = Objects.search()
                                               .eormKeyRiskIndicator()
                                               .filter(kri => Filters.and(kri.riskId.exactMatch(riskID),
                                                                          kri.kriName.exactMatch(newKRIName)))
                                               .all();
        
        if (krisWithThisNameAndRisk.length > 0) {
            throw new UserFacingError("A KRI with this name already exists, please choose another.");
        }

        // check if valid status
        if (newStatus !== "Active" && newStatus !== "Inactive" && newStatus !== "In Development") {
            throw new UserFacingError("Status must be Active, Inactive, or In Development. Not: " + newStatus);
        }

        // check if valid reporting frequency
        if (newRptFreq !== "Annual" && newRptFreq !== "Quarterly" && newRptFreq !== "Monthly") {
            throw new UserFacingError("Reporting Frequency must be Annual, Quarterly, or Monthly. Not: " + newRptFreq);
        }
        
        // compute new kri ID
        const krisMatchingRiskID = Objects.search()
                                          .eormKeyRiskIndicator()
                                          .filter(kri => 
                                                  Filters.and(kri.riskId.exactMatch(riskID)))
                                          .all();
        
        var kriIDNumbers: Array<number> = [];
        
        for (var i = 0; i < krisMatchingRiskID.length; i++) {
            var kriID = krisMatchingRiskID[i].kriId;
            var kriIDComponents = kriID.split("-");
            var kriIDNumber = Number(kriIDComponents[kriIDComponents.length - 1]);
            kriIDNumbers.push(kriIDNumber);
        }
        
        const maxNum = Math.max(...kriIDNumbers.map(function(kriN: number) {return kriN;}));
        const newKRIID = riskID + "-" + String(maxNum + 1);

        const newKRI = Objects.create().eormKeyRiskIndicator(newKRIID);
        newKRI.riskId = riskID;
        newKRI.kriName = newKRIName;
        newKRI.kriDesc = newDesc;
        newKRI.reporter = newReporter;
        newKRI.rptFreq = newRptFreq;
        newKRI.status = newStatus;
        newKRI.validFrom = newValidFrom;
        newKRI.validUntil = newValidUntil;
    }

    @Edits(EormKriActualTarget)
    @OntologyEditFunction()
    public submitNewMeasure(
        kriID: string,
        year: Integer,
        month: Integer,
        monthlyTargetValue: Double,
        monthlyActualValue: Double,
        ytdTargetValue: Double,
        ytdActualValue: Double): void {
            
            // removed code to check for annual target, Jennie asked that this limit be removed.

            // Check to see if EormKriActualTarget exists
            const measurementsForKRIYearMonth = Objects.search()
                                                       .eormKriActualTarget()
                                                       .filter(measurement => Filters.and(measurement.kriId.exactMatch(kriID),
                                                                                          measurement.year.exactMatch(year),
                                                                                          measurement.month.exactMatch(month)))
                                                       .all();
            if (measurementsForKRIYearMonth.length > 0){
                throw new UserFacingError("Measurement already exists; editing not yet enabled ")
            }
            else {
                //create new object
                const newPrimaryKey = "actualMeasurePKey"
                const actualObject = Objects.create().eormKriActualTarget(newPrimaryKey)
                
                if (year >= 2020 || year <= 2100 && month >= 1 || month <= 12) {
                    actualObject.year = year;
                    actualObject.month = month;
                    }
                else {
                    throw new UserFacingError("Year must be between 2020 or 2100 && month must be between 1 - 12");
                }
                
                actualObject.actualsMonthly = monthlyActualValue;
                actualObject.targetMonthly = monthlyTargetValue;
                actualObject.targetYtd = ytdTargetValue;
                actualObject.actualsYtd = ytdActualValue;

                // to implement: compute RAG status
                // get annual target for this KRI and Year, if none exists, set to null
                // compare RAG thresholds with monthly targets 
                // set RAG status
             
            }
            const annualsForKRIYear = Objects.search()
                                                       .eormKriAnnualTarget()
                                                       .filter(annual => Filters.and(annual.kriId.exactMatch(kriID),
                                                                                          annual.year.exactMatch(year)))
                                                       .all();

            // const newPrimary Key to generate the new value
            var kriIDNumbers: Array<number> = [];
            for (var i = 0; i < measurementsForKRIYearMonth.length; i++) {
                var newKriID = measurementsForKRIYearMonth[i].kriId;
                var kriIDComponents = newKriID.split("-");
                var kriIDNumber = Number(kriIDComponents[kriIDComponents.length - 1]);
                kriIDNumbers.push(kriIDNumber);
            }

            const maxNum = Math.max(...kriIDNumbers.map(function(kriN: number) {return kriN;}));
            const newPrimaryKey = year + "-" + String(maxNum + 1);
            
            /*  Follow logic in createNewKri:
                    - get the set of ActualTarget objects that match the KRI ID and Year
                    - get numbers at the end of the existing set of primary keys
                    - take the max to get the max number
                    - add 1 to the max number
                    - concatenate to form new primary key value
            */
            const newActualObject = Objects.create().eormKriActualTarget(newPrimaryKey)
                                    
            if (annualsForKRIYear.length === 1) {
                //const annualTargetObject: EormKriAnnualTarget = annualsForKRIYear[0];

                ////
                var kriIDNumbers: Array<number> = [];
                for (var i = 0; i < annualsForKRIYear.length; i++) {
                    var newKriID = annualsForKRIYear[i].kriId;
                    var kriIDComponents = newKriID.split("-");
                    var kriIDNumber = Number(kriIDComponents[kriIDComponents.length - 1]);
                    kriIDNumbers.push(kriIDNumber);
                }

                const maxNum = Math.max(...kriIDNumbers.map(function(kriN: number) {return kriN;}));
                const newPrimaryKey = year + "-" + String(maxNum + 1);
                
                /*  Follow logic in createNewKri:
                        - get the set of ActualTarget objects that match the KRI ID and Year
                        - get numbers at the end of the existing set of primary keys
                        - take the max to get the max number
                        - add 1 to the max number
                        - concatenate to form new primary key value
                */
                //create new object
                const annualTargetObject = Objects.create().annualsForKRIYear(newPrimaryKey)
                ////

                if (annualTargetObject.thresholdType === "percentage of target") {
                    var greenMinValue: number = annualTargetObject.greenMin * monthlyTargetValue;
                    var greenMaxValue: number = annualTargetObject.greenMax * monthlyTargetValue;
                    var amberMinValue: number = annualTargetObject.amberMin * monthlyTargetValue;
                    var amberMaxValue: number = annualTargetObject.amberMax * monthlyTargetValue;
                    var redMinValue: number = annualTargetObject.redMin * monthlyTargetValue;
                    var redMaxValue: number = annualTargetObject.redMax * monthlyTargetValue;
                }
                else if (annualTargetObject.thresholdType === "unit") {
                    var greenMinValue: number = annualTargetObject.greenMin;
                    var greenMaxValue: number = annualTargetObject.greenMax;
                    var amberMinValue: number = annualTargetObject.amberMin;
                    var amberMaxValue: number = annualTargetObject.amberMax;
                    var redMinValue: number = annualTargetObject.redMin;
                    var redMaxValue: number = annualTargetObject.redMax;
                }
                else {
                    throw new UserFacingError("Annual Target does not have a valid RAG status threshold type.");
                }

                if ((greenMinValue <= monthlyActualValue) && (monthlyActualValue <= greenMaxValue)) {
                    newActualObject.statusLabel = "green";
                }
                else if ((amberMinValue <= monthlyActualValue) && (monthlyActualValue <= amberMaxValue)) {
                    newActualObject.statusLabel = "amber";
                }
                else if ((redMinValue <= monthlyActualValue) && (monthlyActualValue <= redMaxValue)) {
                    newActualObject.statusLabel = "red";
                }
                else {
                    throw new UserFacingError("Monthly data does not match criteria specified in Annual target, verify annual target data for this year.");
                }
            }
            else if (annualsForKRIYear.length === 0) {
                newActualObject.statusLabel = "N/A"
            }
            else {
                throw new UserFacingError("Metric has more than 1 annual target for this year, cannot create new monthly data.");
            }                
        }
            
    @Edits(EormKriAnnualTarget)
    @OntologyEditFunction()
    public submitNewTarget(
        kriID: EormKriAnnualTarget,
        year: Integer,
        annualTarget: Double,
        thresholdType: string,
        greenMin: Double,
        greenMax: Double,
        amberMin: Double,
        amberMax: Double,
        redMin: Double,
        redMax: Double): void {

            const annualsForKRIYear = Objects.search()
                                                       .eormKriAnnualTarget()
                                                       .filter(annual => Filters.and(annual.kriId.exactMatch(kriID),
                                                                                          annual.year.exactMatch(year)))
                                                       .all();
            if (annualsForKRIYear.length > 0){
                throw new UserFacingError("Annual target already exists")
            }
            else {
                // const newPrimary Key to generate the new value
                var kriIDNumbers: Array<number> = [];
                for (var i = 0; i < annualsForKRIYear.length; i++) {
                    var newKriID = annualsForKRIYear[i].kriId;
                    var kriIDComponents = newKriID.split("-");
                    var kriIDNumber = Number(kriIDComponents[kriIDComponents.length - 1]);
                    kriIDNumbers.push(kriIDNumber);
                }

                const maxNum = Math.max(...kriIDNumbers.map(function(kriN: number) {return kriN;}));
                const newPrimaryKey = year + "-" + String(maxNum + 1);
                
                /*  Follow logic in createNewKri:
                        - get the set of ActualTarget objects that match the KRI ID and Year
                        - get numbers at the end of the existing set of primary keys
                        - take the max to get the max number
                        - add 1 to the max number
                        - concatenate to form new primary key value
                */
                //create new object
                const newAnnualObject = Objects.create().eormKriAnnualTarget(newPrimaryKey)
                
                if (year >= 2020 || year <= 2100) {
                    newAnnualObject.year = year;
                    }
                else {
                    throw new UserFacingError("Year must be between 2020 or 2100");
                }
            newAnnualObject.eoyTarget = annualTarget;
            newAnnualObject.thresholdType = thresholdType;
            newAnnualObject.greenMin = greenMin;
            newAnnualObject.greenMax = greenMax;
            newAnnualObject.amberMin = amberMin;
            newAnnualObject.amberMax = amberMax;
            newAnnualObject.redMin = redMin;
            newAnnualObject.redMax = redMax;
            }
        }
    }