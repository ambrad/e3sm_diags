from __future__ import print_function

import copy
from collections import OrderedDict
from typing import TYPE_CHECKING, Optional, Tuple

import MV2
import numpy as np
from genutil import udunits

if TYPE_CHECKING:
    from cdms2.axis import FileAxis
    from cdms2.fvariable import FileVariable


def rename(new_name):
    """Given the new name, just return it."""
    return new_name


def aplusb(var1, var2, target_units=None):
    """Returns var1 + var2. If both of their units are not the same,
    it tries to convert both of their units to target_units"""

    if target_units is not None:
        var1 = convert_units(var1, target_units)
        var2 = convert_units(var2, target_units)

    return var1 + var2


def convert_units(var, target_units):
    """Converts units of var to target_units.
    var is a cdms.TransientVariable."""

    if not hasattr(var, "units") and var.id == "SST":
        var.units = target_units
    elif not hasattr(var, "units") and var.id == "ICEFRAC":
        var.units = target_units
        var = 100.0 * var
    elif not hasattr(var, "units") and var.id == "AODVIS":
        var.units = target_units
    elif var.id == "AOD_550_ann":
        var.units = target_units
    elif var.units == "C" and target_units == "DegC":
        var.units = target_units
    elif var.units == "N/m2" and target_units == "N/m^2":
        var.units = target_units
    elif var.id == "AODVIS" or var.id == "AOD_550_ann":
        var.units = target_units
    elif var.units == "fraction":
        var = 100.0 * var
        var.units = target_units
    elif var.units == "mb":
        var.units = target_units
    elif var.units == "gpm":  # geopotential meter
        var = var / 9.8 / 100  # convert to hecto meter
        var.units = target_units
    elif var.units == "Pa/s":
        var = var / 100.0 * 24 * 3600
        var.units = target_units
    elif var.units == "mb/day":
        var = var
        var.units = target_units
    elif var.id == "prw" and var.units == "cm":
        var = var * 10.0  # convert from 'cm' to 'kg/m2' or 'mm'
        var.units = target_units
    else:
        temp = udunits(1.0, var.units)
        coeff, offset = temp.how(target_units)
        var = coeff * var + offset
        var.units = target_units

    return var


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


def qflxconvert_units(var):
    if var.units == "kg/m2/s" or var.units == "kg m-2 s-1" or var.units == "mm/s":
        # need to find a solution for units not included in udunits
        # var = convert_units( var, 'kg/m2/s' )
        var = var * 3600.0 * 24  # convert to mm/day
        var.units = "mm/day"
    elif var.units == "mm/hr":
        var = var * 24.0
        var.units = "mm/day"
    return var


def qflx_convert_to_lhflx(qflx, precc, precl, precsc, precsl):
    # A more precise formula to close atmospheric energy budget:
    # LHFLX is modified to account for the latent energy of frozen precipitation.
    # LHFLX = (Lv+Lf)*QFLX - Lf*1.e3*(PRECC+PRECL-PRECSC-PRECSL)
    # Constants, from AMWG diagnostics
    Lv = 2.501e6
    Lf = 3.337e5
    var = (Lv + Lf) * qflx - Lf * 1.0e3 * (precc + precl - precsc - precsl)
    var.units = "W/m2"
    var.long_name = "Surface latent heat flux"
    return var


def qflx_convert_to_lhflx_approxi(var):
    # QFLX units: kg/((m^2)*s)
    # Multiply by the latent heat of condensation/vaporization (in J/kg)
    # kg/((m^2)*s) * J/kg = J/((m^2)*s) = (W*s)/((m^2)*s) = W/(m^2)
    var.units = "W/m2"
    return var * 2.5e6


def pminuse_convert_units(var):
    if var.units == "kg/m2/s" or var.units == "kg m-2 s-1" or var.units == "kg/s/m^2":
        # need to find a solution for units not included in udunits
        # var = convert_units( var, 'kg/m2/s' )
        var = var * 3600.0 * 24  # convert to mm/day
        var.units = "mm/day"
    var.long_name = "precip. flux - evap. flux"
    return var


def prect(precc, precl):
    """Total precipitation flux = convective + large-scale"""
    var = precc + precl
    var = convert_units(var, "mm/day")
    var.long_name = "Total precipitation rate (convective + large-scale)"
    return var


def precst(precc, precl):
    """Total precipitation flux = convective + large-scale"""
    var = precc + precl
    var = convert_units(var, "mm/day")
    var.long_name = "Total snowfall flux (convective + large-scale)"
    return var


def tref_range(tmax, tmin):
    """TREF daily range = TREFMXAV - TREFMNAV"""
    var = tmax - tmin
    var.units = "K"
    var.long_name = "Surface Temperature Daily Range"
    return var


def tauxy(taux, tauy):
    """tauxy = (taux^2 + tauy^2)sqrt"""
    var = (taux**2 + tauy**2) ** 0.5
    var = convert_units(var, "N/m^2")
    var.long_name = "Total surface wind stress"
    return var


def albedo(rsdt, rsut):
    """TOA (top-of-atmosphere) albedo, rsut / rsdt, unit is nondimension"""
    var = rsut / rsdt
    var.units = "dimensionless"
    var.long_name = "TOA albedo"
    return var


def albedoc(rsdt, rsutcs):
    """TOA (top-of-atmosphere) albedo clear-sky, rsutcs / rsdt, unit is nondimension"""
    var = rsutcs / rsdt
    var.units = "dimensionless"
    var.long_name = "TOA albedo clear-sky"
    return var


def albedo_srf(rsds, rsus):
    """Surface albedo, rsus / rsds, unit is nondimension"""
    var = rsus / rsds
    var.units = "dimensionless"
    var.long_name = "Surface albedo"
    return var


def rst(rsdt, rsut):
    """TOA (top-of-atmosphere) net shortwave flux"""
    var = rsdt - rsut
    var.long_name = "TOA net shortwave flux"
    return var


def rstcs(rsdt, rsutcs):
    """TOA (top-of-atmosphere) net shortwave flux clear-sky"""
    var = rsdt - rsutcs
    var.long_name = "TOA net shortwave flux clear-sky"
    return var


