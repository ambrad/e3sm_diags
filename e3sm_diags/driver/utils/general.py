from __future__ import print_function

import copy
import errno
import os
from pathlib import Path

import cdms2
import cdutil
import genutil
import MV2

from e3sm_diags.derivations.default_regions import points_specs, regions_specs
from e3sm_diags.logger import custom_logger

logger = custom_logger(__name__)


def strictly_increasing(L):
    return all(x < y for x, y in zip(L, L[1:]))


def strictly_decreasing(L):
    return all(x > y for x, y in zip(L, L[1:]))


def monotonically_decreasing(L):
    return all(x >= y for x, y in zip(L, L[1:]))


def monotonically_increasing(L):
    return all(x <= y for x, y in zip(L, L[1:]))


def monotonic(L):
    return monotonically_increasing(L) or monotonically_decreasing(L)


def adjust_time_from_time_bounds(var):
    """
    Redefine time to be in the middle of the time interval, and rewrite
    the time axis. This is important for data where the absolute time doesn't fall in the middle of the time interval, such as E3SM, the time was recorded at the end of each time Bounds.
    """
    var_time = var.getTime()
    tbounds = var_time.getBounds()
    var_time[:] = 0.5 * (tbounds[:, 0] + tbounds[:, 1])
    time2 = cdms2.createAxis(var_time)
    time2.designateTime()
    # .designateTime() needs to be set before attributes changes.
    time2.units = var_time.units
    time2.calendar = var_time.calendar
    time2.setBounds(tbounds)
    # time2.calendar = cdtime.NoLeapCalendar
    time2.id = "time"
    var.setAxis(0, time2)
    #    cdutil.setTimeBoundsMonthly(var)

    return var


def get_name_and_yrs(parameters, dataset, season=""):
    """
    Given either test or ref data, get the name of the data
    (test_name or reference_name), along with the years averaged.
    """

    name = get_name(parameters, dataset)
    yrs_averaged = get_yrs(dataset, season)
    if yrs_averaged:
        name_yrs = "{} ({})".format(name, yrs_averaged)
    else:
        name_yrs = name

    return name_yrs


def get_name(parameters, dataset):
    if dataset.test:
        if parameters.short_test_name:
            name = parameters.short_test_name
        else:
            name = parameters.test_name
    else:
        if parameters.short_ref_name:
            name = parameters.short_ref_name
        else:
            # parameter.ref_name is used to search though the reference data directories.
            # parameter.reference_name is printed above ref plots.
            name = parameters.reference_name
    return name


def get_yrs(dataset, season=""):
    if dataset.is_climo():
        try:
            yrs_averaged = dataset.get_attr_from_climo("yrs_averaged", season)
        except Exception:
            yrs_averaged = ""
    else:
        start_yr, end_yr, sub_monthly = dataset.get_start_and_end_years()
        yrs_averaged = "{}-{}".format(start_yr, end_yr)
    return yrs_averaged


def convert_to_pressure_levels(mv, plevs, dataset, var, season):
    """
    Given either test or reference data with a z-axis,
    convert to the desired pressure levels.
    """
    mv_plv = mv.getLevel()
    # var(time,lev,lon,lat) convert from hybrid level to pressure
    if mv_plv.long_name.lower().find("hybrid") != -1:
        extra_vars = ["hyam", "hybm", "PS"]
        hyam, hybm, ps = dataset.get_extra_variables_only(
            var, season, extra_vars=extra_vars
        )
        mv_p = hybrid_to_plevs(mv, hyam, hybm, ps, plevs)

    # levels are pressure levels
    elif (
        mv_plv.long_name.lower().find("pressure") != -1
        or mv_plv.long_name.lower().find("isobaric") != -1
    ):
        mv_p = pressure_to_plevs(mv, plevs)

    else:
        raise RuntimeError("Vertical level is neither hybrid nor pressure. Aborting.")

    return mv_p


