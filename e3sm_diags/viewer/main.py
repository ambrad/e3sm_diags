import collections
import os

from bs4 import BeautifulSoup

import e3sm_diags
from e3sm_diags.logger import custom_logger

from . import (
    annual_cycle_zonal_mean_viewer,
    area_mean_time_series_viewer,
    arm_diags_viewer,
    default_viewer,
    enso_diags_viewer,
    mean_2d_viewer,
    qbo_viewer,
    streamflow_viewer,
    tc_analysis_viewer,
    utils,
)

logger = custom_logger(__name__)

# A mapping of each diagnostics set to the viewer
# that handles creating of the HTML pages.
SET_TO_VIEWER = {
    "lat_lon": default_viewer.create_viewer,
    "polar": default_viewer.create_viewer,
    "zonal_mean_xy": default_viewer.create_viewer,
    "zonal_mean_2d": mean_2d_viewer.create_viewer,
    "zonal_mean_2d_stratosphere": mean_2d_viewer.create_viewer,
    "meridional_mean_2d": mean_2d_viewer.create_viewer,
    "cosp_histogram": default_viewer.create_viewer,
    "area_mean_time_series": area_mean_time_series_viewer.create_viewer,
    "enso_diags": enso_diags_viewer.create_viewer,
    "qbo": qbo_viewer.create_viewer,
    "streamflow": streamflow_viewer.create_viewer,
    "diurnal_cycle": default_viewer.create_viewer,
    "arm_diags": arm_diags_viewer.create_viewer,
    "tc_analysis": tc_analysis_viewer.create_viewer,
    "annual_cycle_zonal_mean": annual_cycle_zonal_mean_viewer.create_viewer,
}


def create_index(root_dir, title_and_url_list):
    """
    Creates the index page in root_dir which
    joins the individual viewers.
    The elements in title_and_url_list can either be:
      - A (title, url) tuple.
      - A list of the above tuples.

    Each element that is a tuple is on its own row.
    Elements that are a list are on a single row.
      - Ex: 'Latitude-Longitude contour maps', 'Table',
        and 'Taylor Diagram' are all on a single line.
    """

    def insert_data_in_row(row_obj, name, url):
        """
        Given a row object, insert the name and url.
        """
        td = soup.new_tag("td")
        a = soup.new_tag("a")
        a["href"] = url
        a.string = name
        td.append(a)
        row_obj.append(td)

    path = os.path.join(e3sm_diags.INSTALL_PATH, "viewer", "index_template.html")
    output = os.path.join(root_dir, "index.html")

    soup = BeautifulSoup(open(path), "lxml")

    # If no one changes it, the template only has
    # one element in the find command below.
    table = soup.find_all("table", {"class": "table"})[0]

    # Adding the title.
    tr = soup.new_tag("tr")
    th = soup.new_tag("th")
    th.string = "Output Sets"
    tr.append(th)

    # Adding each of the rows.
    for row in title_and_url_list:
        tr = soup.new_tag("tr")

        if isinstance(row, list):
            for elt in row:
                name, url = elt
                insert_data_in_row(tr, name, url)
        else:
            name, url = row
            insert_data_in_row(tr, name, url)

        table.append(tr)

    html = soup.prettify("utf-8")

    with open(output, "wb") as f:
        f.write(html)

    return output


def create_viewer(root_dir, parameters):
    """
    Based of the parameters, find the files with the
    certain extension and create the viewer in root_dir.
    """
    # Group each parameter object based on the `sets` parameter.
    set_to_parameters = collections.defaultdict(list)
    for param in parameters:
        for set_name in param.sets:
            set_to_parameters[set_name].append(param)

    # A list of (title, url) tuples that each viewer generates.
    # This is used to create the main index.
    title_and_url_list = []
    # Now call the viewers with the list of parameters as the arguments.
    for set_name, parameters in set_to_parameters.items():
        logger.info(f"{set_name} {root_dir}")
        viewer_function = SET_TO_VIEWER[set_name]
        result = viewer_function(root_dir, parameters)
        logger.info(result)
        title_and_url_list.append(result)

    # Add the provenance in the index as well.
    prov_tuple = ("Provenance", "../prov")
    title_and_url_list.append(prov_tuple)

    index_url = create_index(root_dir, title_and_url_list)
    utils.add_header(root_dir, index_url, parameters)

    return index_url
