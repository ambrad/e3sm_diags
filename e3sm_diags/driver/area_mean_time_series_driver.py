import collections
import json
import os

import cdms2
import cdutil

import e3sm_diags
from e3sm_diags.driver import utils
from e3sm_diags.logger import custom_logger
from e3sm_diags.metrics import mean
from e3sm_diags.plot.cartopy import area_mean_time_series_plot

logger = custom_logger(__name__)

RefsTestMetrics = collections.namedtuple("RefsTestMetrics", ["refs", "test", "metrics"])


def create_metrics(ref_domain):
    """
    For this plotset, calculate the mean of the
    reference data and return a dict of that.
    """
    return {"mean": mean(ref_domain)}


def run_diag(parameter):
    variables = parameter.variables
    regions = parameter.regions
    ref_names = parameter.ref_names

    # Both input data sets must be time-series files.
    # Raising an error will cause this specific set of
    # diagnostics with these parameters to be skipped.
    # if test_data.is_climo() or ref_data.is_climo():
    #    msg = 'Cannot run the plotset regional_mean_time_series '
    #    msg += 'because both the test and ref data need to be time-series files.'
    #    raise RuntimeError(msg)

    for var in variables:
        # The data that'll be sent to the plotting function.
        # There are eight tuples, each will be plotted like so:
        # [ 0 ]   [ 1 ]   [ 2 ]
        # [   ]   [   ]   [   ]
        #
        # [ 3 ]   [ 4 ]   [ 5 ]
        # [   ]   [   ]   [   ]
        #
        # [ 6 ]   [ 7 ]
        # [   ]   [   ]
        regions_to_data = collections.OrderedDict()
        save_data = {}
        logger.info("Variable: {}".format(var))

        # Get land/ocean fraction for masking.
        # For now, we're only using the climo data that we saved below.
        # So no time-series LANDFRAC or OCNFRAC from the user is used.
        mask_path = os.path.join(
            e3sm_diags.INSTALL_PATH, "acme_ne30_ocean_land_mask.nc"
        )
        with cdms2.open(mask_path) as f:
            land_frac = f("LANDFRAC")
            ocean_frac = f("OCNFRAC")

        for region in regions:
            # The regions that are supported are in e3sm_diags/derivations/default_regions.py
            # You can add your own if it's not in there.
            logger.info("Selected region: {}".format(region))
            test_data = utils.dataset.Dataset(parameter, test=True)
            test = test_data.get_timeseries_variable(var)
            logger.info(
                "Start and end time for selected time slices for test data: "
                f"{test.getTime().asComponentTime()[0]} "
                f"{test.getTime().asComponentTime()[-1]}",
            )

            parameter.viewer_descr[var] = getattr(test, "long_name", var)
            # Get the name of the data, appended with the years averaged.
            parameter.test_name_yrs = utils.general.get_name_and_yrs(
                parameter, test_data
            )
            test_domain = utils.general.select_region(
                region, test, land_frac, ocean_frac, parameter
            )

            # Average over selected region, and average
            # over months to get the yearly mean.
            test_domain = cdutil.averager(test_domain, axis="xy")
            cdutil.setTimeBoundsMonthly(test_domain)
            test_domain_year = cdutil.YEAR(test_domain)
            # add back attributes since they got lost after applying cdutil.YEAR
            test_domain_year.long_name = test.long_name
            test_domain_year.units = test.units

            save_data[parameter.test_name_yrs] = test_domain_year.asma().tolist()

            refs = []

            for ref_name in ref_names:
                setattr(parameter, "ref_name", ref_name)
                ref_data = utils.dataset.Dataset(parameter, ref=True)

                parameter.ref_name_yrs = utils.general.get_name_and_yrs(
                    parameter, ref_data
                )

                try:
                    ref = ref_data.get_timeseries_variable(var)

                    ref_domain = utils.general.select_region(
                        region, ref, land_frac, ocean_frac, parameter
                    )

                    ref_domain = cdutil.averager(ref_domain, axis="xy")
                    cdutil.setTimeBoundsMonthly(ref_domain)
                    logger.info(
                        (
                            "Start and end time for selected time slices for ref data: "
                            f"{ref_domain.getTime().asComponentTime()[0]} "
                            f"{ref_domain.getTime().asComponentTime()[-1]}"
                        )
                    )

                    ref_domain_year = cdutil.YEAR(ref_domain)
                    ref_domain_year.ref_name = ref_name
                    save_data[ref_name] = ref_domain_year.asma().tolist()

                    refs.append(ref_domain_year)
                except Exception:
                    logger.exception(
                        "No valid value for reference datasets available for the specified time range"
                    )

            # save data for potential later use
            parameter.output_file = "-".join([var, region])
            fnm = os.path.join(
                utils.general.get_output_dir(parameter.current_set, parameter),
                parameter.output_file + ".json",
            )

            with open(fnm, "w") as outfile:
                json.dump(save_data, outfile)

            regions_to_data[region] = RefsTestMetrics(
                test=test_domain_year, refs=refs, metrics=[]
            )

        area_mean_time_series_plot.plot(var, regions_to_data, parameter)

    return parameter