def hybrid_to_plevs(var, hyam, hybm, ps, plev):
    """Convert from hybrid pressure coordinate to desired pressure level(s)."""
    p0 = 1000.0  # mb
    ps = ps / 100.0  # convert unit from 'Pa' to mb
    levels_orig = cdutil.vertical.reconstructPressureFromHybrid(ps, hyam, hybm, p0)
    levels_orig.units = "mb"
    # Make sure z is positive down
    if var.getLevel()[0] > var.getLevel()[-1]:
        var = var(lev=slice(-1, None, -1))
        levels_orig = levels_orig(lev=slice(-1, None, -1))
    var_p = cdutil.vertical.logLinearInterpolation(
        var(squeeze=1), levels_orig(squeeze=1), plev
    )

    return var_p


def pressure_to_plevs(var, plev):
    """Convert from pressure coordinate to desired pressure level(s)."""
    # Construct pressure level for interpolation
    var_plv = var.getLevel()
    if var_plv.units == "Pa":
        var_plv[:] = var_plv[:] / 100.0  # convert Pa to mb
    levels_orig = MV2.array(var_plv[:])
    levels_orig.setAxis(0, var_plv)
    # grow 1d levels_orig to mv dimention
    var, levels_orig = genutil.grower(var, levels_orig)
    # levels_orig.info()
    # logLinearInterpolation only takes positive down plevel:
    # "I :      interpolation field (usually Pressure or depth)
    # from TOP (level 0) to BOTTOM (last level), i.e P value
    # going up with each level"
    if var.getLevel()[0] > var.getLevel()[-1]:
        var = var(lev=slice(-1, None, -1))
        levels_orig = levels_orig(lev=slice(-1, None, -1))
    var_p = cdutil.vertical.logLinearInterpolation(
        var(squeeze=1), levels_orig(squeeze=1), plev
    )

    return var_p


def select_region_lat_lon(region, var, parameter):
    """Select desired regions from transient variables (no mask)."""
    try:
        # if region.find('global') == -1:
        domain = regions_specs[region]["domain"]  # type: ignore
    except Exception:
        pass

    var_selected = var(domain)
    var_selected.units = var.units

    return var_selected


def select_region(region, var, land_frac, ocean_frac, parameter):
    """Select desired regions from transient variables."""
    domain = None
    # if region != 'global':
    if region.find("land") != -1 or region.find("ocean") != -1:
        if region.find("land") != -1:
            land_ocean_frac = land_frac
        elif region.find("ocean") != -1:
            land_ocean_frac = ocean_frac
        region_value = regions_specs[region]["value"]  # type: ignore

        land_ocean_frac = land_ocean_frac.regrid(
            var.getGrid(),
            regridTool=parameter.regrid_tool,
            regridMethod=parameter.regrid_method,
        )

        var_domain = mask_by(var, land_ocean_frac, low_limit=region_value)
    else:
        var_domain = var

    try:
        # if region.find('global') == -1:
        domain = regions_specs[region]["domain"]  # type: ignore
    except Exception:
        pass

    var_domain_selected = var_domain(domain)
    var_domain_selected.units = var.units

    return var_domain_selected


def select_point(region, var):
    """Select desired point from transient variables."""

    lat = points_specs[region][0]
    lon = points_specs[region][1]
    select = points_specs[region][2]

    try:
        var_selected = var(
            latitude=(lat, lat, select),
            longitude=(lon, lon, select),
            squeeze=1,
        )
    except Exception:
        logger.info("No point selected.")

    return var_selected


def regrid_to_lower_res(mv1, mv2, regrid_tool, regrid_method):
    """Regrid transient variable toward lower resolution of two variables."""

    axes1 = mv1.getAxisList()
    axes2 = mv2.getAxisList()

    # use nlat to decide data resolution, higher number means higher data
    # resolution. For the difference plot, regrid toward lower resolution
    if len(axes1[1]) <= len(axes2[1]):
        mv_grid = mv1.getGrid()
        mv1_reg = mv1
        mv2_reg = mv2.regrid(
            mv_grid, regridTool=regrid_tool, regridMethod=regrid_method
        )
        mv2_reg.units = mv2.units

    else:
        mv_grid = mv2.getGrid()
        mv2_reg = mv2
        mv1_reg = mv1.regrid(
            mv_grid, regridTool=regrid_tool, regridMethod=regrid_method
        )
        mv1_reg.units = mv1.units

    return mv1_reg, mv2_reg