def swcfsrf(fsns, fsnsc):
    """Surface shortwave cloud forcing"""
    var = fsns - fsnsc
    var.long_name = "Surface shortwave cloud forcing"
    return var


def lwcfsrf(flns, flnsc):
    """Surface longwave cloud forcing, for ACME model, upward is postitive for LW , for ceres, downward is postive for both LW and SW"""
    var = -(flns - flnsc)
    var.long_name = "Surface longwave cloud forcing"
    return var


def swcf(fsntoa, fsntoac):
    """TOA shortwave cloud forcing"""
    var = fsntoa - fsntoac
    var.long_name = "TOA shortwave cloud forcing"
    return var


def lwcf(flntoa, flntoac):
    """TOA longwave cloud forcing"""
    var = flntoa - flntoac
    var.long_name = "TOA longwave cloud forcing"
    return var


def netcf2(swcf, lwcf):
    """TOA net cloud forcing"""
    var = swcf + lwcf
    var.long_name = "TOA net cloud forcing"
    return var


def netcf4(fsntoa, fsntoac, flntoa, flntoac):
    """TOA net cloud forcing"""
    var = fsntoa - fsntoac + flntoa - flntoac
    var.long_name = "TOA net cloud forcing"
    return var


def netcf2srf(swcf, lwcf):
    """Surface net cloud forcing"""
    var = swcf + lwcf
    var.long_name = "Surface net cloud forcing"
    return var


def netcf4srf(fsntoa, fsntoac, flntoa, flntoac):
    """Surface net cloud forcing"""
    var = fsntoa - fsntoac + flntoa - flntoac
    var.long_name = "Surface net cloud forcing"
    return var


def fldsc(ts, flnsc):
    """Clearsky Surf LW downwelling flux"""
    var = 5.67e-8 * ts**4 - flnsc
    var.units = "W/m2"
    var.long_name = "Clearsky Surf LW downwelling flux"
    return var


def restom(fsnt, flnt):
    """TOM(top of model) Radiative flux"""
    var = fsnt - flnt
    var.long_name = "TOM(top of model) Radiative flux"
    return var


def restoa(fsnt, flnt):
    """TOA(top of atmosphere) Radiative flux"""
    var = fsnt - flnt
    var.long_name = "TOA(top of atmosphere) Radiative flux"
    return var


def flus(flds, flns):
    """Surface Upwelling LW Radiative flux"""
    var = flns + flds
    var.long_name = "Upwelling longwave flux at surface"
    return var


def fsus(fsds, fsns):
    """Surface Up-welling SW Radiative flux"""
    var = fsds - fsns
    var.long_name = "Upwelling shortwave flux at surface"
    return var


def netsw(rsds, rsus):
    """Surface SW Radiative flux"""
    var = rsds - rsus
    var.long_name = "Surface SW Radiative flux"
    return var


def netlw(rlds, rlus):
    """Surface LW Radiative flux"""
    var = -(rlds - rlus)
    var.long_name = "Surface LW Radiative flux"
    return var


def netflux4(fsns, flns, lhflx, shflx):
    """Surface Net flux"""
    var = fsns - flns - lhflx - shflx
    var.long_name = "Surface Net flux"
    return var


def netflux6(rsds, rsus, rlds, rlus, hfls, hfss):
    """Surface Net flux"""
    var = rsds - rsus + (rlds - rlus) - hfls - hfss
    var.long_name = "Surface Net flux"
    return var


def adjust_prs_val_units(
    prs: "FileAxis", prs_val: float, prs_val0: Optional[float]
) -> float:
    """Adjust the prs_val units based on the prs.id"""
    # COSP v2 cosp_pr in units Pa instead of hPa as in v1
    # COSP v2 cosp_htmisr in units m instead of km as in v1
    adjust_ids = {"cosp_prs": 100, "cosp_htmisr": 1000}

    if prs_val0:
        prs_val = prs_val0
        if prs.id in adjust_ids.keys() and max(prs.getData()) > 1000:
            prs_val = prs_val * adjust_ids[prs.id]

    return prs_val


def determine_cloud_level(
    prs_low: float,
    prs_high: float,
    low_bnds: Tuple[int, int],
    high_bnds: Tuple[int, int],
) -> str:
    """Determines the cloud type based on prs values and the specified boundaries"""
    # Threshold for cloud top height: high cloud (<440hPa or > 7km), midlevel cloud (440-680hPa, 3-7 km) and low clouds (>680hPa, < 3km)
    if prs_low in low_bnds and prs_high in high_bnds:
        return "middle cloud fraction"
    elif prs_low in low_bnds:
        return "high cloud fraction"
    elif prs_high in high_bnds:
        return "low cloud fraction"
    else:
        return "total cloud fraction"


