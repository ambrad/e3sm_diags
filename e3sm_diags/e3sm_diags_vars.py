#!/usr/bin/env python
"""
What variables in the passed in file can have E3SM Diagnostics ran on them?
Pass in an E3SM model output file.
It's assumed that this file will have all of the E3SM variables in it.
This is used to get the correct variable names from the derived variables dictionary.
"""
import glob
import os
from typing import Any, Dict, List

import cdms2

import e3sm_diags
from e3sm_diags.derivations.acme import derived_variables
from e3sm_diags.e3sm_diags_driver import get_parameters
from e3sm_diags.logger import custom_logger
from e3sm_diags.parser.core_parser import CoreParser

logger = custom_logger(__name__)


def main():
    vars_in_e3sm_diags = list_of_vars_in_e3sm_diags()
    vars_with_derived_vars = sorted(check_for_derived_vars(vars_in_e3sm_diags))
    logger.info(
        "Below are the variables needed to run all of the diagnostics in e3sm_diags."
    )
    logger.info(
        "NOTE: This list doesn't include auxiliary variables such as hyam, hybm, PS, etc."
    )
    logger.info(vars_with_derived_vars)


def list_of_vars_in_user_file():
    """
    Given a path to an nc file, return all of the variables in it.
    """
    # parser = argparse.ArgumentParser()
    # parser.add_argument("path")
    # path = parser.parse_args().path
    # path = DUMMY_FILE_PATH
    path = parser.parse_args().path
    logger.info("Using the file: {}".format(path))

    if not os.path.exists(path):
        msg = "The file ({}) does not exist.".format(path)
        raise RuntimeError(msg)
    with cdms2.open(path) as f:
        return f.variables.keys()


parser = CoreParser()


def list_of_vars_in_e3sm_diags():
    """
    Get a list of all of the variables used in e3sm_diags.
    Open all of the *.cfg files located in e3sm_diags/e3sm_diags/driver/default_diags/
    and get all of the 'variables' parameters.
    """

    # Get all of the 'variables' parameter from each file.
    vars_used = []
    try:
        logger.info("Using user arguments.")
        parameters = get_parameters(parser)
    except Exception as e:
        logger.error(e)
        # Looks for these files in their installed location.
        pth = os.path.join(e3sm_diags.INSTALL_PATH)
        # The first '*' is the folder of the set, the second is the actual file.
        # Ex: {e3sm_diags.INSTALL_PATH}/lat_lon/lat_lon_model_vs_obs.cfg
        file_paths = [p for p in glob.glob(pth + "*/*.cfg")]
        # NOT NEEDED:
        # parser.add_argument('path')  # Needed so the filename can be passed in.
        # parser.add_args_and_values([DUMMY_FILE_PATH])
        parameters = parser.get_other_parameters(
            files_to_open=file_paths, check_values=False
        )

    for p in parameters:
        logger.info(f"p.variables {p.variables}")
        vars_used.extend(p.variables)

    logger.info(f"Variables used: {sorted(list(set(vars_used)))}")
    return set(vars_used)


def check_for_derived_vars(e3sm_vars: Dict[Any, Any]):
    """
    For any of the e3sm_vars which are derived variables, we need
    to check whether any of the original variables are actually in the user's file.

    Ex:
    'PRECT' is a variable in e3sm_vars.
    But it maps to both ('pr',) and ('PRECC', 'PRECL').
    Which one do we use?

    Given a path to a file, we get the vars in that file and
    decided whether to use ('pr',) or ('PRECC', 'PRECL').
    """
    vars_used = []  # type: List[Any]
    vars_in_user_file = set(list_of_vars_in_user_file())
    for var in e3sm_vars:
        if var in derived_variables:
            # Ex: {('PRECC', 'PRECL'): func, ('pr',): func1, ...}.
            vars_to_func_dict = derived_variables[var]
            # Ex: [('pr',), ('PRECC', 'PRECL')].
            possible_vars = vars_to_func_dict.keys()  # type: ignore

            var_added = False
            for list_of_vars in possible_vars:
                if not var_added and vars_in_user_file.issuperset(list_of_vars):
                    # All of the variables (list_of_vars) are in the input file.
                    # These are needed.
                    vars_used.extend(list_of_vars)
                    var_added = True
            # If none of the original vars are in the file, just keep this var.
            # This means that it isn't a derived variable in E3SM.
            if not var_added:
                vars_used.append(var)

        else:
            # This var is not a derived variable, it's okay.
            vars_used.append(var)

    return list(set(vars_used))


if __name__ == "__main__":
    main()