def mask_by(input_var, maskvar, low_limit=None, high_limit=None):
    """masks a variable var to be missing except where maskvar>=low_limit and maskvar<=high_limit.
    None means to omit the constrint, i.e. low_limit = -infinity or high_limit = infinity.
    var is changed and returned; we don't make a new variable.
    var and maskvar: dimensioned the same variables.
    low_limit and high_limit: scalars.
    """
    var = copy.deepcopy(input_var)
    if low_limit is None and high_limit is None:
        return var
    if low_limit is None and high_limit is not None:
        maskvarmask = maskvar > high_limit
    elif low_limit is not None and high_limit is None:
        maskvarmask = maskvar < low_limit
    else:
        maskvarmask = (maskvar < low_limit) | (maskvar > high_limit)
    if var.mask is False:
        newmask = maskvarmask
    else:
        newmask = var.mask | maskvarmask
    var.mask = newmask
    return var


def save_transient_variables_to_netcdf(set_num, variables_dict, label, parameter):
    """
    Save the transient variables to nc file.
    """
    if parameter.save_netcdf:
        for (variable_name, variable) in variables_dict.items():
            # Set cdms preferences - no compression, no shuffling, no complaining
            cdms2.setNetcdfDeflateFlag(1)
            # 1-9, min to max - Comes at heavy IO (read/write time cost)
            cdms2.setNetcdfDeflateLevelFlag(0)
            cdms2.setNetcdfShuffleFlag(0)
            cdms2.setCompressionWarnings(0)  # Turn off warning messages

            path = get_output_dir(set_num, parameter)
            # Save variable
            try:
                variable.id = parameter.var_id
            except AttributeError:
                logger.error("Could not save variable.id for {}".format(variable_name))
            file_name = "{}_{}_{}.nc".format(
                parameter.output_file, variable_name, label
            )
            test_pth = os.path.join(path, file_name)
            with cdms2.open(test_pth, "w+") as file_test:
                try:
                    file_test.write(variable)
                except AttributeError:
                    logger.error("Could not write variable {}".format(variable_name))


def save_ncfiles(set_num, test, ref, diff, parameter):
    """
    Saves the test, reference, and difference
    data being plotted as nc files.
    """
    if parameter.save_netcdf:
        # Save files being plotted
        # Set cdms preferences - no compression, no shuffling, no complaining
        cdms2.setNetcdfDeflateFlag(1)
        # 1-9, min to max - Comes at heavy IO (read/write time cost)
        cdms2.setNetcdfDeflateLevelFlag(0)
        cdms2.setNetcdfShuffleFlag(0)
        cdms2.setCompressionWarnings(0)  # Turn off warning messages

        pth = get_output_dir(set_num, parameter)

        # Save test file
        if test.id.startswith("variable_"):
            test.id = parameter.var_id
        test_pth = os.path.join(pth, parameter.output_file + "_test.nc")

        cdms_arg = "w"

        if Path(test_pth).is_file():
            cdms_arg = "a"

        with cdms2.open(test_pth, cdms_arg) as file_test:
            file_test.write(test)

        # Save reference file
        if ref.id.startswith("variable_"):
            ref.id = parameter.var_id
        ref_pth = os.path.join(pth, parameter.output_file + "_ref.nc")
        with cdms2.open(ref_pth, cdms_arg) as file_ref:
            file_ref.write(ref)

        # Save difference file
        if diff is not None:
            if diff.id.startswith("variable_"):
                diff.id = parameter.var_id + "_diff"
            diff_pth = os.path.join(pth, parameter.output_file + "_diff.nc")
            with cdms2.open(diff_pth, cdms_arg) as file_diff:
                file_diff.write(diff)


def get_output_dir(set_num, parameter):
    """
    Get the directory of where to save the outputs for a run.
    """
    results_dir = parameter.results_dir
    pth = os.path.join(results_dir, "{}".format(set_num), parameter.case_id)

    if not os.path.exists(pth):
        # When running diags in parallel, sometimes another process will create the dir.
        try:
            os.makedirs(pth, 0o755)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    return pth