def cosp_bin_sum(
    cld: "FileVariable",
    prs_low0: Optional[float],
    prs_high0: Optional[float],
    tau_low0: Optional[float],
    tau_high0: Optional[float],
):
    """sum of cosp bins to calculate cloud fraction in specified cloud top pressure / height and
    cloud thickness bins, input variable has dimension (cosp_prs,cosp_tau,lat,lon)/(cosp_ht,cosp_tau,lat,lon)"""
    prs: FileAxis = cld.getAxis(0)
    tau: FileAxis = cld.getAxis(1)

    prs_low: float = adjust_prs_val_units(prs, prs[0], prs_low0)
    prs_high: float = adjust_prs_val_units(prs, prs[-1], prs_high0)

    if prs_low0 is None and prs_high0 is None:
        prs_lim = "total cloud fraction"

    tau_high, tau_low, tau_lim = determine_tau(tau, tau_low0, tau_high0)

    if cld.id == "FISCCP1_COSP":  # ISCCP model
        cld_bin = cld(cosp_prs=(prs_low, prs_high), cosp_tau=(tau_low, tau_high))
        simulator = "ISCCP"
    if cld.id == "CLISCCP":  # ISCCP obs
        cld_bin = cld(isccp_prs=(prs_low, prs_high), isccp_tau=(tau_low, tau_high))

    if cld.id == "CLMODIS":  # MODIS
        prs_lim = determine_cloud_level(prs_low, prs_high, (440, 44000), (680, 68000))
        simulator = "MODIS"

        if prs.id == "cosp_prs":  # Model
            cld_bin = cld(
                cosp_prs=(prs_low, prs_high), cosp_tau_modis=(tau_low, tau_high)
            )
        elif prs.id == "modis_prs":  # Obs
            cld_bin = cld(modis_prs=(prs_low, prs_high), modis_tau=(tau_low, tau_high))

    if cld.id == "CLD_MISR":  # MISR model
        if max(prs) > 1000:  # COSP v2 cosp_htmisr in units m instead of km as in v1
            cld = cld[
                1:, :, :, :
            ]  # COSP v2 cosp_htmisr[0] equals to 0 instead of -99 as in v1, therefore cld needs to be masked manually
        cld_bin = cld(cosp_htmisr=(prs_low, prs_high), cosp_tau=(tau_low, tau_high))
        prs_lim = determine_cloud_level(prs_low, prs_high, (7, 7000), (3, 3000))
        simulator = "MISR"
    if cld.id == "CLMISR":  # MISR obs
        cld_bin = cld(misr_cth=(prs_low, prs_high), misr_tau=(tau_low, tau_high))

    cld_bin_sum = MV2.sum(MV2.sum(cld_bin, axis=1), axis=0)

    try:
        cld_bin_sum.long_name = simulator + ": " + prs_lim + " with " + tau_lim
        # cld_bin_sum.long_name = "{}: {} with {}".format(simulator, prs_lim, tau_lim)
    except BaseException:
        pass
    return cld_bin_sum


def determine_tau(
    tau: "FileAxis", tau_low0: Optional[float], tau_high0: Optional[float]
):
    tau_low = tau[0]
    tau_high = tau[-1]

    if tau_low0 is None and tau_high0:
        tau_high = tau_high0
        tau_lim = "tau <" + str(tau_high0)
    elif tau_high0 is None and tau_low0:
        tau_low = tau_low0
        tau_lim = "tau >" + str(tau_low0)
    elif tau_low0 is None and tau_high0 is None:
        tau_lim = str(tau_low) + "< tau < " + str(tau_high)
    else:
        tau_low = tau_low0
        tau_high = tau_high0
        tau_lim = str(tau_low) + "< tau < " + str(tau_high)

    return tau_high, tau_low, tau_lim


def cosp_histogram_standardize(cld: "FileVariable"):
    """standarize cloud top pressure and cloud thickness bins to dimensions that
    suitable for plotting, input variable has dimention (cosp_prs,cosp_tau)"""
    prs = cld.getAxis(0)
    tau = cld.getAxis(1)

    prs[0]
    prs_high = prs[-1]
    tau[0]
    tau_high = tau[-1]

    prs_bounds = getattr(prs, "bounds")
    if prs_bounds is None:
        cloud_prs_bounds = np.array(
            [
                [1000.0, 800.0],
                [800.0, 680.0],
                [680.0, 560.0],
                [560.0, 440.0],
                [440.0, 310.0],
                [310.0, 180.0],
                [180.0, 0.0],
            ]
        )  # length 7
        prs.setBounds(np.array(cloud_prs_bounds, dtype=np.float32))

    tau_bounds = getattr(tau, "bounds")
    if tau_bounds is None:
        cloud_tau_bounds = np.array(
            [
                [0.3, 1.3],
                [1.3, 3.6],
                [3.6, 9.4],
                [9.4, 23],
                [23, 60],
                [60, 379],
            ]
        )  # length 6
        tau.setBounds(np.array(cloud_tau_bounds, dtype=np.float32))

    if cld.id == "FISCCP1_COSP":  # ISCCP model
        cld_hist = cld(cosp_tau=(0.3, tau_high))
    if cld.id == "CLISCCP":  # ISCCP obs
        cld_hist = cld(isccp_tau=(0.3, tau_high))

    if cld.id == "CLMODIS":  # MODIS
        try:
            cld_hist = cld(cosp_tau_modis=(0.3, tau_high))  # MODIS model
        except BaseException:
            cld_hist = cld(modis_tau=(0.3, tau_high))  # MODIS obs

    if cld.id == "CLD_MISR":  # MISR model
        if max(prs) > 1000:  # COSP v2 cosp_htmisr in units m instead of km as in v1
            cld = cld[
                1:, :, :, :
            ]  # COSP v2 cosp_htmisr[0] equals to 0 instead of -99 as in v1, therefore cld needs to be masked manually
            prs_high = 1000.0 * prs_high
        cld_hist = cld(cosp_tau=(0.3, tau_high), cosp_htmisr=(0, prs_high))
    if cld.id == "CLMISR":  # MISR obs
        cld_hist = cld(misr_tau=(0.3, tau_high), misr_cth=(0, prs_high))

    return cld_hist


# derived_variables is a dictionary to accomodate user specified derived variables.
# The driver search for available variable keys and functions to calculate derived variable.
# For example
# In derived_variable there is an entry for 'PRECT':
# If 'PRECT' is not available, but both 'PRECC' and 'PRECT' are available in the netcdf variable keys,
# PRECT is calculated using fuction prect() with precc and precl as inputs.

