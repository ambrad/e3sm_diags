from e3sm_diags.parameter.diurnal_cycle_parameter import DiurnalCycleParameter

from .core_parser import CoreParser


class DiurnalCycleParser(CoreParser):
    def __init__(self, *args, **kwargs):
        if "parameter_cls" in kwargs:
            super().__init__(*args, **kwargs)
        else:
            super().__init__(parameter_cls=DiurnalCycleParameter, *args, **kwargs)

    def load_default_args(self, files=[]):
        # This has '-p' and '--parameter' reserved.
        super().load_default_args(files)

        self.add_argument(
            "--ref_timeseries_input",
            dest="ref_timeseries_input",
            help="The input reference data are timeseries files.",
            action="store_const",
            const=True,
            required=False,
        )

        self.add_argument(
            "--test_timeseries_input",
            dest="test_timeseries_input",
            help="The input test data are timeseries files.",
            action="store_const",
            const=True,
            required=False,
        )

        self.add_argument(
            "--start_yr",
            dest="start_yr",
            help="Start year for the timeseries files.",
            required=False,
        )

        self.add_argument(
            "--end_yr",
            dest="end_yr",
            help="End year for the timeseries files.",
            required=False,
        )

        self.add_argument(
            "--normalize_test_amp",
            dest="normalize_test_amp",
            help="Normalize test data by maximum diurnal cycle amplitude from reference data",
            required=False,
        )
