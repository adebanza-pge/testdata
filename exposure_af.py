from pyspark.sql import Window 

ef exposure_af(program_exposure):
    af = (
        program_exposure.withColumn("allocation_factor_2020", F.col("Program_Exposure_2020")/F.sum(
            "Program_Exposure_2020").over(Window.partitionBy())*100)
            .withColumn("allocation_factor_2021", F.col("Program_Exposure_2021")/F.sum(
            "Program_Exposure_2021").over(Window.partitionBy())*100)
            .withColumn("allocation_factor_2022", F.col("Program_Exposure_2022")/F.sum(
            "Program_Exposure_2022").over(Window.partitionBy())*100)
            .withColumn("allocation_factor_2023", F.col("Program_Exposure_2023")/F.sum(
            "Program_Exposure_2023").over(Window.partitionBy())*100)
            .withColumn("allocation_factor_2024", F.col("Program_Exposure_2024")/F.sum(
            "Program_Exposure_2024").over(Window.partitionBy())*100)
            .withColumn("allocation_factor_2025", F.col("Program_Exposure_2025")/F.sum(
            "Program_Exposure_2025").over(Window.partitionBy())*100)
            .withColumn("allocation_factor_2026", F.col("Program_Exposure_2026")/F.sum(
            "Program_Exposure_2026").over(Window.partitionBy())*100)
        )
    
    af = af.select(
        *[x for x in af.columns if x not in ["Program_Exposure_2020", "Program_Exposure_2021", "Program_Exposure_2022",
        "Program_Exposure_2023", "Program_Exposure_2024", "Program_Exposure_2025", "Program_Exposure_2026"]]
    )
    return a