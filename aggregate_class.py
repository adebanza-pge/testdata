from pyspark.sql import functions as F
from pyspark.sql import Window as W


class RiskScoreAggregator:

    def __init__(self, df=0):
        self.df = df

    def _select_subset(self, df):
        return (df.select(
                'lob', 'risk_id', 'tranche', 'outcome', 'driver', 'subdriver',
                'attribute', 'exp_value', 'lore_value', 'risk_score_value',
                'case', 'year', 'default_run', 'run_vintage', 'risk_name',
                'is_crr'
                )
                .withColumn('frequency',
                F.col('lore_value') * F.col('exp_value'))
                .withColumn('attribute', F
                .when(F.col('attribute') == 'Electric Reliability', 'electric_reliability')
                .when(F.col('attribute') == 'Gas Reliability', 'gas_reliability')
                .when(F.col('attribute') == 'Financial', 'financial')
                .when(F.col('attribute') == 'Safety', 'safety')
                )
                )

    # Pivot the data by Attribute, taking the average of frequency and risk score
    # (there is only one value per attribute so average is fine).
    def _pivot_attributes(self, df, additional_cols=[]):
        return (df.drop('exp_value', 'lore_value')
                .groupby(
                    'lob', 'risk_id', 'driver', 'subdriver', 'tranche', 'outcome',
                    'case', 'year', 'default_run', 'run_vintage', 'is_crr', *additional_cols
        )
            .pivot('attribute', ['financial', 'safety', 'electric_reliability', 'gas_reliability'])
            .agg(
            F.avg('frequency').alias('frequency'),
            F.avg('risk_score_value').alias('risk_score')
        )
            .fillna(0)
        )

    def _compute_freq_and_total_score(self, df, additional_cols=[]):
        return (df

                # Create a new frequency column by taking the greatest value of the
                # four frequency columns created by the pivot.
                .withColumn('frequency', F.greatest(
                    F.col('financial_frequency'),
                    F.col('safety_frequency'),
                    F.col('electric_reliability_frequency'),
                    F.col('gas_reliability_frequency'),))

                # Create a new risk score column by taking the sum of the four risk score columns created by the pivot.
                .withColumn('risk_score', F.col('electric_reliability_risk_score')
                            + F.col('financial_risk_score')
                            + F.col('safety_risk_score')
                            + F.col('gas_reliability_risk_score')
                            )
                .select([
                    'lob', 'risk_id', 'frequency', 'risk_score', 'case',
                    'year', 'default_run', 'run_vintage', 'is_crr',
                ] + additional_cols)
                )

    # Create the frequency column by multiplying your aggregate LoRE by the exposure (exp_value).
    def _aggregate_scores(self, df, agg_cols=[], additional_cols=[]):
        return (df.groupby(['lob', 'risk_id', 'case', 'year', 'default_run', 'run_vintage', 'is_crr', ] + additional_cols)
                .agg(*[F.sum(c).alias(c) for c in agg_cols])
                )

    # Create percent of frequency and percent of risk score by using a window function over the
    # total frequency/risk score for each risk ID.
    def _compute_percentage_cols(self, df, agg_cols=[], partition_cols=[], prefix=''):
        for c in agg_cols:
            df = df.withColumn(f'{prefix}perc_{c}', F.col(
                c) / F.sum(c).over(W.partitionBy(partition_cols)))
        return df

    # Create primary and title keyes for ontolongy program object promotion
    def _create_keys(self, df, title_key, primary_key, additional_cols=[]):
        cols = [
            F.lit('Risk Score for '),
            F.col('lob'),
            F.col('risk_id'),
            *additional_cols,
        ]

        return (df.withColumn(title_key, F.concat_ws(' ', *cols))
                .withColumn(primary_key, F.row_number().over(W.orderBy('risk_id')))
                )

    def _verify_columns(self, df, expected_cols):
        set_exp_cols = set(expected_cols)
        set_all_cols = set(df.columns)
        set_exp_types = set([t for c, t in df.dtypes if c in expected_cols])
        set_num_types = set(['int', 'bigint', 'float', 'double', ])

        if not set_exp_cols.issubset(set_all_cols):
            raise Exception(
                'One of the expected columns does not exist in dataframe', [*set_all_cols])
        if not set_exp_types.issubset(set_num_types):
            raise Exception(
                'One of aggregation column\'s type are not numeric', [*set_num_types])

        return df

    def aggregate_risk_scores(self, agg_cols, additional_cols, df=0):
        if df == 0:
            df = self.df

        if sorted(additional_cols) == ['driver', 'subdriver', ]:
            method = 'risk_driver_subdriver_scores'
        elif sorted(additional_cols) == ['driver', 'outcome', ]:
            method = 'risk_outcome_scores'
        elif sorted(additional_cols) == ['driver', 'subdriver', 'tranche', ]:
            method = 'risk_tranche_driver_subdriver_scores'
        elif sorted(additional_cols) == ['outcome', 'tranche', ]:
            method = 'risk_tranche_scores'
        elif sorted(additional_cols) == ['tranche', ]:
            method = 'risk_scores_agg_tranche_processed'
        elif sorted(additional_cols) == ['risk_name', ]:
            method = 'risk_scores_crr_baseline'
        else:
            raise Exception('Please supply correct additional columns')

        if method == 'risk_scores_crr_baseline':
            df = self._select_subset(df)
            df = self._pivot_attributes(df, additional_cols)
            df = self._compute_freq_and_total_score(df, additional_cols + [
                'electric_reliability_risk_score', 'financial_risk_score',
                'safety_risk_score', 'gas_reliability_risk_score'
            ])
            df = self._verify_columns(df, agg_cols)
            df = self._aggregate_scores(df, agg_cols, additional_cols)

            lob_level_partition_cols = [
                'lob', 'case', 'year', 'default_run', 'is_crr'
            ]
            df = self._compute_percentage_cols(
                df, ['frequency', 'risk_score'], lob_level_partition_cols, prefix='lob_level_')

            case_level_partition_cols = [
                'case', 'year', 'default_run', 'is_crr'
            ]
            df = self._compute_percentage_cols(
                df, ['frequency', 'risk_score'], case_level_partition_cols, prefix='case_level_')

            df = df.withColumn(
                'risk_score_rank', F.row_number().over(W.partitionBy('case', 'year', 'is_crr', 'default_run').orderBy(
                    F.col('risk_score').desc()
                ))
            )
            df = df.withColumnRenamed('risk_score', 'total_risk_score')
            df = df.dropna()
            df = self._create_keys(
                df, 'title_key', '_primary_key', additional_cols)
        else:
            df = self._select_subset(df)
            df = self._pivot_attributes(df, additional_cols)
            df = self._compute_freq_and_total_score(df, additional_cols)
            df = self._verify_columns(df, agg_cols)
            df = self._aggregate_scores(df, agg_cols, additional_cols)
            partition_cols = ['lob', 'risk_id', 'case',
                              'year', 'default_run', 'is_crr']
            df = self._compute_percentage_cols(df, agg_cols, partition_cols)
            df = df.select(
                ['lob', 'risk_id', 'risk_score', 'frequency', 'case',
                    'year', 'default_run', 'run_vintage', 'is_crr', ]
                + [f'perc_{c}' for c in agg_cols] + additional_cols
            )
            df = df.dropna()
            df = self._create_keys(
                df, 'title_key', 'primary_key', additional_cols)

        return df