derived_variables = {
    "PRECT": OrderedDict(
        [
            (
                ("PRECT",),
                lambda pr: convert_units(rename(pr), target_units="mm/day"),
            ),
            (("pr",), lambda pr: qflxconvert_units(rename(pr))),
            (("PRECC", "PRECL"), lambda precc, precl: prect(precc, precl)),
        ]
    ),
    "PRECST": OrderedDict(
        [
            (("prsn",), lambda prsn: qflxconvert_units(rename(prsn))),
            (
                ("PRECSC", "PRECSL"),
                lambda precsc, precsl: precst(precsc, precsl),
            ),
        ]
    ),
    # Sea Surface Temperature: Degrees C
    # Temperature of the water, not the air. Ignore land.
    "SST": OrderedDict(
        [
            # lambda sst: convert_units(rename(sst),target_units="degC")),
            (("sst",), rename),
            (
                ("TS", "OCNFRAC"),
                lambda ts, ocnfrac: mask_by(
                    convert_units(ts, target_units="degC"),
                    ocnfrac,
                    low_limit=0.9,
                ),
            ),
            (("SST",), lambda sst: convert_units(sst, target_units="degC")),
        ]
    ),
    "TMQ": OrderedDict(
        [
            (("PREH2O",), rename),
            (
                ("prw",),
                lambda prw: convert_units(rename(prw), target_units="kg/m2"),
            ),
        ]
    ),
    "SOLIN": OrderedDict([(("rsdt",), rename)]),
    "ALBEDO": OrderedDict(
        [
            (("ALBEDO",), rename),
            (
                ("SOLIN", "FSNTOA"),
                lambda solin, fsntoa: albedo(solin, solin - fsntoa),
            ),
            (("rsdt", "rsut"), lambda rsdt, rsut: albedo(rsdt, rsut)),
        ]
    ),
    "ALBEDOC": OrderedDict(
        [
            (("ALBEDOC",), rename),
            (
                ("SOLIN", "FSNTOAC"),
                lambda solin, fsntoac: albedoc(solin, solin - fsntoac),
            ),
            (("rsdt", "rsutcs"), lambda rsdt, rsutcs: albedoc(rsdt, rsutcs)),
        ]
    ),
    "ALBEDO_SRF": OrderedDict(
        [
            (("ALBEDO_SRF",), rename),
            (("rsds", "rsus"), lambda rsds, rsus: albedo_srf(rsds, rsus)),
            (
                ("FSDS", "FSNS"),
                lambda fsds, fsns: albedo_srf(fsds, fsds - fsns),
            ),
        ]
    ),
    # Pay attention to the positive direction of SW and LW fluxes
    "SWCF": OrderedDict(
        [
            (("SWCF",), rename),
            (
                ("toa_net_sw_all_mon", "toa_net_sw_clr_mon"),
                lambda net_all, net_clr: swcf(net_all, net_clr),
            ),
            (
                ("toa_net_sw_all_mon", "toa_net_sw_clr_t_mon"),
                lambda net_all, net_clr: swcf(net_all, net_clr),
            ),
            (("toa_cre_sw_mon",), rename),
            (
                ("FSNTOA", "FSNTOAC"),
                lambda fsntoa, fsntoac: swcf(fsntoa, fsntoac),
            ),
            (("rsut", "rsutcs"), lambda rsutcs, rsut: swcf(rsut, rsutcs)),
        ]
    ),
    "SWCFSRF": OrderedDict(
        [
            (("SWCFSRF",), rename),
            (
                ("sfc_net_sw_all_mon", "sfc_net_sw_clr_mon"),
                lambda net_all, net_clr: swcfsrf(net_all, net_clr),
            ),
            (
                ("sfc_net_sw_all_mon", "sfc_net_sw_clr_t_mon"),
                lambda net_all, net_clr: swcfsrf(net_all, net_clr),
            ),
            (("sfc_cre_net_sw_mon",), rename),
            (("FSNS", "FSNSC"), lambda fsns, fsnsc: swcfsrf(fsns, fsnsc)),
        ]
    ),
    "LWCF": OrderedDict(
        [
            (("LWCF",), rename),
            (
                ("toa_net_lw_all_mon", "toa_net_lw_clr_mon"),
                lambda net_all, net_clr: lwcf(net_clr, net_all),
            ),
            (
                ("toa_net_lw_all_mon", "toa_net_lw_clr_t_mon"),
                lambda net_all, net_clr: lwcf(net_clr, net_all),
            ),
            (("toa_cre_lw_mon",), rename),
            (
                ("FLNTOA", "FLNTOAC"),
                lambda flntoa, flntoac: lwcf(flntoa, flntoac),
            ),
            (("rlut", "rlutcs"), lambda rlutcs, rlut: lwcf(rlut, rlutcs)),
        ]
    ),
    "LWCFSRF": OrderedDict(
        [
            (("LWCFSRF",), rename),
            (
                ("sfc_net_lw_all_mon", "sfc_net_lw_clr_mon"),
                lambda net_all, net_clr: lwcfsrf(net_clr, net_all),
            ),
            (
                ("sfc_net_lw_all_mon", "sfc_net_lw_clr_t_mon"),
                lambda net_all, net_clr: lwcfsrf(net_clr, net_all),
            ),
            (("sfc_cre_net_lw_mon",), rename),
            (("FLNS", "FLNSC"), lambda flns, flnsc: lwcfsrf(flns, flnsc)),
        ]
    ),
    "NETCF": OrderedDict(
        [
            (
                (
                    "toa_net_sw_all_mon",
                    "toa_net_sw_clr_mon",
                    "toa_net_lw_all_mon",
                    "toa_net_lw_clr_mon",
                ),
                lambda sw_all, sw_clr, lw_all, lw_clr: netcf4(
                    sw_all, sw_clr, lw_all, lw_clr
                ),
            ),
            (
                (
                    "toa_net_sw_all_mon",
                    "toa_net_sw_clr_t_mon",
                    "toa_net_lw_all_mon",
                    "toa_net_lw_clr_t_mon",
                ),
                lambda sw_all, sw_clr, lw_all, lw_clr: netcf4(
                    sw_all, sw_clr, lw_all, lw_clr
                ),
            ),
            (
                ("toa_cre_sw_mon", "toa_cre_lw_mon"),
                lambda swcf, lwcf: netcf2(swcf, lwcf),
            ),
            (("SWCF", "LWCF"), lambda swcf, lwcf: netcf2(swcf, lwcf)),
            (
                ("FSNTOA", "FSNTOAC", "FLNTOA", "FLNTOAC"),
                lambda fsntoa, fsntoac, flntoa, flntoac: netcf4(
                    fsntoa, fsntoac, flntoa, flntoac
                ),
            ),
        ]
    ),
    "NETCF_SRF": OrderedDict(
        [
            (
                (
                    "sfc_net_sw_all_mon",
                    "sfc_net_sw_clr_mon",
                    "sfc_net_lw_all_mon",
                    "sfc_net_lw_clr_mon",
                ),
                lambda sw_all, sw_clr, lw_all, lw_clr: netcf4srf(
                    sw_all, sw_clr, lw_all, lw_clr
                ),
            ),
            (
                (
                    "sfc_net_sw_all_mon",
                    "sfc_net_sw_clr_t_mon",
                    "sfc_net_lw_all_mon",
                    "sfc_net_lw_clr_t_mon",
                ),
                lambda sw_all, sw_clr, lw_all, lw_clr: netcf4srf(
                    sw_all, sw_clr, lw_all, lw_clr
                ),
            ),
            (
                ("sfc_cre_sw_mon", "sfc_cre_lw_mon"),
                lambda swcf, lwcf: netcf2srf(swcf, lwcf),
            ),
            (
                ("FSNS", "FSNSC", "FLNSC", "FLNS"),
                lambda fsns, fsnsc, flnsc, flns: netcf4srf(fsns, fsnsc, flnsc, flns),
            ),
        ]
    ),
    "FLNS": OrderedDict(
        [
            (
                ("sfc_net_lw_all_mon",),
                lambda sfc_net_lw_all_mon: -sfc_net_lw_all_mon,
            ),
            (("rlds", "rlus"), lambda rlds, rlus: netlw(rlds, rlus)),
        ]
    ),
    "FLNSC": OrderedDict(
        [
            (
                ("sfc_net_lw_clr_mon",),
                lambda sfc_net_lw_clr_mon: -sfc_net_lw_clr_mon,
            ),
            (
                ("sfc_net_lw_clr_t_mon",),
                lambda sfc_net_lw_clr_mon: -sfc_net_lw_clr_mon,
            ),
        ]
    ),
    "FLDS": OrderedDict([(("rlds",), rename)]),
    "FLUS": OrderedDict(
        [
            (("rlus",), rename),
            (("FLDS", "FLNS"), lambda FLDS, FLNS: flus(FLDS, FLNS)),
        ]
    ),
    "FLDSC": OrderedDict(
        [
            (("rldscs",), rename),
            (("TS", "FLNSC"), lambda ts, flnsc: fldsc(ts, flnsc)),
        ]
    ),
    "FSNS": OrderedDict(
        [
            (("sfc_net_sw_all_mon",), rename),
            (("rsds", "rsus"), lambda rsds, rsus: netsw(rsds, rsus)),
        ]
    ),
    "FSNSC": OrderedDict(
        [
            (("sfc_net_sw_clr_mon",), rename),
            (("sfc_net_sw_clr_t_mon",), rename),
        ]
    ),
    "FSDS": OrderedDict([(("rsds",), rename)]),
    "FSUS": OrderedDict(
        [
            (("rsus",), rename),
            (("FSDS", "FSNS"), lambda FSDS, FSNS: fsus(FSDS, FSNS)),
        ]
    ),
    "FSUSC": OrderedDict([(("rsuscs",), rename)]),
    "FSDSC": OrderedDict([(("rsdscs",), rename), (("rsdsc",), rename)]),
    # Net surface heat flux: W/(m^2)
    "NET_FLUX_SRF": OrderedDict(
        [
            # A more precise formula to close atmospheric surface budget, than the second entry.
            (
                ("FSNS", "FLNS", "QFLX", "PRECC", "PRECL", "PRECSC", "PRECSL", "SHFLX"),
                lambda fsns, flns, qflx, precc, precl, precsc, precsl, shflx: netflux4(
                    fsns,
                    flns,
                    qflx_convert_to_lhflx(qflx, precc, precl, precsc, precsl),
                    shflx,
                ),
            ),
            (
                ("FSNS", "FLNS", "LHFLX", "SHFLX"),
                lambda fsns, flns, lhflx, shflx: netflux4(fsns, flns, lhflx, shflx),
            ),
            (
                ("FSNS", "FLNS", "QFLX", "SHFLX"),
                lambda fsns, flns, qflx, shflx: netflux4(
                    fsns, flns, qflx_convert_to_lhflx_approxi(qflx), shflx
                ),
            ),
            (
                ("rsds", "rsus", "rlds", "rlus", "hfls", "hfss"),
                lambda rsds, rsus, rlds, rlus, hfls, hfss: netflux6(
                    rsds, rsus, rlds, rlus, hfls, hfss
                ),
            ),
        ]
    ),
    "FLUT": OrderedDict([(("rlut",), rename)]),
    "FSUTOA": OrderedDict([(("rsut",), rename)]),
    "FSUTOAC": OrderedDict([(("rsutcs",), rename)]),
    "FLNT": OrderedDict([(("FLNT",), rename)]),
    "FLUTC": OrderedDict([(("rlutcs",), rename)]),
    "FSNTOA": OrderedDict(
        [
            (("FSNTOA",), rename),
            (("rsdt", "rsut"), lambda rsdt, rsut: rst(rsdt, rsut)),
        ]
    ),
    "FSNTOAC": OrderedDict(
        [
            # Note: CERES_EBAF data in amwg obs sets misspells "units" as "lunits"
            (("FSNTOAC",), rename),
            (("rsdt", "rsutcs"), lambda rsdt, rsutcs: rstcs(rsdt, rsutcs)),
        ]
    ),
    "RESTOM": OrderedDict(
        [
            (("RESTOA",), rename),
            (("toa_net_all_mon",), rename),
            (("FSNT", "FLNT"), lambda fsnt, flnt: restom(fsnt, flnt)),
            (("rtmt",), rename),
        ]
    ),
    "RESTOA": OrderedDict(
        [
            (("RESTOM",), rename),
            (("toa_net_all_mon",), rename),
            (("FSNT", "FLNT"), lambda fsnt, flnt: restoa(fsnt, flnt)),
            (("rtmt",), rename),
        ]
    ),
    #    'TREFHT_LAND': OrderedDict([
    #        (('TREFHT_LAND',), rename),
    #        (('TREFHT', 'LANDFRAC'), lambda trefht, landfrac: mask_by(
    #            convert_units(trefht, target_units="K"), landfrac, low_limit=0.65))
    #    ]),
    #    'TREFHT_LAND': OrderedDict([
    #        (('TREFHT_LAND',), lambda t: convert_units(rename(t), target_units="DegC")),
    #        (('tas',), lambda t: convert_units(t, target_units="DegC")), #special case for GHCN data provided by Jerry
    #        (('TREFHT', 'LANDFRAC'), lambda trefht, landfrac: mask_by(
    #            convert_units(trefht, target_units="DegC"), landfrac, low_limit=0.65))
    #    ]),
    "PRECT_LAND": OrderedDict(
        [
            (("PRECIP_LAND",), rename),
            # 0.5 just to match amwg
            (
                ("PRECC", "PRECL", "LANDFRAC"),
                lambda precc, precl, landfrac: mask_by(
                    prect(precc, precl), landfrac, low_limit=0.5
                ),
            ),
        ]
    ),
    "Z3": OrderedDict(
        [
            (
                ("zg",),
                lambda zg: convert_units(rename(zg), target_units="hectometer"),
            ),
            (("Z3",), lambda z3: convert_units(z3, target_units="hectometer")),
        ]
    ),
    "PSL": OrderedDict(
        [
            (("PSL",), lambda psl: convert_units(psl, target_units="mbar")),
            (("psl",), lambda psl: convert_units(psl, target_units="mbar")),
        ]
    ),
    "T": OrderedDict(
        [
            (("ta",), rename),
            (("T",), lambda t: convert_units(t, target_units="K")),
        ]
    ),
    "U": OrderedDict(
        [
            (("ua",), rename),
            (("U",), lambda u: convert_units(u, target_units="m/s")),
        ]
    ),
    "V": OrderedDict(
        [
            (("va",), rename),
            (("V",), lambda u: convert_units(u, target_units="m/s")),
        ]
    ),
    "TREFHT": OrderedDict(
        [
            (("TREFHT",), lambda t: convert_units(t, target_units="DegC")),
            (
                ("TREFHT_LAND",),
                lambda t: convert_units(t, target_units="DegC"),
            ),
            (("tas",), lambda t: convert_units(t, target_units="DegC")),
        ]
    ),
    # Surface water flux: kg/((m^2)*s)
    "QFLX": OrderedDict(
        [
            (("evspsbl",), rename),
            (("QFLX",), lambda qflx: qflxconvert_units(qflx)),
        ]
    ),
    # Surface latent heat flux: W/(m^2)
    "LHFLX": OrderedDict(
        [
            (("hfls",), rename),
            (("QFLX",), lambda qflx: qflx_convert_to_lhflx_approxi(qflx)),
        ]
    ),
    "SHFLX": OrderedDict([(("hfss",), rename)]),
    "TGCLDLWP_OCN": OrderedDict(
        [
            (
                ("TGCLDLWP_OCEAN",),
                lambda x: convert_units(x, target_units="g/m^2"),
            ),
            (
                ("TGCLDLWP", "OCNFRAC"),
                lambda tgcldlwp, ocnfrac: mask_by(
                    convert_units(tgcldlwp, target_units="g/m^2"),
                    ocnfrac,
                    low_limit=0.65,
                ),
            ),
        ]
    ),
    "PRECT_OCN": OrderedDict(
        [
            (
                ("PRECT_OCEAN",),
                lambda x: convert_units(x, target_units="mm/day"),
            ),
            (
                ("PRECC", "PRECL", "OCNFRAC"),
                lambda a, b, ocnfrac: mask_by(
                    aplusb(a, b, target_units="mm/day"),
                    ocnfrac,
                    low_limit=0.65,
                ),
            ),
        ]
    ),
    "PREH2O_OCN": OrderedDict(
        [
            (("PREH2O_OCEAN",), lambda x: convert_units(x, target_units="mm")),
            (
                ("TMQ", "OCNFRAC"),
                lambda preh2o, ocnfrac: mask_by(preh2o, ocnfrac, low_limit=0.65),
            ),
        ]
    ),
    "CLDHGH": OrderedDict(
        [(("CLDHGH",), lambda cldhgh: convert_units(cldhgh, target_units="%"))]
    ),
    "CLDLOW": OrderedDict(
        [(("CLDLOW",), lambda cldlow: convert_units(cldlow, target_units="%"))]
    ),
    "CLDMED": OrderedDict(
        [(("CLDMED",), lambda cldmed: convert_units(cldmed, target_units="%"))]
    ),
    "CLDTOT": OrderedDict(
        [
            (("clt",), rename),
            (
                ("CLDTOT",),
                lambda cldtot: convert_units(cldtot, target_units="%"),
            ),
        ]
    ),
    "CLOUD": OrderedDict(
        [
            (("cl",), rename),
            (
                ("CLOUD",),
                lambda cldtot: convert_units(cldtot, target_units="%"),
            ),
        ]
    ),
    # below for COSP output
    # CLIPSO
    "CLDHGH_CAL": OrderedDict(
        [
            (
                ("CLDHGH_CAL",),
                lambda cldhgh: convert_units(cldhgh, target_units="%"),
            )
        ]
    ),
    "CLDLOW_CAL": OrderedDict(
        [
            (
                ("CLDLOW_CAL",),
                lambda cldlow: convert_units(cldlow, target_units="%"),
            )
        ]
    ),
    "CLDMED_CAL": OrderedDict(
        [
            (
                ("CLDMED_CAL",),
                lambda cldmed: convert_units(cldmed, target_units="%"),
            )
        ]
    ),
    "CLDTOT_CAL": OrderedDict(
        [
            (
                ("CLDTOT_CAL",),
                lambda cldtot: convert_units(cldtot, target_units="%"),
            )
        ]
    ),
    # ISCCP
    "CLDTOT_TAU1.3_ISCCP": OrderedDict(
        [
            (
                ("FISCCP1_COSP",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, None, None, 1.3, None), target_units="%"
                ),
            ),
            (
                ("CLISCCP",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, None, None, 1.3, None), target_units="%"
                ),
            ),
        ]
    ),
    "CLDTOT_TAU1.3_9.4_ISCCP": OrderedDict(
        [
            (
                ("FISCCP1_COSP",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, None, None, 1.3, 9.4), target_units="%"
                ),
            ),
            (
                ("CLISCCP",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, None, None, 1.3, 9.4), target_units="%"
                ),
            ),
        ]
    ),
    "CLDTOT_TAU9.4_ISCCP": OrderedDict(
        [
            (
                ("FISCCP1_COSP",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, None, None, 9.4, None), target_units="%"
                ),
            ),
            (
                ("CLISCCP",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, None, None, 9.4, None), target_units="%"
                ),
            ),
        ]
    ),
    # MODIS
    "CLDTOT_TAU1.3_MODIS": OrderedDict(
        [
            (
                ("CLMODIS",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, None, None, 1.3, None), target_units="%"
                ),
            ),
        ]
    ),
    "CLDTOT_TAU1.3_9.4_MODIS": OrderedDict(
        [
            (
                ("CLMODIS",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, None, None, 1.3, 9.4), target_units="%"
                ),
            ),
        ]
    ),
    "CLDTOT_TAU9.4_MODIS": OrderedDict(
        [
            (
                ("CLMODIS",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, None, None, 9.4, None), target_units="%"
                ),
            ),
        ]
    ),
    "CLDHGH_TAU1.3_MODIS": OrderedDict(
        [
            (
                ("CLMODIS",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, 440, 0, 1.3, None), target_units="%"
                ),
            ),
        ]
    ),
    "CLDHGH_TAU1.3_9.4_MODIS": OrderedDict(
        [
            (
                ("CLMODIS",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, 440, 0, 1.3, 9.4), target_units="%"
                ),
            ),
        ]
    ),
    "CLDHGH_TAU9.4_MODIS": OrderedDict(
        [
            (
                ("CLMODIS",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, 440, 0, 9.4, None), target_units="%"
                ),
            ),
        ]
    ),
    # MISR
    "CLDTOT_TAU1.3_MISR": OrderedDict(
        [
            (
                ("CLD_MISR",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, None, None, 1.3, None), target_units="%"
                ),
            ),
            (
                ("CLMISR",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, None, None, 1.3, None), target_units="%"
                ),
            ),
        ]
    ),
    "CLDTOT_TAU1.3_9.4_MISR": OrderedDict(
        [
            (
                ("CLD_MISR",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, None, None, 1.3, 9.4), target_units="%"
                ),
            ),
            (
                ("CLMISR",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, None, None, 1.3, 9.4), target_units="%"
                ),
            ),
        ]
    ),
    "CLDTOT_TAU9.4_MISR": OrderedDict(
        [
            (
                ("CLD_MISR",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, None, None, 9.4, None), target_units="%"
                ),
            ),
            (
                ("CLMISR",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, None, None, 9.4, None), target_units="%"
                ),
            ),
        ]
    ),
    "CLDLOW_TAU1.3_MISR": OrderedDict(
        [
            (
                ("CLD_MISR",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, 0, 3, 1.3, None), target_units="%"
                ),
            ),
            (
                ("CLMISR",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, 0, 3, 1.3, None), target_units="%"
                ),
            ),
        ]
    ),
    "CLDLOW_TAU1.3_9.4_MISR": OrderedDict(
        [
            (
                ("CLD_MISR",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, 0, 3, 1.3, 9.4), target_units="%"
                ),
            ),
            (
                ("CLMISR",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, 0, 3, 1.3, 9.4), target_units="%"
                ),
            ),
        ]
    ),
    "CLDLOW_TAU9.4_MISR": OrderedDict(
        [
            (
                ("CLD_MISR",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, 0, 3, 9.4, None), target_units="%"
                ),
            ),
            (
                ("CLMISR",),
                lambda cld: convert_units(
                    cosp_bin_sum(cld, 0, 3, 9.4, None), target_units="%"
                ),
            ),
        ]
    ),
    # COSP cloud fraction joint histogram
    "COSP_HISTOGRAM_MISR": OrderedDict(
        [
            (
                ("CLD_MISR",),
                lambda cld: cosp_histogram_standardize(rename(cld)),
            ),
            (("CLMISR",), lambda cld: cosp_histogram_standardize(rename(cld))),
        ]
    ),
    "COSP_HISTOGRAM_MODIS": OrderedDict(
        [
            (
                ("CLMODIS",),
                lambda cld: cosp_histogram_standardize(rename(cld)),
            ),
        ]
    ),
    "COSP_HISTOGRAM_ISCCP": OrderedDict(
        [
            (
                ("FISCCP1_COSP",),
                lambda cld: cosp_histogram_standardize(rename(cld)),
            ),
            (
                ("CLISCCP",),
                lambda cld: cosp_histogram_standardize(rename(cld)),
            ),
        ]
    ),
    "ICEFRAC": OrderedDict(
        [
            (
                ("ICEFRAC",),
                lambda icefrac: convert_units(icefrac, target_units="%"),
            )
        ]
    ),
    "RELHUM": OrderedDict(
        [
            (("hur",), lambda hur: convert_units(hur, target_units="%")),
            (
                ("RELHUM",),
                lambda relhum: convert_units(relhum, target_units="%"),
            )
            # (('RELHUM',), rename)
        ]
    ),
    "OMEGA": OrderedDict(
        [
            (
                ("wap",),
                lambda wap: convert_units(wap, target_units="mbar/day"),
            ),
            (
                ("OMEGA",),
                lambda omega: convert_units(omega, target_units="mbar/day"),
            ),
        ]
    ),
    "Q": OrderedDict(
        [
            (
                ("hus",),
                lambda q: convert_units(rename(q), target_units="g/kg"),
            ),
            (("Q",), lambda q: convert_units(rename(q), target_units="g/kg")),
            (("SHUM",), lambda shum: convert_units(shum, target_units="g/kg")),
        ]
    ),
    "TAUXY": OrderedDict(
        [
            (("TAUX", "TAUY"), lambda taux, tauy: tauxy(taux, tauy)),
            (("tauu", "tauv"), lambda taux, tauy: tauxy(taux, tauy)),
        ]
    ),
    "AODVIS": OrderedDict(
        [
            (("od550aer",), rename),
            (
                ("AODVIS",),
                lambda aod: convert_units(rename(aod), target_units="dimensionless"),
            ),
            (
                ("AOD_550_ann",),
                lambda aod: convert_units(rename(aod), target_units="dimensionless"),
            ),
        ]
    ),
    "AODABS": OrderedDict([(("abs550aer",), rename)]),
    # Surface temperature: Degrees C
    # (Temperature of the surface (land/water) itself, not the air)
    "TS": OrderedDict([(("ts",), rename)]),
    "PS": OrderedDict([(("ps",), rename)]),
    "U10": OrderedDict([(("sfcWind",), rename)]),
    "QREFHT": OrderedDict([(("huss",), rename)]),
    "PRECC": OrderedDict([(("prc",), rename)]),
    "TAUX": OrderedDict([(("tauu",), lambda tauu: -tauu)]),
    "TAUY": OrderedDict([(("tauv",), lambda tauv: -tauv)]),
    "CLDICE": OrderedDict([(("cli",), rename)]),
    "TGCLDIWP": OrderedDict([(("clivi",), rename)]),
    "CLDLIQ": OrderedDict([(("clw",), rename)]),
    "TGCLDCWP": OrderedDict([(("clwvi",), rename)]),
    "O3": OrderedDict([(("o3",), rename)]),
    "PminusE": OrderedDict(
        [
            (("PminusE",), lambda pminuse: pminuse_convert_units(pminuse)),
            (
                (
                    "PRECC",
                    "PRECL",
                    "QFLX",
                ),
                lambda precc, precl, qflx: pminuse_convert_units(
                    prect(precc, precl) - pminuse_convert_units(qflx)
                ),
            ),
            (
                ("F_prec", "F_evap"),
                lambda pr, evspsbl: pminuse_convert_units(pr + evspsbl),
            ),
            (
                ("pr", "evspsbl"),
                lambda pr, evspsbl: pminuse_convert_units(pr - evspsbl),
            ),
        ]
    ),
    "TREFMNAV": OrderedDict(
        [
            (("TREFMNAV",), lambda t: convert_units(t, target_units="DegC")),
            (("tasmin",), lambda t: convert_units(t, target_units="DegC")),
        ]
    ),
    "TREFMXAV": OrderedDict(
        [
            (("TREFMXAV",), lambda t: convert_units(t, target_units="DegC")),
            (("tasmax",), lambda t: convert_units(t, target_units="DegC")),
        ]
    ),
    "TREF_range": OrderedDict(
        [
            (("TREFMXAV", "TREFMNAV"), lambda tmax, tmin: tref_range(tmax, tmin)),
            (("tasmax", "tasmin"), lambda tmax, tmin: tref_range(tmax, tmin)),
        ]
    ),
    "TCO": OrderedDict([(("TCO",), rename)]),
    "SCO": OrderedDict([(("SCO",), rename)]),
    # Land variables
    "SOILWATER_10CM": OrderedDict([(("mrsos",), rename)]),
    "SOILWATER_SUM": OrderedDict([(("mrso",), rename)]),
    "SOILICE_SUM": OrderedDict([(("mrfso",), rename)]),
    "QOVER": OrderedDict([(("mrros",), rename)]),
    "QRUNOFF": OrderedDict(
        [
            (("QRUNOFF",), lambda qrunoff: qflxconvert_units(qrunoff)),
            (("mrro",), rename),
        ]
    ),
    "QINTR": OrderedDict([(("prveg",), rename)]),
    "QVEGE": OrderedDict([(("evspsblveg",), rename)]),
    "QSOIL": OrderedDict([(("evspsblsoi",), rename)]),
    "TRAN": OrderedDict([(("tran",), rename)]),
    "TSOI": OrderedDict([(("tsl",), rename)]),
    "LAI": OrderedDict([(("lai",), rename)]),
    # Ocean variables
    "tauuo": OrderedDict([(("tauuo",), rename)]),
    "tos": OrderedDict([(("tos",), rename)]),
    "thetaoga": OrderedDict([(("thetaoga",), rename)]),
    "hfsifrazil": OrderedDict([(("hfsifrazil",), rename)]),
    "sos": OrderedDict([(("sos",), rename)]),
    "soga": OrderedDict([(("soga",), rename)]),
    "tosga": OrderedDict([(("tosga",), rename)]),
    "wo": OrderedDict([(("wo",), rename)]),
    "thetao": OrderedDict([(("thetao",), rename)]),
    "masscello": OrderedDict([(("masscello",), rename)]),
    "wfo": OrderedDict([(("wfo",), rename)]),
    "tauvo": OrderedDict([(("tauvo",), rename)]),
    "vo": OrderedDict([(("vo",), rename)]),
    "hfds": OrderedDict([(("hfds",), rename)]),
    "volo": OrderedDict([(("volo",), rename)]),
    "uo": OrderedDict([(("uo",), rename)]),
    "zos": OrderedDict([(("zos",), rename)]),
    "tob": OrderedDict([(("tob",), rename)]),
    "sosga": OrderedDict([(("sosga",), rename)]),
    "sfdsi": OrderedDict([(("sfdsi",), rename)]),
    "zhalfo": OrderedDict([(("zhalfo",), rename)]),
    "masso": OrderedDict([(("masso",), rename)]),
    "so": OrderedDict([(("so",), rename)]),
    "sob": OrderedDict([(("sob",), rename)]),
    "mlotst": OrderedDict([(("mlotst",), rename)]),
    "fsitherm": OrderedDict([(("fsitherm",), rename)]),
    "msftmz": OrderedDict([(("msftmz",), rename)]),
    # sea ice variables
    "sitimefrac": OrderedDict([(("sitimefrac",), rename)]),
    "siconc": OrderedDict([(("siconc",), rename)]),
    "sisnmass": OrderedDict([(("sisnmass",), rename)]),
    "sisnthick": OrderedDict([(("sisnthick",), rename)]),
    "simass": OrderedDict([(("simass",), rename)]),
    "sithick": OrderedDict([(("sithick",), rename)]),
    "siu": OrderedDict([(("siu",), rename)]),
    "sitemptop": OrderedDict([(("sitemptop",), rename)]),
    "siv": OrderedDict([(("siv",), rename)]),
}
