import tkinter as tk
from tkinter import ttk
import math
import sys
import threading
import openpyxl
import shutil
from PIL import ImageTk, Image
import numpy
import utils
import tkinter.font
import acoustics
import csv
import BarrierPlotExporter
from collections import defaultdict

BED_IMAGE_FILEPATH = "bed_image.png"
XL_FILEPATH = "WCV - PL - 2025.04.06.xlsm"
SHEET_NAME = "Input LwA_XYZ"
XL_TEMP_FILEPATH = "_temp.xlsm"
XL_FILEPATH_SAVE = XL_FILEPATH[0:-5] + " - exported.xlsm"
DRAWING_FONT = "Helvetica 12 bold"
GRID_FONT = "Helvetica 16 bold"
GRID_DEFAULT_ELEV_SPACE = "0,25"
GRID_DEFAULT_METRIC = "NC"
GRID_DEFAULT_SIZE = (1000, 1000)
BAR_IL_FONT = "Helvetica 14"

# setting columns
shutil.copyfile(XL_FILEPATH, XL_TEMP_FILEPATH)
wb = openpyxl.load_workbook(XL_TEMP_FILEPATH, data_only=True)
ws = wb[SHEET_NAME]
ws_tl = wb["TL"]
EQMT_COUNT = ws["A"]
EQMT_TAG = ws["B"]
PATH = ws["C"]
MAKE = ws["D"]
MODEL = ws["E"]
HZ63 = ws["F"]
HZ125 = ws["G"]
HZ250 = ws["H"]
HZ500 = ws["I"]
HZ1000 = ws["J"]
HZ2000 = ws["K"]
HZ4000 = ws["L"]
HZ8000 = ws["M"]
SOUND_LEVEL = ws["N"]
SOUND_REF_DIST = ws["O"]
TESTED_Q = ws["P"]
INSTALLED_Q = ws["R"]
EQMT_INSERTION_LOSS = ws["S"]
EQMT_X_COORD = ws["T"]
EQMT_Y_COORD = ws["U"]
EQMT_Z_COORD = ws["V"]

# RCVRS
R_NAME = ws["Z"]
REC_X_COORD = ws["AA"]
REC_Y_COORD = ws["AB"]
REC_Z_COORD = ws["AC"]
SOUND_LIMIT = ws["AD"]

# BARRIERS
BARRIER_NAME = ws["Z"]
BAR_X0_COORD = ws["AA"]
BAR_Y0_COORD = ws["AB"]
BAR_Z0_COORD = ws["AC"]
BAR_X1_COORD = ws["AD"]
BAR_Y1_COORD = ws["AE"]
BAR_Z1_COORD = ws["AF"]

# SCALING
KNOWN_DISTANCE_FT_CELL = ws["AE20"]
SCALE_LINE_DISTANCE_PX_CELL = ws["AF20"]

# IMAGE HEIGHT FOR 3D VIEW
IMAGE_HEIGHT_3D_VIEW = ws["AF21"].value

# BAR BOOLS
USE_SPECIFIC_BAR_BOOL      = ws["AC19"].value
TAKE_ARI_BARRIER           = ws["AC20"].value
TAKE_OB_FRESNAL_BARRIER    = ws["AC21"].value
if not isinstance(USE_SPECIFIC_BAR_BOOL, bool):
    raise TypeError("USE_SPECIFIC_BAR must be TRUE or FALSE")
if not isinstance(TAKE_ARI_BARRIER, bool):
    raise TypeError("TAKE_ARI_BAR must be TRUE or FALSE")
if not isinstance(TAKE_OB_FRESNAL_BARRIER, bool):
    raise TypeError("TAKE_OB_FRESNEL_BAR must be TRUE or FALSE")

# ROW/COLs for MATRICES
IGNORE_MATRIX_COL = 108  # 1-index based
IGNORE_MATRIX_ROW = 2  # 1-index based
DIRECTIVITY_MATRIX_COL = 125  # 1-index based
DIRECTIVITY_MATRIX_ROW = 2  # 1-index based
SPECIFIC_BAR_MATRIX_COL = 91  # 1-index based
SPECIFIC_BAR_MATRIX_ROW = 2  # 1-index based

# ROW/COLs for TL MATRICES
ROOF_ASSEMBLY_COL = 2 # 1-index based
ROOF_ASSEMBLY_ROW = 3 # 1-index based

# ROW/COL VALUES FOR Export List Button
EQMT_NAME_COL = 1
EQMT_X_COORD_COL = 19
EQMT_Y_COORD_COL = 20

RCVR_NAME_COL = 25
RCVR_X_COORD_COL = 26
RCVR_Y_COORD_COL = 27

BAR_NAME_COL = 25
BAR_START_ROW = 24  # 1-index based
BAR_X0_COORD_COL = 26
BAR_Y0_COORD_COL = 27
BAR_Z0_COORD_COL = 28
BAR_X1_COORD_COL = 29
BAR_Y1_COORD_COL = 30
BAR_Z1_COORD_COL = 31

BAR_IL_COL_RANGE = range(73, 88)



OCTAVE_BAND_HZ = [63, 125, 250, 500, 1000, 2000, 4000, 8000]

def RCLevel(levelsFrom63to8k_OB):
    """ RC should take 16Hz to 4kHz but I'm working with what I have. """
    ob = levelsFrom63to8k_OB
    # print(ob)
    hz500 = ob[3]
    hz1000 = ob[4]
    hz2000 = ob[5]
    rc = (hz500 + hz1000 + hz2000) / 3.0 # RC = avg 500, 1k, 2k
    rc_curve = [ rc + (5 * i) for i in range(4, -4, -1) ] # -5dB/octave slope from 1khz
    diff = [ max(0, ob_val - rc_val) for (ob_val, rc_val) in zip(ob, rc_curve)]
    rumbly = any( [ lvl > 5 for lvl in diff[:4]] ) # lvls @ <= 500Hz exceeds curve by greater than 5 dB
    hissy = any( [ lvl >= 3 for lvl in diff[4:]] ) # lvls @ >= 1kHz exceeds curve by greater than 3 dB
    classifier = []
    if rumbly is False and hissy is False:
        classifier.append("N")
    if rumbly is True:
        classifier.append("R")
    if hissy is True:
        classifier.append("H")
    classifier = "".join(classifier)
    # print(rc, classifier)
    return (rc, classifier)


NC_CURVES = {
    15: [47.0, 36.0, 29.0, 22.0, 17.0, 14.0, 12.0, 11.0],
    20: [51.0, 40.0, 33.0, 26.0, 22.0, 19.0, 17.0, 16.0],
    25: [54.0, 44.0, 37.0, 31.0, 27.0, 24.0, 22.0, 21.0],
    30: [57.0, 48.0, 41.0, 35.0, 31.0, 29.0, 28.0, 27.0],
    35: [60.0, 52.0, 45.0, 40.0, 36.0, 34.0, 33.0, 32.0],
    40: [64.0, 56.0, 50.0, 45.0, 41.0, 39.0, 38.0, 37.0],
    45: [67.0, 60.0, 54.0, 49.0, 46.0, 44.0, 43.0, 42.0],
    50: [71.0, 64.0, 58.0, 54.0, 51.0, 49.0, 48.0, 47.0],
    55: [74.0, 67.0, 62.0, 58.0, 56.0, 54.0, 53.0, 52.0],
    60: [77.0, 71.0, 67.0, 63.0, 61.0, 59.0, 58.0, 57.0],
    65: [80.0, 75.0, 71.0, 68.0, 66.0, 64.0, 63.0, 62.0],
    70: [83.0, 79.0, 75.0, 72.0, 71.0, 70.0, 69.0, 68.0],
}

def nc_curve(nc):
    return NC_CURVES.get(nc)

def nc(levels):
    """
    It returns the NC curve of `levels`. If `levels` is upper than NC-70
    returns '70+'.

    Parameter:

    levels: 1-D NumPy array containing values between 63 Hz and 8 kHz in octave
    bands.
    """
    nc_range = range(15, 71, 5)
    for nc_test in nc_range:
        curve = NC_CURVES.get(nc_test)
        if all([l <= c for l, c in zip(levels, curve)]):
            break
        if nc_test == 70:
            nc_test = "70+"
            break
    return nc_test  # pylint: disable=undefined-loop-variable

def NCLevel(levelsFrom63to8k_OB, controllingBand=False):
    """
    this works by getting the NC curve completely above all the input values and then subtracts. A better way may be to start at the bottom and work up.
    it tests which curve is closer, the upper or the lower, then used the appropriate helper function to interpolate
    """
    NC_high = nc(levelsFrom63to8k_OB)
    if NC_high == "70+":
        return "70+" if not controllingBand else "70+ (NA)"
    NC_low = NC_high - 5

    NC_high_curve = NC_CURVES.get(NC_high)
    NC_low_curve = NC_CURVES.get(NC_low)

    if all([x <= y for x, y in zip(levelsFrom63to8k_OB, NC_CURVES[15])]):
        if not controllingBand:
            return 15
        else:
            return "15 (NA)"

    if all([x == y for x, y in zip(levelsFrom63to8k_OB, NC_CURVES[NC_high])]):
        if not controllingBand:
            return NC_high
        else:
            return f"{NC_high} (NA)"

    which = "low"
    for i in range(len(NC_high_curve)):
        if (
            levelsFrom63to8k_OB[i] - NC_low_curve[i]
            > (NC_high_curve[i] - NC_low_curve[i]) / 2
        ):
            which = "high"

    if which == "high":
        return NCLevel_startFromUpperCurve(levelsFrom63to8k_OB, controllingBand)

    else:
        return NCLevel_startFromLowerCurve(levelsFrom63to8k_OB, controllingBand)

def NCLevel_startFromUpperCurve(levelsFrom63to8k_OB, controllingBand=False):
    """
    this works by getting the NC curve completely above all the input values and then subtracts.
    """
    NC_roundedUpRating = nc(levelsFrom63to8k_OB)
    NC_roundedUpCurve = NC_CURVES.get(NC_roundedUpRating)

    # NC_CurveLevel_Difference = NC_roundedUpCurve - levelsFrom63to8k_OB
    NC_CurveLevel_Difference = [
        nc - v
        for nc, v in zip(NC_roundedUpCurve, [round(x) for x in levelsFrom63to8k_OB])
    ]
    NC_shifted = NC_roundedUpRating - min(NC_CurveLevel_Difference)

    if not controllingBand:
        return int(NC_shifted)
    else:
        controllingBand_idx = NC_CurveLevel_Difference.index(
            min(NC_CurveLevel_Difference)
        )
        return f" {int(NC_shifted)} ({OCTAVE_BAND_HZ[controllingBand_idx]}Hz)"


def NCLevel_startFromLowerCurve(levelsFrom63to8k_OB, controllingBand=False):
    """
    this works by getting the NC curve completely below all the input values and then adds.
    """
    NC_roundedUpRating = (
        nc(levelsFrom63to8k_OB) - 5
    )  # this -5 is what makes it start from the lower curve
    NC_roundedUpCurve = NC_CURVES.get(NC_roundedUpRating)

    # NC_CurveLevel_Difference = NC_roundedUpCurve - levelsFrom63to8k_OB
    NC_CurveLevel_Difference = [
        nc - v
        for nc, v in zip(NC_roundedUpCurve, [round(x) for x in levelsFrom63to8k_OB])
    ]
    NC_shifted = NC_roundedUpRating - min(NC_CurveLevel_Difference)

    if not controllingBand:
        return int(NC_shifted)
    else:
        controllingBand_idx = NC_CurveLevel_Difference.index(
            min(NC_CurveLevel_Difference)
        )
        return f" {int(NC_shifted)} ({OCTAVE_BAND_HZ[controllingBand_idx]}Hz)"

class FuncVars(object):
    def __init__(self, parent):
        self.parent = parent
        seen_tag_strs = set()
        seen_receiver_strs = set()
        seen_barriers_strs = set()

        # initialize eqmt list
        self.equipment_list = list()
        for (
            count,
            eqmt_tag,
            path,
            make,
            model,
            sound_level,
            sound_ref_dist,
            tested_q,
            installed_q,
            insertion_loss,
            x_coord,
            y_coord,
            z_coord,
            hz63,
            hz125,
            hz250,
            hz500,
            hz1000,
            hz2000,
            hz4000,
            hz8000,
        ) in zip(
            EQMT_COUNT,
            EQMT_TAG,
            PATH,
            MAKE,
            MODEL,
            SOUND_LEVEL,
            SOUND_REF_DIST,
            TESTED_Q,
            INSTALLED_Q,
            EQMT_INSERTION_LOSS,
            EQMT_X_COORD,
            EQMT_Y_COORD,
            EQMT_Z_COORD,
            HZ63,
            HZ125,
            HZ250,
            HZ500,
            HZ1000,
            HZ2000,
            HZ4000,
            HZ8000,
        ):
            if count.value == "Number of Units":
                continue
            if count.value == None:
                break
            if eqmt_tag.value is None:
                raise NameError(f"BLANK EQMT_TAG: {eqmt_tag.value}")
            if str(eqmt_tag.value) in seen_tag_strs:
                raise NameError(f"DUPLICATE_TAG_NAMES: {eqmt_tag.value}")
            seen_tag_strs.add(str(eqmt_tag.value))

            self.equipment_list.append(
                Equipment(
                    count.value,
                    str(eqmt_tag.value),
                    path.value,
                    make.value,
                    model.value,
                    sound_level.value,
                    sound_ref_dist.value,
                    tested_q.value,
                    installed_q.value,
                    insertion_loss.value,
                    x_coord.value,
                    y_coord.value,
                    z_coord.value,
                    hz63.value,
                    hz125.value,
                    hz250.value,
                    hz500.value,
                    hz1000.value,
                    hz2000.value,
                    hz4000.value,
                    hz8000.value,
                )
            )

        # initialize rcvr list
        self.receiver_list = list()
        for r_name, x_coord, y_coord, z_coord, sound_limit in zip(
            R_NAME, REC_X_COORD, REC_Y_COORD, REC_Z_COORD, SOUND_LIMIT
        ):
            if r_name.value == "R#":
                continue
            if r_name.value == None:
                break
            if str(r_name.value) in seen_receiver_strs:
                raise NameError(f"DUPLICATE_RCVR_NAME: {r_name.value}")
            seen_receiver_strs.add(str(r_name.value))

            self.receiver_list.append(
                Receiver(
                    str(r_name.value),
                    x_coord.value,
                    y_coord.value,
                    z_coord.value,
                    sound_limit.value,
                    "NA",
                )
            )

        # initialize barrier list
        self.barrier_list = list()
        for (
            barrier_name,
            x0_coord,
            y0_coord,
            z0_coord,
            x1_coord,
            y1_coord,
            z1_coord,
        ) in zip(
            BARRIER_NAME,
            BAR_X0_COORD,
            BAR_Y0_COORD,
            BAR_Z0_COORD,
            BAR_X1_COORD,
            BAR_Y1_COORD,
            BAR_Z1_COORD,
        ):
            if int(barrier_name.coordinate[1:]) < 24:
                continue
            if barrier_name.value == None:
                break
            if str(barrier_name.value) in seen_barriers_strs:
                raise NameError(f"DUPLICATE_BARRIER_NAME: {barrier_name.value}")
            seen_barriers_strs.add(str(barrier_name.value))

            self.barrier_list.append(
                Barrier(
                    str(barrier_name.value),
                    x0_coord.value,
                    y0_coord.value,
                    z0_coord.value,
                    x1_coord.value,
                    y1_coord.value,
                    z1_coord.value,
                )
            )

        # Grab roof assembly / TL details
        self.roof_assembly_dict = defaultdict(lambda: [0] * len(OCTAVE_BAND_HZ))
        self.roof_assembly_dict["None"] = [ 0 ] * len(OCTAVE_BAND_HZ)
        currow = ROOF_ASSEMBLY_ROW
        while ws_tl.cell(row=currow, column=ROOF_ASSEMBLY_COL).value is not None:
            assembly = ws_tl.cell(row=currow, column=ROOF_ASSEMBLY_COL).value
            tl = []
            for i in range(len(OCTAVE_BAND_HZ)):
                tl_cur_hz = ws_tl.cell(row=currow, column=ROOF_ASSEMBLY_COL + 1 + i).value
                if tl_cur_hz is None:
                    raise ValueError(
                        f"Missing TL value for roof assembly '{assembly}' "
                        f"at {OCTAVE_BAND_HZ[i]} Hz (row {currow})"
                    )
                tl.append(tl_cur_hz)
            self.roof_assembly_dict[assembly] = tl
            currow += 1

        try:
            self.selected_roof_assembly = list(self.roof_assembly_dict)[1]
        except IndexError:
            self.selected_roof_assembly = None

        self.grid_outline_coords = None
        self.grid_receiver_coords = []
        self.grid_receivers_on_canvas = []
        # for eqmt_to_rcvr_shapes drawing
        self.e_to_r_with_bar = dict()
        for eqmt in self.equipment_list:
            self.e_to_r_with_bar[eqmt] = dict()
            for rcvr in self.receiver_list:
                self.e_to_r_with_bar[eqmt][rcvr] = {"bar_obj": None, "bar_il": 0}

        def make_matrix(r: int, c: int, replace_none=None) -> list:
            matrix = list()
            for eqmt_row in range(len(self.equipment_list)):
                rcvrs_list = list()
                for rcvr_col in range(len(self.receiver_list)):
                    val = ws.cell(row=r + eqmt_row, column=c + rcvr_col).value
                    if val is None:
                        val = replace_none
                    rcvrs_list.append(val)
                matrix.append(rcvrs_list)
            return matrix

        self.ignore_matrix = make_matrix(IGNORE_MATRIX_ROW, IGNORE_MATRIX_COL)
        self.directivity_matrix = make_matrix(
            DIRECTIVITY_MATRIX_ROW, DIRECTIVITY_MATRIX_COL, replace_none=0
        )
        self.specific_bar_matrix = make_matrix(
            SPECIFIC_BAR_MATRIX_ROW, SPECIFIC_BAR_MATRIX_COL
        )
        for r in range(len(self.specific_bar_matrix)):
            for c in range(len(self.specific_bar_matrix[r])):
                s = self.specific_bar_matrix[r][c]
                if s is None:
                    continue
                s = s.split(", ")
                for (
                    i,
                    el,
                ) in enumerate(s):
                    s[i] = el.strip()
                    s[i] = el.replace(" ", "-")
                s = ", ".join(s)
                if s[-1] == ",":
                    s = s[:-1]
                self.specific_bar_matrix[r][c] = s

        # # initialize ignore matrix
        # c = IGNORE_MATRIX_COL # 1-index based
        # r = IGNORE_MATRIX_ROW
        # self.ignore_matrix = list()
        # for eqmt_row in range(len(self.equipment_list)):
        #     ignore_rcvrs_list = list()
        #     for rcvr_col in range(len(self.receiver_list)):
        #         ignore_rcvrs_list.append(ws.cell(row=r + eqmt_row, column=c + rcvr_col).value)
        #     self.ignore_matrix.append(ignore_rcvrs_list)

        # # initialize directivity matrix
        # c = DIRECTIVITY_MATRIX_COL # 1-index based
        # r = DIRECTIVITY_MATRIX_ROW
        # self.directivity_matrix = list()
        # for eqmt_row in range(len(self.equipment_list)):
        #     directivity_rcvrs_list = list()
        #     for rcvr_col in range(len(self.receiver_list)):
        #         directivity = ws.cell(row=r + eqmt_row, column=c + rcvr_col).value
        #         if directivity is None:
        #             directivity = 0
        #         directivity_rcvrs_list.append(directivity)
        #     self.directivity_matrix.append(directivity_rcvrs_list)

        # # initialize specific barrier matrix
        # c = SPECIFIC_BAR_MATRIX_COL # 1-index based
        # r = SPECIFIC_BAR_MATRIX_ROW
        # self.specific_bar_matrix = list()
        # for eqmt_row in range(len(self.equipment_list)):
        #     spec_bar_rcvrs_list = list()
        #     for rcvr_col in range(len(self.receiver_list)):
        #         spec_bar = ws.cell(row=r + eqmt_row, column=c + rcvr_col).value
        #         spec_bar_rcvrs_list.append(spec_bar)
        #     self.specific_bar_matrix.append(spec_bar_rcvrs_list)

        # initialize master_scale
        self.old_master_scale = 1.0
        self.known_distance_ft = 1
        if KNOWN_DISTANCE_FT_CELL.value is not None:
            self.known_distance_ft = KNOWN_DISTANCE_FT_CELL.value
        self.scale_line_distance_px = 1
        if SCALE_LINE_DISTANCE_PX_CELL.value is not None:
            self.scale_line_distance_px = SCALE_LINE_DISTANCE_PX_CELL.value
        self.master_scale = self.known_distance_ft / self.scale_line_distance_px
        self.quickdraw_bool = tk.IntVar()
        self.quickdraw_bool.set(True)
        self.e_to_r_shapes_bool = tk.BooleanVar()
        self.grid_uses_nc_bool = tk.BooleanVar()
        self.grid_uses_nc_bool.set(True)
        self.grid_color_only_bool = tk.BooleanVar()
        self.grid_color_only_bool.set(False)
        self.draw_grid_legend_bool = tk.BooleanVar()
        self.use_specific_bar_bool = tk.BooleanVar()
        self.use_specific_bar_bool.set(USE_SPECIFIC_BAR_BOOL)

    def update_master_scale(self, scale_line_distance_px, known_distance_ft):
        self.scale_line_distance_px = scale_line_distance_px
        self.known_distance_ft = known_distance_ft
        self.old_master_scale = self.master_scale
        self.master_scale = self.known_distance_ft / self.scale_line_distance_px

        """rescaling eqmt"""
        for obj in self.equipment_list:
            obj.x_coord /= self.old_master_scale
            obj.y_coord /= self.old_master_scale
            obj.x_coord *= self.master_scale
            obj.y_coord *= self.master_scale
            obj.x_coord = round(obj.x_coord, 2)
            obj.y_coord = round(obj.y_coord, 2)

        """rescaling rcvrs"""
        for obj in self.receiver_list:
            obj.x_coord /= self.old_master_scale
            obj.y_coord /= self.old_master_scale
            obj.x_coord *= self.master_scale
            obj.y_coord *= self.master_scale
            obj.x_coord = round(obj.x_coord, 2)
            obj.y_coord = round(obj.y_coord, 2)

        """rescaling bars"""
        for obj in self.barrier_list:
            obj.x0_coord /= self.old_master_scale
            obj.y0_coord /= self.old_master_scale
            obj.x1_coord /= self.old_master_scale
            obj.y1_coord /= self.old_master_scale
            obj.x0_coord *= self.master_scale
            obj.y0_coord *= self.master_scale
            obj.x1_coord *= self.master_scale
            obj.y1_coord *= self.master_scale
            obj.x0_coord = round(obj.x0_coord, 2)
            obj.y0_coord = round(obj.y0_coord, 2)
            obj.x1_coord = round(obj.x1_coord, 2)
            obj.y1_coord = round(obj.y1_coord, 2)

        self.parent.pane_eqmt_info.update_est_noise_levels()
        self.parent.pane_eqmt_info.generateRcvrTree()
        self.parent.pane_eqmt_info.generateEqmtTree()
        self.parent.pane_eqmt_info.generateBarrierTree()


class Equipment(object):
    def __init__(
        self,
        count,
        eqmt_tag,
        path,
        make,
        model,
        sound_level,
        sound_ref_dist,
        tested_q,
        installed_q,
        insertion_loss,
        x_coord,
        y_coord,
        z_coord,
        hz63,
        hz125,
        hz250,
        hz500,
        hz1000,
        hz2000,
        hz4000,
        hz8000,
    ):
        self.count = count
        self.eqmt_tag = eqmt_tag.replace(" ", "-")
        self.path = path
        self.make = make
        self.model = model
        self.sound_level = sound_level if sound_level != None else 0
        self.sound_ref_dist = sound_ref_dist if sound_ref_dist != None else 0
        self.tested_q = tested_q
        self.installed_q = installed_q
        self.insertion_loss = insertion_loss if insertion_loss != None else 0
        self.x_coord = x_coord if x_coord != None else 0
        self.y_coord = y_coord if y_coord != None else 0
        self.z_coord = z_coord if z_coord != None else 0
        self.hz63 = hz63
        self.hz125 = hz125
        self.hz250 = hz250
        self.hz500 = hz500
        self.hz1000 = hz1000
        self.hz2000 = hz2000
        self.hz4000 = hz4000
        self.hz8000 = hz8000


class Receiver(object):
    def __init__(
        self, r_name, x_coord, y_coord, z_coord, sound_limit, predicted_sound_level
    ):
        self.r_name = r_name.replace(" ", "-")
        self.x_coord = x_coord if x_coord != None else 0
        self.y_coord = y_coord if y_coord != None else 0
        self.z_coord = z_coord if z_coord != None else 0
        self.sound_limit = sound_limit
        self.predicted_sound_level = predicted_sound_level


class Barrier(object):
    def __init__(
        self, barrier_name, x0_coord, y0_coord, z0_coord, x1_coord, y1_coord, z1_coord
    ):
        self.barrier_name = barrier_name.replace(" ", "-")
        self.x0_coord = x0_coord if x0_coord != None else 0
        self.y0_coord = y0_coord if y0_coord != None else 0
        self.z0_coord = z0_coord if z0_coord != None else 0
        self.x1_coord = x1_coord if x1_coord != None else 0
        self.y1_coord = y1_coord if y1_coord != None else 0
        self.z1_coord = z1_coord if z1_coord != None else 0


class Editor(tk.Frame):
    def __init__(self, parent):
        tk.Frame.__init__(self, parent)
        self.parent = parent
        self.e_to_r_shapes = []
        self.e_to_r_lines_for_opengl = []

        # open image
        self.image = Image.open(BED_IMAGE_FILEPATH)
        self.original_image = Image.open(BED_IMAGE_FILEPATH)  # never resized — source for zoom resamples

        # image sizing
        self.imageWidth, self.imageHeight = self.image.size
        print(self.image.size)
        self.image_size_factor = 1.5
        self.imageWidth *= self.image_size_factor
        self.imageHeight *= self.image_size_factor
        self.imageWidth = int(self.imageWidth)
        self.imageHeight = int(self.imageHeight)
        self.base_imageWidth = self.imageWidth    # zoom=1 pixel dimensions
        self.base_imageHeight = self.imageHeight
        self.image = self.image.resize(
            (self.imageWidth, self.imageHeight), Image.LANCZOS
        )
        self.tk_image = ImageTk.PhotoImage(self.image)
        self.zoom_factor = 1.0
        self.ZOOM_MIN = 0.1
        self.ZOOM_MAX = 10.0

        # canvas sizing
        self.screen_width = self.winfo_screenwidth()
        self.screen_height = self.winfo_screenheight()
        self.canvas_size_factor = 1
        self.canvasWidth = self.screen_width * self.canvas_size_factor
        self.canvasHeight = self.screen_height * self.canvas_size_factor
        self.canvasWidth -= 1000  # otherwise window is off the screen on home pc
        self.canvasHeight -= 150  # otherwise window is off the screen on home pc
        self.canvas = tk.Canvas(
            self, width=self.canvasWidth, height=self.canvasHeight, cursor="cross"
        )

        # giving scrollbars
        self.canvas.config(scrollregion=(0, 0, self.imageWidth, self.imageHeight))
        self.canvas.create_image(
            0, 0, anchor="nw", image=self.tk_image, tag="bed_layer"
        )

        """scroll bar setup"""
        self.vScrollbar = tk.Scrollbar(self, orient=tk.VERTICAL)
        self.hScrollbar = tk.Scrollbar(self, orient=tk.HORIZONTAL)
        self.vScrollbar.config(command=self.canvas.yview)
        self.hScrollbar.config(command=self.canvas.xview)
        self.canvas.config(yscrollcommand=self.vScrollbar.set)
        self.canvas.config(xscrollcommand=self.hScrollbar.set)

        self.canvas.grid(row=0, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
        self.vScrollbar.grid(row=0, column=1, stick=tk.N + tk.S)
        self.hScrollbar.grid(row=1, column=0, sticky=tk.E + tk.W)
        """scroll bar setup"""

        self.initialize_eqmt_rcvr_barrier_grid_drawings()

        self.temp_rect = None
        self.temp_line = None
        self.scale_line = None
        self.measure_line = None
        self.angle = 0

        self.canvas.bind("<Shift-ButtonPress-1>", self.shift_click)
        self.canvas.bind("<Shift-B1-Motion>", self.shift_click_move)
        self.canvas.bind("<Shift-ButtonRelease-1>", self.shift_click_release)

        """Scrollable image"""
        self.canvas.bind("<Enter>", self._bound_to_mousewheel)
        self.canvas.bind("<Leave>", self._unbound_to_mousewheel)

    def initialize_eqmt_rcvr_barrier_grid_drawings(self):
        """initialize receivers / equipment boxes,  grid and barriers """
        for eqmt in self.parent.func_vars.equipment_list:
            green_hex_color = utils.rgb_to_hex((0, 254, 0))
            offset = 20
            x = self.world_to_px(eqmt.x_coord)
            y = self.world_to_px(eqmt.y_coord)
            self.rectPerm = self.canvas.create_rectangle(
                x - offset,
                y - offset,
                x + offset,
                y + offset,
                tag=eqmt.eqmt_tag,
                fill=green_hex_color,
                activeoutline="red",
            )
            self.canvas.create_text(
                x,
                y,
                tag=eqmt.eqmt_tag,
                text=eqmt.eqmt_tag,
                font=DRAWING_FONT,
                fill="Black",
            )

        for rcvr in self.parent.func_vars.receiver_list:
            red_hex_color = utils.rgb_to_hex((254, 0, 0))
            offset = 20
            x = self.world_to_px(rcvr.x_coord)
            y = self.world_to_px(rcvr.y_coord)
            self.rectPerm = self.canvas.create_rectangle(
                x - offset,
                y - offset,
                x + offset,
                y + offset,
                tag=rcvr.r_name,
                fill=red_hex_color,
                activeoutline="red",
            )
            self.canvas.create_text(
                x, y, tag=rcvr.r_name, text=rcvr.r_name, font=DRAWING_FONT, fill="Black"
            )

        for bar in self.parent.func_vars.barrier_list:
            x0 = self.world_to_px(bar.x0_coord)
            y0 = self.world_to_px(bar.y0_coord)
            x1 = self.world_to_px(bar.x1_coord)
            y1 = self.world_to_px(bar.y1_coord)
            self.linePerm = self.canvas.create_line(
                x0, y0, x1, y1, tag=bar.barrier_name, fill="purple", width=5
            )
            self.canvas.create_text(
                x0 + (x1 - x0) / 2,
                y0 + (y1 - y0) / 2,
                tag=bar.barrier_name,
                text=bar.barrier_name,
                font=DRAWING_FONT,
                fill="Black",
            )

        # colorscale = lower bound of each colored bucket; the last bound (70)
        # is the "70+" bucket (NC tops out at 70+). colorlist[0] colors levels
        # below the first bound; colorlist[i+1] colors the bucket at colorscale[i].
        self.colorscale = [x for x in range(25, 75, 5)]  # [25, 30, ..., 70]
        self.colorlist = [
            "cyan3",       # < 25
            "green3",      # 25-29
            "blue",        # 30-34
            "yellow3",     # 35-39
            "DarkOrange1", # 40-44
            "OrangeRed2",  # 45-49
            "maroon2",     # 50-54
            "purple",      # 55-59
            "grey",        # 60-64
            "gray40",      # 65-69
            "black",       # 70+
        ]
        if len(self.colorscale) + 1 != len(self.colorlist):
            print(f"colorscale_len: {len(self.colorscale)}")
            print(f"colorlist_len: {len(self.colorlist)}")
            raise ValueError("colorscale and colorlist not aligned.")

        # redraw grid
        if self.parent.func_vars.grid_outline_coords is not None:
            coords = self.parent.func_vars.grid_outline_coords
            self.grid_rect = self.canvas.create_rectangle(
                self.world_to_px(coords[0]),
                self.world_to_px(coords[1]),
                self.world_to_px(coords[2]),
                self.world_to_px(coords[3]),
                outline="green",
                width=5,
                tag="grid_rect",
            )
        # HEATMAP_COLORS = [
        #     "#0F52BA",  # < 30       sapphire blue
        #     "#00B7EB",  # 30-34      electric cyan
        #     "#00FF7F",  # 35-39      spring green
        #     "#FFEA00",  # 40-44      vivid yellow
        #     "#FF8C00",  # 45-49      bright orange
        #     "#FF1744",  # 50-54      hot red-pink
        #     "#B900FF",  # > 55       electric purple/magenta
        # ]

        # def get_heat_color(value):
        #     if value < 30:
        #         return HEATMAP_COLORS[0]
        #     elif value >= 55:
        #         return HEATMAP_COLORS[-1]
        #     else:
        #         idx = 1 + (int(value) - 30) // 5
        #         idx = min(idx, len(HEATMAP_COLORS) - 2)
        #     return HEATMAP_COLORS[idx]

        for grid_rcvr in self.parent.func_vars.grid_receiver_coords:
            x = self.parent.editor.world_to_px(grid_rcvr[0])
            y = self.parent.editor.world_to_px(grid_rcvr[1])
            classifier = ""
            font = GRID_FONT
            if self.parent.pane_toolbox.combobox_grid_metric.get() == "RC":
                font = DRAWING_FONT
                classifier = grid_rcvr[3]

            # NC can be the string "70+"; treat it as off the top of the scale
            # for coloring and keep the label text as-is
            level_str = grid_rcvr[2]
            try:
                level = float(level_str)
                print_level = str(int(round(level)))
            except ValueError:
                level = float("inf")
                print_level = level_str

            textcolor = self.colorlist[0]
            for colorrange, color in zip(self.colorscale, self.colorlist[1:]):
                if level >= colorrange:
                    textcolor = color

            if self.parent.func_vars.grid_color_only_bool.get() is True:
                ofs = self.parent.func_vars.grid_spacing / 2.0
                ofs = self.parent.editor.world_to_px(ofs)
                gr_id = self.canvas.create_rectangle(
                    x-ofs, y-ofs, x+ofs, y+ofs, fill=textcolor, width=0)
            else:
                gr_id = self.parent.editor.canvas.create_text(
                    (x, y),
                    text=print_level+classifier,
                    font=font,
                    fill=textcolor,
                )
            self.parent.func_vars.grid_receivers_on_canvas.append(gr_id)


    def _bound_to_mousewheel(self, event):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Shift-MouseWheel>", self._on_shift_mousewheel)
        self.canvas.bind_all("<Control-MouseWheel>", self._on_ctrl_mousewheel)

    def _unbound_to_mousewheel(self, event):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Shift-MouseWheel>")
        self.canvas.unbind_all("<Control-MouseWheel>")

    def _on_mousewheel(self, event):
        if event.state & 0x0004:  # Ctrl held — handled by _on_ctrl_mousewheel
            return
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_shift_mousewheel(self, event):
        self.canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
        """Scrollable image"""

    def _on_ctrl_mousewheel(self, event):
        factor = 1.15 if event.delta > 0 else (1 / 1.15)
        new_zoom = max(self.ZOOM_MIN, min(self.ZOOM_MAX, self.zoom_factor * factor))
        if new_zoom == self.zoom_factor:
            return

        # World point under cursor — stays fixed across zoom
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        world_x = self.px_to_world(cx)
        world_y = self.px_to_world(cy)

        self.zoom_factor = new_zoom
        self.full_redraw()

        # Scroll so the same world point stays under the cursor
        new_cx = self.world_to_px(world_x)
        new_cy = self.world_to_px(world_y)
        total_w = self.base_imageWidth * self.zoom_factor
        total_h = self.base_imageHeight * self.zoom_factor
        xfrac = max(0.0, min(1.0, (new_cx - event.x) / total_w))
        yfrac = max(0.0, min(1.0, (new_cy - event.y) / total_h))
        self.canvas.xview_moveto(xfrac)
        self.canvas.yview_moveto(yfrac)

    def world_to_px(self, world_coord_ft):
        """Convert world coordinate (feet) to canvas pixels at current zoom."""
        return (world_coord_ft / self.parent.func_vars.master_scale) * self.zoom_factor

    def px_to_world(self, canvas_px):
        """Convert canvas pixels at current zoom to world coordinate (feet)."""
        return (canvas_px / self.zoom_factor) * self.parent.func_vars.master_scale

    def full_redraw(self):
        """Resize image and redraw all canvas items at the current zoom_factor."""
        new_w = int(self.base_imageWidth * self.zoom_factor)
        new_h = int(self.base_imageHeight * self.zoom_factor)

        zoomed_pil = self.original_image.resize((new_w, new_h), Image.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(zoomed_pil)
        self.canvas.itemconfig("bed_layer", image=self.tk_image)
        self.canvas.coords("bed_layer", 0, 0)
        self.canvas.config(scrollregion=(0, 0, new_w, new_h))

        for eqmt in self.parent.func_vars.equipment_list:
            self.canvas.delete(eqmt.eqmt_tag)
        for rcvr in self.parent.func_vars.receiver_list:
            self.canvas.delete(rcvr.r_name)
        for bar in self.parent.func_vars.barrier_list:
            self.canvas.delete(bar.barrier_name)

        # delete grid components (delete-by-tag is a safe no-op if not drawn)
        self.canvas.delete("grid_rect")

        for gr_id in self.parent.func_vars.grid_receivers_on_canvas:
            self.canvas.delete(gr_id)
        self.parent.func_vars.grid_receivers_on_canvas.clear()

        self.initialize_eqmt_rcvr_barrier_grid_drawings()
        self.parent.pane_toolbox.draw_eqmt_to_rcvr_shapes()

    def get_angle(self, x, y):
        v0 = [x, 0]
        v1 = [x, y]
        dot_product = numpy.dot(v0, v1)
        v0_mag = numpy.linalg.norm(v0)
        v1_mag = numpy.linalg.norm(v1)
        angle = math.degrees(numpy.arccos((dot_product / (v0_mag * v1_mag))))
        if dot_product < 0:
            angle += 90
        print("hey", angle)
        return angle

    def update_distance_label(self):
        dist = math.sqrt((self.x0 - self.curX) ** 2 + (self.y0 - self.curY) ** 2)
        dist = round(self.px_to_world(dist), 2)
        self.parent.pane_eqmt_info.measurement_label.configure(
            text="Measurement: " + str(dist) + " ft"
        )

    def get_current_n_start_mouse_pos(self, event):
        self.x0 = self.canvas.canvasx(event.x)
        self.y0 = self.canvas.canvasy(event.y)
        self.curX = self.canvas.canvasx(event.x)
        self.curY = self.canvas.canvasy(event.y)

    def get_current_mouse_pos(self, event):
        self.curX = self.canvas.canvasx(event.x)
        self.curY = self.canvas.canvasy(event.y)

    def drawing_grid_leftMouseClick(self, event):
        self.canvas.delete("grid_rect")
        self.canvas.delete("grid_level")
        self.get_current_n_start_mouse_pos(event)
        self.temp_rect = self.canvas.create_rectangle(
            self.x0, self.y0, self.x0, self.y0, outline="green", width=5
        )

    def drawing_grid_leftMouseMove(self, event):
        self.get_current_mouse_pos(event)
        self.canvas.coords(self.temp_rect, self.x0, self.y0, self.curX, self.curY)

    def drawing_grid_leftMouseRelease(self, event):
        self.get_current_mouse_pos(event)
        self.canvas.delete(self.temp_rect)
        self.parent.func_vars.grid_outline_coords = [
            self.px_to_world(self.x0),
            self.px_to_world(self.y0),
            self.px_to_world(self.curX),
            self.px_to_world(self.curY)
            ]
        self.grid_rect = self.canvas.create_rectangle(
            self.x0,
            self.y0,
            self.curX,
            self.curY,
            outline="green",
            width=5,
            tag="grid_rect",
        )

    def setting_scale_leftMouseClick(self, event):
        self.get_current_n_start_mouse_pos(event)

        if self.scale_line != None:
            self.canvas.delete(self.scale_line)
        self.temp_scale_line = self.canvas.create_line(
            self.x0, self.y0, self.curX, self.curY, fill="orange", width=5
        )

    def setting_scale_leftMouseMove(self, event):
        self.get_current_mouse_pos(event)
        self.canvas.coords(self.temp_scale_line, self.x0, self.y0, self.curX, self.curY)

    def setting_scale_leftMouseRelease(self, event):
        self.get_current_mouse_pos(event)
        self.canvas.delete(self.temp_scale_line)

        self.scale_line = self.canvas.create_line(
            self.x0, self.y0, self.curX, self.curY, fill="blue", width=5
        )
        scale_line_coords = self.canvas.coords(self.scale_line)
        _scale_line_distance_px = utils.distance_formula(
            scale_line_coords[0],
            scale_line_coords[2],
            scale_line_coords[1],
            scale_line_coords[3],
        ) / self.zoom_factor
        _known_distance_ft = float(self.parent.pane_eqmt_info.entryBox1.get())
        self.parent.func_vars.update_master_scale(
            _scale_line_distance_px, _known_distance_ft
        )

        scaleIndicatorLabelText = (
            "Scale: "
            + str(round(self.parent.func_vars.scale_line_distance_px, 0))
            + " px = "
            + str(self.parent.func_vars.known_distance_ft)
            + " ft"
        )
        self.parent.pane_eqmt_info.scaleIndicatorLabel.configure(
            text=scaleIndicatorLabelText
        )

    def drawing_eqmt_leftMouseClick(self, event):
        self.get_current_n_start_mouse_pos(event)
        self.temp_rect = self.canvas.create_rectangle(
            self.x0, self.y0, self.x0, self.y0, outline="red"
        )

    def drawing_eqmt_leftMouseMove(self, event):
        self.get_current_mouse_pos(event)
        self.canvas.coords(self.temp_rect, self.x0, self.y0, self.curX, self.curY)

    def drawing_eqmt_leftMouseRelease(self, event):
        self.get_current_mouse_pos(event)
        self.canvas.delete(self.temp_rect)

        green_hex_color = utils.rgb_to_hex((0, 254, 0))

        eqmt_tag = self.parent.pane_eqmt_info.current_equipment[1]
        tagged_objects = self.canvas.find_withtag(eqmt_tag)
        for tagged_object in tagged_objects:
            self.canvas.delete(tagged_object)
        self.rectPerm = self.canvas.create_rectangle(
            self.x0,
            self.y0,
            self.curX,
            self.curY,
            tag=eqmt_tag,
            fill=green_hex_color,
            activeoutline="red",
        )

        self.canvas.create_text(
            (self.x0 + (self.curX - self.x0) / 2, self.y0 + (self.curY - self.y0) / 2),
            tag=eqmt_tag,
            text=eqmt_tag,
            font=DRAWING_FONT,
            fill="Black",
        )

        # update this one piece of eqmt
        for obj in self.parent.func_vars.equipment_list:
            if obj.eqmt_tag == eqmt_tag:
                obj.x_coord = round(self.px_to_world(self.x0 + (self.curX - self.x0) / 2), 2)
                obj.y_coord = round(self.px_to_world(self.y0 + (self.curY - self.y0) / 2), 2)

        self.parent.pane_eqmt_info.focused_tree_children = (
            self.parent.pane_eqmt_info.equipment_tree.get_children()
        )
        idx = self.parent.pane_eqmt_info.equipment_tree.index(
            self.parent.pane_eqmt_info.focused_line
        )

        self.parent.pane_eqmt_info.update_est_noise_levels()
        self.parent.pane_eqmt_info.generateRcvrTree()
        self.parent.pane_eqmt_info.generateEqmtTree()

        children = self.parent.pane_eqmt_info.equipment_tree.get_children()
        to_focus = children[idx]

        if self.parent.func_vars.quickdraw_bool.get() == 1:
            self.parent.pane_eqmt_info.focused_line = (
                self.parent.pane_eqmt_info.equipment_tree.next(to_focus)
            )
            if self.parent.pane_eqmt_info.focused_line != "":
                self.parent.pane_eqmt_info.equipment_tree.selection_set(
                    self.parent.pane_eqmt_info.focused_line
                )
                self.parent.pane_eqmt_info.current_equipment = (
                    self.parent.pane_eqmt_info.equipment_tree.item(
                        self.parent.pane_eqmt_info.focused_line
                    )["values"]
                )
            else:
                self.parent.pane_eqmt_info.deselect_item_from_trees()
        else:
            self.parent.pane_eqmt_info.focused_line = to_focus
            self.parent.pane_eqmt_info.equipment_tree.selection_set(to_focus)

    def drawing_rcvr_leftMouseClick(self, event):
        self.get_current_n_start_mouse_pos(event)
        self.temp_rect = self.canvas.create_rectangle(
            self.x0, self.y0, self.x0, self.y0, outline="green"
        )

    def drawing_rcvr_leftMouseMove(self, event):
        self.get_current_mouse_pos(event)
        self.canvas.coords(self.temp_rect, self.x0, self.y0, self.curX, self.curY)

    def drawing_rcvr_leftMouseRelease(self, event):
        self.get_current_mouse_pos(event)
        self.canvas.delete(self.temp_rect)

        red_hex_color = utils.rgb_to_hex((254, 0, 0))

        r_name = self.parent.pane_eqmt_info.current_receiver[0]
        tagged_objects = self.canvas.find_withtag(r_name)
        for tagged_object in tagged_objects:
            self.canvas.delete(tagged_object)
        self.rectPerm = self.canvas.create_rectangle(
            self.x0,
            self.y0,
            self.curX,
            self.curY,
            tag=r_name,
            fill=red_hex_color,
            activeoutline="red",
        )

        self.canvas.create_text(
            (self.x0 + (self.curX - self.x0) / 2, self.y0 + (self.curY - self.y0) / 2),
            tag=r_name,
            text=r_name,
            font=DRAWING_FONT,
            fill="Black",
        )

        # update this one rcvr
        for obj in self.parent.func_vars.receiver_list:
            if obj.r_name == r_name:
                obj.x_coord = round(self.px_to_world(self.x0 + (self.curX - self.x0) / 2), 2)
                obj.y_coord = round(self.px_to_world(self.y0 + (self.curY - self.y0) / 2), 2)

        self.parent.pane_eqmt_info.focused_tree_children = (
            self.parent.pane_eqmt_info.receiver_tree.get_children()
        )
        idx = self.parent.pane_eqmt_info.receiver_tree.index(
            self.parent.pane_eqmt_info.focused_line
        )

        self.parent.pane_eqmt_info.update_est_noise_levels()
        self.parent.pane_eqmt_info.generateRcvrTree()

        children = self.parent.pane_eqmt_info.receiver_tree.get_children()
        to_focus = children[idx]

        if self.parent.func_vars.quickdraw_bool.get() == 1:
            self.parent.pane_eqmt_info.focused_line = (
                self.parent.pane_eqmt_info.receiver_tree.next(to_focus)
            )
            if self.parent.pane_eqmt_info.focused_line != "":
                self.parent.pane_eqmt_info.receiver_tree.selection_set(
                    self.parent.pane_eqmt_info.focused_line
                )
                self.parent.pane_eqmt_info.current_receiver = (
                    self.parent.pane_eqmt_info.receiver_tree.item(
                        self.parent.pane_eqmt_info.focused_line
                    )["values"]
                )
            else:
                self.parent.pane_eqmt_info.deselect_item_from_trees()
        else:
            self.parent.pane_eqmt_info.focused_line = to_focus
            self.parent.pane_eqmt_info.receiver_tree.selection_set(to_focus)

    def drawing_barrier_leftMouseClick(self, event):
        self.get_current_n_start_mouse_pos(event)
        self.temp_line = self.canvas.create_line(
            self.x0, self.y0, self.curX, self.curY, fill="yellow", width=5
        )

    def drawing_barrier_leftMouseMove(self, event):
        self.get_current_mouse_pos(event)
        self.canvas.coords(self.temp_line, self.x0, self.y0, self.curX, self.curY)

    def drawing_barrier_leftMouseRelease(self, event):
        self.get_current_mouse_pos(event)
        self.canvas.delete(self.temp_line)

        barrier_name = self.parent.pane_eqmt_info.current_barrier[0]
        tagged_objects = self.canvas.find_withtag(barrier_name)
        for tagged_object in tagged_objects:
            self.canvas.delete(tagged_object)
        self.barPerm = self.canvas.create_line(
            self.x0,
            self.y0,
            self.curX,
            self.curY,
            tag=barrier_name,
            fill="purple",
            width=5,
        )

        self.canvas.create_text(
            (self.x0 + (self.curX - self.x0) / 2, self.y0 + (self.curY - self.y0) / 2),
            tag=barrier_name,
            text=barrier_name,
            font=DRAWING_FONT,
            fill="Black",
        )

        # update this one bar
        for obj in self.parent.func_vars.barrier_list:
            if obj.barrier_name == barrier_name:
                obj.x0_coord = round(self.px_to_world(self.x0), 2)
                obj.y0_coord = round(self.px_to_world(self.y0), 2)
                obj.x1_coord = round(self.px_to_world(self.curX), 2)
                obj.y1_coord = round(self.px_to_world(self.curY), 2)

        self.parent.pane_eqmt_info.focused_tree_children = (
            self.parent.pane_eqmt_info.barrier_tree.get_children()
        )
        idx = self.parent.pane_eqmt_info.barrier_tree.index(
            self.parent.pane_eqmt_info.focused_line
        )

        self.parent.pane_eqmt_info.generateRcvrTree()
        self.parent.pane_eqmt_info.generateBarrierTree()
        self.parent.pane_eqmt_info.update_est_noise_levels()

        children = self.parent.pane_eqmt_info.barrier_tree.get_children()
        to_focus = children[idx]

        if self.parent.func_vars.quickdraw_bool.get() == 1:
            self.parent.pane_eqmt_info.focused_line = (
                self.parent.pane_eqmt_info.barrier_tree.next(to_focus)
            )
            if self.parent.pane_eqmt_info.focused_line != "":
                self.parent.pane_eqmt_info.barrier_tree.selection_set(
                    self.parent.pane_eqmt_info.focused_line
                )
                self.parent.pane_eqmt_info.current_barrier = (
                    self.parent.pane_eqmt_info.barrier_tree.item(
                        self.parent.pane_eqmt_info.focused_line
                    )["values"]
                )
            else:
                self.parent.pane_eqmt_info.deselect_item_from_trees()
        else:
            self.parent.pane_eqmt_info.focused_line = to_focus
            self.parent.pane_eqmt_info.barrier_tree.selection_set(to_focus)

    def measureing_leftMouseClick(self, event):
        self.get_current_n_start_mouse_pos(event)
        if self.measure_line != None:
            self.canvas.delete(self.measure_line)
        self.update_distance_label()
        self.temp_measure_line = self.canvas.create_line(
            self.x0, self.y0, self.curX, self.curY, fill="orange", width=5
        )

    def measureing_leftMouseMove(self, event):
        self.get_current_mouse_pos(event)
        self.canvas.coords(
            self.temp_measure_line, self.x0, self.y0, self.curX, self.curY
        )
        self.update_distance_label()

    def measureing_leftMouseRelease(self, event):
        self.get_current_mouse_pos(event)
        self.canvas.delete(self.temp_measure_line)
        self.measure_line = self.canvas.create_line(
            self.x0, self.y0, self.curX, self.curY, fill="red", width=5
        )

    def shift_click(self, event):
        if self.canvas.find_withtag("current"):
            self.eqmt_rcvr_or_barr_tagged = self.canvas.gettags("current")
            self.tag_rcvr_or_barr_num = self.eqmt_rcvr_or_barr_tagged[0]
            self.eqmt_rcvr_barr_ids = self.canvas.find_withtag(
                self.eqmt_rcvr_or_barr_tagged[0]
            )
            self.current_shape = self.eqmt_rcvr_barr_ids[0]
            self.current_text = self.eqmt_rcvr_barr_ids[1]
            self.current_shape_coords = self.canvas.coords(self.current_shape)
            self.current_text_coords = self.canvas.coords(self.current_text)

            self.get_current_n_start_mouse_pos(event)

        for obj in self.parent.func_vars.equipment_list:
            if obj.eqmt_tag == self.tag_rcvr_or_barr_num:
                self.obj_x_coord_0 = obj.x_coord
                self.obj_y_coord_0 = obj.y_coord

        for obj in self.parent.func_vars.receiver_list:
            if obj.r_name == self.tag_rcvr_or_barr_num:
                self.obj_x_coord_0 = obj.x_coord
                self.obj_y_coord_0 = obj.y_coord

        for obj in self.parent.func_vars.barrier_list:
            if obj.barrier_name == self.tag_rcvr_or_barr_num:
                self.obj_x_coord_0 = obj.x0_coord
                self.obj_y_coord_0 = obj.y0_coord
                self.obj_x_coord_1 = obj.x1_coord
                self.obj_y_coord_1 = obj.y1_coord

    def shift_click_move(self, event):
        self.get_current_mouse_pos(event)
        x_shifter = self.curX - self.x0
        y_shifter = self.curY - self.y0
        self.canvas.coords(
            self.current_shape,
            self.current_shape_coords[0] + x_shifter,
            self.current_shape_coords[1] + y_shifter,
            self.current_shape_coords[2] + x_shifter,
            self.current_shape_coords[3] + y_shifter,
        )
        self.canvas.coords(
            self.current_text,
            self.current_text_coords[0] + x_shifter,
            self.current_text_coords[1] + y_shifter,
        )

    def shift_click_release(self, event):
        self.get_current_mouse_pos(event)
        x_shifter = self.curX - self.x0
        y_shifter = self.curY - self.y0
        self.canvas.coords(
            self.current_shape,
            self.current_shape_coords[0] + x_shifter,
            self.current_shape_coords[1] + y_shifter,
            self.current_shape_coords[2] + x_shifter,
            self.current_shape_coords[3] + y_shifter,
        )
        self.canvas.coords(
            self.current_text,
            self.current_text_coords[0] + x_shifter,
            self.current_text_coords[1] + y_shifter,
        )

        for obj in self.parent.func_vars.equipment_list:
            if obj.eqmt_tag == self.tag_rcvr_or_barr_num:
                obj.x_coord = round(self.obj_x_coord_0 + self.px_to_world(x_shifter), 2)
                obj.y_coord = round(self.obj_y_coord_0 + self.px_to_world(y_shifter), 2)

        for obj in self.parent.func_vars.receiver_list:
            if obj.r_name == self.tag_rcvr_or_barr_num:
                obj.x_coord = round(self.obj_x_coord_0 + self.px_to_world(x_shifter), 2)
                obj.y_coord = round(self.obj_y_coord_0 + self.px_to_world(y_shifter), 2)

        for obj in self.parent.func_vars.barrier_list:
            if obj.barrier_name == self.tag_rcvr_or_barr_num:
                obj.x0_coord = round(self.obj_x_coord_0 + self.px_to_world(x_shifter), 2)
                obj.y0_coord = round(self.obj_y_coord_0 + self.px_to_world(y_shifter), 2)
                obj.x1_coord = round(self.obj_x_coord_1 + self.px_to_world(x_shifter), 2)
                obj.y1_coord = round(self.obj_y_coord_1 + self.px_to_world(y_shifter), 2)

        self.parent.pane_eqmt_info.update_est_noise_levels()
        self.parent.pane_toolbox.draw_eqmt_to_rcvr_shapes()
        self.parent.pane_eqmt_info.generateEqmtTree()
        self.parent.pane_eqmt_info.generateRcvrTree()
        self.parent.pane_eqmt_info.generateBarrierTree()


class Pane_Toolbox(tk.Frame):
    def __init__(self, parent):
        tk.Frame.__init__(self, parent)
        self.parent = parent

        self.button_set_image_scale = tk.Button(
            self, text="Set Image Scale", command=self.set_scale, font=(None, 15)
        )
        self.button_measure = tk.Button(
            self, text="Measure", command=self.measure, font=(None, 15)
        )
        self.button_draw_equipment = tk.Button(
            self, text="Draw Equipment", command=self.draw_equipment, font=(None, 15)
        )
        self.button_draw_receiver = tk.Button(
            self, text="Draw Receiver", command=self.draw_receiver, font=(None, 15)
        )
        self.button_draw_barrier = tk.Button(
            self, text="Draw Barrier", command=self.draw_barrier, font=(None, 15)
        )
        self.checkbox_quickdraw = tk.Checkbutton(
            self,
            text="Quickdraw",
            variable=self.parent.func_vars.quickdraw_bool,
            onvalue=1,
            offvalue=0,
            font=(None, 15),
        )
        self.checkbox_specific_barrier = tk.Checkbutton(
            self,
            text="Specific Barrier",
            variable=self.parent.func_vars.use_specific_bar_bool,
            onvalue=True,
            offvalue=False,
            command=self.specificbar_update_est_noise_levels,
            font=(None, 15),
        )
        self.checkbox_e_to_r_shapes = tk.Checkbutton(
            self,
            text="eqmt_to_rcvr_shapes",
            variable=self.parent.func_vars.e_to_r_shapes_bool,
            onvalue=True,
            offvalue=False,
            command=self.draw_eqmt_to_rcvr_shapes,
            font=(None, 15),
        )
        # self.checkbox_grid_uses_nc = tk.Checkbutton(
        #     self,
        #     text="grid_uses_nc",
        #     variable=self.parent.func_vars.grid_uses_nc_bool,
        #     onvalue=True,
        #     offvalue=False,
        #     command=self.update_grid,
        #     font=(None, 15),
        # )
        self.combobox_grid_metric = tkinter.ttk.Combobox(
            self,
            values=["NC", "dBA", "RC"],
            state="readonly"
        )
        self.combobox_grid_metric.set(GRID_DEFAULT_METRIC)
        self.combobox_roof_assembly = tkinter.ttk.Combobox(
            self,
            values=[x for x in self.parent.func_vars.roof_assembly_dict.keys()],
            state="readonly"
        )
        try:
            self.combobox_roof_assembly.set(list(self.parent.func_vars.roof_assembly_dict.keys())[1])
        except IndexError:
            self.combobox_roof_assembly.set("None")
        self.checkbox_grid_legend = tk.Checkbutton(
            self,
            text="Draw Grid Legend",
            variable=self.parent.func_vars.draw_grid_legend_bool,
            onvalue=True,
            offvalue=False,
            command=self.draw_grid_legend,
            font=(None, 15),
        )
        self.checkbox_grid_color_only = tk.Checkbutton(
            self,
            text="Grid w/ Colors Only",
            variable=self.parent.func_vars.grid_color_only_bool,
            onvalue=True,
            offvalue=False,
            command=self.update_grid,
            font=(None, 15),
        )
        self.button_draw_grid = tk.Button(
            self, text="Draw Grid", command=self.draw_grid, font=(None, 15)
        )
        self.button_update_grid = tk.Button(
            self, text="Update Grid", command=self.update_grid, font=(None, 15)
        )
        self.button_export_bar_file = tk.Button(
            self,
            text="Export Bar to File",
            command=self.export_bar_file,
            font=(None, 15),
        )
        self.button_view_3d = tk.Button(
            self, text="View 3D", command=self.open_3d_view, font=(None, 15)
        )

        self.button_set_image_scale.grid(row=0, column=0, sticky=tk.N + tk.W)
        self.button_measure.grid(row=1, column=0, sticky=tk.N + tk.W)
        self.button_draw_equipment.grid(row=0, column=1, sticky=tk.N + tk.W)
        self.button_draw_receiver.grid(row=1, column=1, sticky=tk.N + tk.W)
        self.button_draw_barrier.grid(row=2, column=1, sticky=tk.N + tk.W)
        self.checkbox_quickdraw.grid(row=3, column=1, sticky=tk.N + tk.W)
        self.checkbox_specific_barrier.grid(row=4, column=1, sticky=tk.N + tk.W)
        self.checkbox_e_to_r_shapes.grid(row=5, column=1, sticky=tk.N + tk.W)
        # self.checkbox_grid_uses_nc.grid(row=6, column=1, sticky=tk.N + tk.W)
        self.combobox_grid_metric.grid(row=6, column=1, sticky=tk.N + tk.W)
        self.combobox_roof_assembly.grid(row=7, column=1, sticky=tk.N + tk.W)
        self.checkbox_grid_legend.grid(row=8, column=1, sticky=tk.N + tk.W)
        self.checkbox_grid_color_only.grid(row=9, column=1, sticky=tk.N + tk.W)
        self.button_draw_grid.grid(row=0, column=2, sticky=tk.N + tk.W)
        self.button_update_grid.grid(row=1, column=2, sticky=tk.N + tk.W)
        self.button_export_bar_file.grid(row=2, column=2, sticky=tk.N + tk.W)
        self.button_view_3d.grid(row=3, column=2, sticky=tk.N + tk.W)

        self.combobox_roof_assembly.bind("<<ComboboxSelected>>", self.update_selected_roof_assembly)
        self.combobox_grid_metric.bind("<<ComboboxSelected>>", self.update_grid_per_metric_change)

        self.demo_grid_drawings = []

    def update_grid_per_metric_change(self, event):
        self.update_grid()

    def draw_grid_legend(self):

        if self.parent.func_vars.draw_grid_legend_bool.get() is False:
            for item in self.demo_grid_drawings:
                self.parent.editor.canvas.delete(item)
            self.demo_grid_drawings.clear()
            return

        # colorscale is the lower bound of each bucket; the last bound is the
        # "70+" overflow. Labels: "<min", "lo-hi" per interior bucket, "70+".
        colorscale = self.parent.editor.colorscale
        scale_txt = [f"<{colorscale[0]}"]
        for i in range(len(colorscale) - 1):
            scale_txt.append(f"{colorscale[i]}-{colorscale[i + 1] - 1}")
        scale_txt.append(f"{colorscale[-1]}+")

        height = 0
        offset = 55
        x_start = -offset
        y_start = offset*2
        colorlist = self.parent.editor.colorlist
        for txt, color in zip(scale_txt, colorlist):
            txt_color = "black"
            if color in ("black", "gray40"):
                txt_color = "white"

            shape1 = self.parent.editor.canvas.create_rectangle(
                x_start - offset,
                y_start + height - offset,
                x_start + offset,
                y_start + height + offset,
                fill=color,
            )
            shape2 = self.parent.editor.canvas.create_text(
                x_start,
                y_start + height,
                text=txt,
                font=GRID_FONT,
                fill=txt_color
            )
            height += offset * 2
            self.demo_grid_drawings += [shape1, shape2]

    def update_selected_roof_assembly(self, event):
        self.parent.func_vars.selected_roof_assembly = self.combobox_roof_assembly.get()
        self.update_grid()

    def specificbar_update_est_noise_levels(self):
        self.parent.pane_eqmt_info.update_est_noise_levels()
        self.parent.pane_toolbox.draw_eqmt_to_rcvr_shapes()
        self.parent.pane_eqmt_info.generateRcvrTree()

    def export_bar_file(self):
        with open("bar_export_list.csv", mode="w", newline="") as csvfile:
            csv_writer = csv.writer(
                csvfile, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
            )
            for barrier_item in self.parent.pane_eqmt_info.barrierListForExcelOutput:
                print(barrier_item)
                csv_writer.writerow(barrier_item)
        BarrierPlotExporter.exportBarrierPlots(
            self.parent.pane_eqmt_info.barrierListForExcelOutput[1:]
        )

    def open_3d_view(self):
        from opengl_view import View3D, SceneData

        def make_scene():
            return SceneData(
                self.parent.func_vars.equipment_list,
                self.parent.func_vars.receiver_list,
                self.parent.func_vars.barrier_list,
                self.parent.editor.e_to_r_lines_for_opengl,
                master_scale=self.parent.func_vars.master_scale,
                image_size_factor=self.parent.editor.image_size_factor,
                image_path=BED_IMAGE_FILEPATH,
                image_height=IMAGE_HEIGHT_3D_VIEW
            )

        # If already open, reload scene data in-place (camera preserved)
        if hasattr(self, "_view3d_instance") and self._view3d_instance is not None:
            if hasattr(self, "_view3d_thread") and self._view3d_thread.is_alive():
                self._view3d_instance.request_reload(make_scene())
                return

        # Fresh open
        v = View3D(make_scene())
        v._reload_callback = make_scene
        self._view3d_instance = v
        self._view3d_thread = threading.Thread(target=v.run, daemon=True)
        self._view3d_thread.start()

    def draw_eqmt_to_rcvr_shapes(self):

        for shape in self.parent.editor.e_to_r_shapes:
            self.parent.editor.canvas.delete(shape)
        self.parent.editor.e_to_r_shapes.clear()
        self.parent.editor.e_to_r_lines_for_opengl = []
        tmp_e_2_r_nobar = []
        tmp_e_2_r_yesbar = []

        if not self.parent.pane_eqmt_info.current_receiver:
            return

        this_r_name = self.parent.pane_eqmt_info.current_receiver[0]
        canvas_rcvr = self.parent.editor.canvas.find_withtag(this_r_name)

        for rcvr_index, rcvr in enumerate(self.parent.func_vars.receiver_list):
            if this_r_name != rcvr.r_name:
                continue
            stnd_draw_lines = []
            bar_draw_lines = []
            bar_draw_txt = []
            for eqmt_index, eqmt in enumerate(self.parent.func_vars.equipment_list):
                if self.parent.func_vars.ignore_matrix[eqmt_index][rcvr_index] != None:
                    continue

                # rcvr
                canvas_rcvr_id = canvas_rcvr[0]
                coords = self.parent.editor.canvas.coords(canvas_rcvr_id)
                center_x = (coords[0] + coords[2]) / 2
                center_y = (coords[1] + coords[3]) / 2
                r_coords = center_x, center_y

                # eqmt
                canvas_eqmt_id = self.parent.editor.canvas.find_withtag(eqmt.eqmt_tag)[ 0 ]
                # coords = self.parent.editor.canvas.bbox(canvas_eqmt_id)
                coords = self.parent.editor.canvas.coords(canvas_eqmt_id)
                center_x = (coords[0] + coords[2]) / 2
                center_y = (coords[1] + coords[3]) / 2
                e_coords = center_x, center_y

                # bar
                bar_obj = self.parent.func_vars.e_to_r_with_bar[eqmt][rcvr]["bar_obj"]
                if not bar_obj:
                    stnd_draw_lines.append([r_coords, e_coords])
                    tmp_e_2_r_nobar.append( (eqmt.x_coord, eqmt.y_coord, eqmt.z_coord, rcvr.x_coord, rcvr.y_coord, rcvr.z_coord, 1, 1, 0 )) # yellow
                else:
                    bar_draw_lines.append([r_coords, e_coords])
                    tmp_e_2_r_yesbar.append( (eqmt.x_coord, eqmt.y_coord, eqmt.z_coord, rcvr.x_coord, rcvr.y_coord, rcvr.z_coord, 0, 0, 1)) # blue

                    bar_il = self.parent.func_vars.e_to_r_with_bar[eqmt][rcvr]["bar_il"]
                    canvas_bar_id = self.parent.editor.canvas.find_withtag(
                        bar_obj.barrier_name
                    )[0]
                    b_coords = self.parent.editor.canvas.coords(canvas_bar_id)

                    x1, y1, x2, y2 = b_coords
                    x3, y3 = e_coords
                    x4, y4 = r_coords
                    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
                    if (
                        denom == 0
                    ):  # Lines are parallel or collinear, should never happen here
                        continue
                    px = (
                        (x1 * y2 - y1 * x2) * (x3 - x4)
                        - (x1 - x2) * (x3 * y4 - y3 * x4)
                    ) / denom
                    py = (
                        (x1 * y2 - y1 * x2) * (y3 - y4)
                        - (y1 - y2) * (x3 * y4 - y3 * x4)
                    ) / denom
                    bar_draw_txt.append((px, py, bar_il))
                    # intersection = (px, py)

                for r_coords, e_coords in stnd_draw_lines:
                    self.parent.editor.e_to_r_shapes.append(
                        self.parent.editor.canvas.create_line(
                            r_coords, e_coords, fill="yellow", width=1
                        )
                    )
                for r_coords, e_coords in bar_draw_lines:
                    self.parent.editor.e_to_r_shapes.append(
                        self.parent.editor.canvas.create_line(
                            r_coords, e_coords, fill="blue", width=1
                        )
                    )
                for x, y, bar_il in bar_draw_txt:
                    self.parent.editor.e_to_r_shapes.append(
                        self.parent.editor.canvas.create_text(
                            x,
                            y,
                            text=str(int(round(bar_il, 0))),
                            font=BAR_IL_FONT,
                            fill="red",
                        )
                    )

                # for opengl line draw
                self.parent.editor.e_to_r_lines_for_opengl = tmp_e_2_r_nobar + tmp_e_2_r_yesbar
                # TODO
                # check barriers
                # get barrier coords
                # markup canvas where barrier crosses path

    def draw_grid(self):
        self.parent.editor.canvas.bind(
            "<ButtonPress-1>", self.parent.editor.drawing_grid_leftMouseClick
        )
        self.parent.editor.canvas.bind(
            "<B1-Motion>", self.parent.editor.drawing_grid_leftMouseMove
        )
        self.parent.editor.canvas.bind(
            "<ButtonRelease-1>", self.parent.editor.drawing_grid_leftMouseRelease
        )

        # DEFAULT GRID
        if GRID_DEFAULT_SIZE is None:
            w = self.parent.editor.imageWidth * self.parent.editor.zoom_factor
            h = self.parent.editor.imageHeight * self.parent.editor.zoom_factor
        else:
            w, h = GRID_DEFAULT_SIZE
        self.parent.func_vars.grid_outline_coords = [
            self.parent.editor.px_to_world(0),
            self.parent.editor.px_to_world(0),
            self.parent.editor.px_to_world(w),
            self.parent.editor.px_to_world(h)
            ]
        self.parent.editor.grid_rect = self.parent.editor.canvas.create_rectangle(
            0,
            0,
            w,
            h,
            outline="green",
            width=5,
            tag="grid_rect",
        )

        self.parent.pane_eqmt_info.status_label.configure(text="Status: Drawing Grid-- input elevation, spacing(ft)")
        self.parent.pane_eqmt_info.entryBox1.delete(0, "end")
        self.parent.pane_eqmt_info.entryBox1.insert(0, GRID_DEFAULT_ELEV_SPACE)

        self.parent.pane_eqmt_info.entryBox1.focus()

    def update_grid(self):
        inputdata = self.parent.pane_eqmt_info.entryBox1.get()
        inputdata_list = inputdata.split(",")
        self.parent.func_vars.grid_elevation = float(inputdata_list[0])
        self.parent.func_vars.grid_spacing = float(inputdata_list[1])
        grid_elevation = self.parent.func_vars.grid_elevation
        spacing = self.parent.func_vars.grid_spacing

        grid_rect_coords = self.parent.editor.canvas.coords(
            self.parent.editor.grid_rect
        )
        start_x_coord_ft = self.parent.editor.px_to_world(grid_rect_coords[0])
        start_y_coord_ft = self.parent.editor.px_to_world(grid_rect_coords[1])
        end_x_coord_ft = self.parent.editor.px_to_world(grid_rect_coords[2])
        end_y_coord_ft = self.parent.editor.px_to_world(grid_rect_coords[3])

        grid_receiver_list = []
        cur_x_coord_ft = start_x_coord_ft
        cur_y_coord_ft = start_y_coord_ft
        while cur_y_coord_ft < end_y_coord_ft:
            while cur_x_coord_ft < end_x_coord_ft:
                grid_receiver_list.append([cur_x_coord_ft, cur_y_coord_ft, "0", ""]) #coords, lvl, rc_classifier
                cur_x_coord_ft += spacing
            cur_y_coord_ft += spacing
            cur_x_coord_ft = start_x_coord_ft
        # print(grid_receiver_list)

        # calculating noise levels at receiver in grid list
        # def _get_dBA(rcvr_x_coord, rcvr_y_coord):
        #     sound_pressure = 0
        #     for eqmt in self.parent.func_vars.equipment_list:
        #         if eqmt.sound_ref_dist == 0:
        #             sound_power = eqmt.sound_level
        #         else:
        #             q = eqmt.tested_q  # need to update this
        #             r = eqmt.sound_ref_dist * 0.308
        #             lp = eqmt.sound_level
        #             b = q / (4 * math.pi * r**2)
        #             sound_power = lp + abs(10 * math.log10(b))
        #         sound_power += 10 * math.log10(eqmt.count)
        #         distance = math.sqrt(
        #             (rcvr_x_coord - eqmt.x_coord) ** 2
        #             + (rcvr_y_coord - eqmt.y_coord) ** 2
        #             + (grid_elevation - eqmt.z_coord) ** 2
        #         )
        #         try:
        #             q = eqmt.installed_q
        #             r = distance * 0.308
        #             attenuation = abs(10 * math.log10(q / (4 * math.pi * r**2)))
        #             used_barrier_name = None
        #             barrier_IL = 0
        #             if TAKE_ARI_BARRIER == True and TAKE_OB_FRESNAL_BARRIER == False:
        #                 for bar in self.parent.func_vars.barrier_list:
        #                     barrier_info_list = (
        #                         self.parent.pane_eqmt_info.ARI_barrier_IL_calc(
        #                             eqmt.x_coord,
        #                             eqmt.y_coord,
        #                             eqmt.z_coord,
        #                             bar.x0_coord,
        #                             bar.y0_coord,
        #                             bar.z0_coord,
        #                             bar.x1_coord,
        #                             bar.y1_coord,
        #                             bar.z1_coord,
        #                             rcvr_x_coord,
        #                             rcvr_y_coord,
        #                             grid_elevation,
        #                         )
        #                     )
        #                     barrier_IL_test = (
        #                         barrier_info_list[0] if barrier_info_list != 0 else 0
        #                     )
        #                     if barrier_IL_test > barrier_IL:
        #                         barrier_IL = barrier_IL_test
        #                         used_barrier_name = str(bar.barrier_name + " - ari")

        #             if TAKE_ARI_BARRIER == True and TAKE_OB_FRESNAL_BARRIER == True:
        #                 for bar in self.parent.func_vars.barrier_list:
        #                     if None not in [
        #                         eqmt.hz63,
        #                         eqmt.hz125,
        #                         eqmt.hz250,
        #                         eqmt.hz500,
        #                         eqmt.hz1000,
        #                         eqmt.hz2000,
        #                         eqmt.hz4000,
        #                         eqmt.hz8000,
        #                     ]:
        #                         barrier_info_list = self.parent.pane_eqmt_info.OB_fresnel_barrier_IL_calc(
        #                             eqmt.x_coord,
        #                             eqmt.y_coord,
        #                             eqmt.z_coord,
        #                             eqmt.hz63,
        #                             eqmt.hz125,
        #                             eqmt.hz250,
        #                             eqmt.hz500,
        #                             eqmt.hz1000,
        #                             eqmt.hz2000,
        #                             eqmt.hz4000,
        #                             eqmt.hz8000,
        #                             eqmt.sound_level,
        #                             bar.x0_coord,
        #                             bar.y0_coord,
        #                             bar.z0_coord,
        #                             bar.x1_coord,
        #                             bar.y1_coord,
        #                             bar.z1_coord,
        #                             rcvr_x_coord,
        #                             rcvr_y_coord,
        #                             grid_elevation,
        #                         )
        #                         barrier_IL_test = (
        #                             barrier_info_list[0]
        #                             if barrier_info_list != 0
        #                             else 0
        #                         )
        #                         barriermethod = " - OB_fresnel"
        #                     else:
        #                         barrier_info_list = (
        #                             self.parent.pane_eqmt_info.ARI_barrier_IL_calc(
        #                                 eqmt.x_coord,
        #                                 eqmt.y_coord,
        #                                 eqmt.z_coord,
        #                                 bar.x0_coord,
        #                                 bar.y0_coord,
        #                                 bar.z0_coord,
        #                                 bar.x1_coord,
        #                                 bar.y1_coord,
        #                                 bar.z1_coord,
        #                                 rcvr_x_coord,
        #                                 rcvr_y_coord,
        #                                 grid_elevation,
        #                             )
        #                         )
        #                         barrier_IL_test = (
        #                             barrier_info_list[0]
        #                             if barrier_info_list != 0
        #                             else 0
        #                         )
        #                         barriermethod = " - ari"
        #                     if barrier_IL_test > barrier_IL:
        #                         barrier_IL = barrier_IL_test
        #                         used_barrier_name = str(
        #                             bar.barrier_name + barriermethod
        #                         )

        #             spl = max(0, sound_power - eqmt.insertion_loss - attenuation - barrier_IL)
        #         except ValueError:
        #             # print("MATH DOMAIN ERROR OCCURED")
        #             spl = 1000
        #         sound_pressure += 10 ** (spl / 10)
        #     return 10 * math.log10(sound_pressure)

        def _get_OB_Metric(rcvr_x_coord, rcvr_y_coord):
            sound_pressure_hz = [ 0 ] * len(OCTAVE_BAND_HZ)
            for eqmt in self.parent.func_vars.equipment_list:
                eqmt_hz = [
                        eqmt.hz63,
                        eqmt.hz125,
                        eqmt.hz250,
                        eqmt.hz500,
                        eqmt.hz1000,
                        eqmt.hz2000,
                        eqmt.hz4000,
                        eqmt.hz8000,
                    ]
                # print(eqmt.eqmt_tag, eqmt_hz)
                if None in eqmt_hz:
                    raise ValueError("NC CALCS NOT FUNCTIONAL W/O OCTAVE BAND DATA")

                if eqmt.sound_ref_dist == 0:
                    sound_power_hz = eqmt_hz
                else:
                    q = eqmt.tested_q  # need to update this
                    r = eqmt.sound_ref_dist * 0.308
                    lp_hz = eqmt_hz
                    b = q / (4 * math.pi * r**2)
                    sound_power_hz = [ lp + abs(10 * math.log10(b)) for lp in lp_hz ]
                sound_power_hz = [ lw + 10 * math.log10(eqmt.count) for lw in sound_power_hz ]
                distance = math.sqrt(
                    (rcvr_x_coord - eqmt.x_coord) ** 2
                    + (rcvr_y_coord - eqmt.y_coord) ** 2
                    + (grid_elevation - eqmt.z_coord) ** 2
                )

                try:
                    q = eqmt.installed_q
                    r = distance * 0.308
                    distance_attenuation = abs(10 * math.log10(q / (4 * math.pi * r**2)))

                    # NO BARRIER
                    assembly = self.parent.func_vars.selected_roof_assembly
                    tl_hz = self.parent.func_vars.roof_assembly_dict[assembly]
                    spl_hz = [
                        lw - tl - eqmt.insertion_loss - distance_attenuation for (lw, tl) in zip(sound_power_hz, tl_hz)
                        ]
                    # print(eqmt.eqmt_tag, "spl_hz", spl_hz)
                except (ValueError, ZeroDivisionError):
                    # grid point sits on (or ~0 ft from) this source: mark the
                    # cell off-scale instead of aborting the whole grid
                    spl_hz = [1000] * len(OCTAVE_BAND_HZ)

                for i in range(len(OCTAVE_BAND_HZ)):
                    sound_pressure_hz[i] += 10 ** (spl_hz[i] / 10)
                # print(eqmt.eqmt_tag, "sound_pressure_hz", sound_pressure_hz)

            spl_total_hz = [ 10 * math.log10(pressure) for pressure in sound_pressure_hz ]
            # print(spl_total_hz)
            if self.combobox_grid_metric.get() == "NC":
                return NCLevel(spl_total_hz)
            elif self.combobox_grid_metric.get() == "dBA":
                aweight_hz = [-26.2, -16.1, -8.6, -3.2, -0, 1.2, 1, -1.1]
                spl_total_hz = [ max(0,spl + weight) for (spl, weight) in zip(spl_total_hz, aweight_hz) ]
                dBA = acoustics.decibel.dbsum(spl_total_hz)
                return dBA
            elif self.combobox_grid_metric.get() == "RC":
                return RCLevel(spl_total_hz)
            else:
                raise ValueError("No metric selected")

        for grd_rcvr in grid_receiver_list:
            rcvr_x_coord = grd_rcvr[0]
            rcvr_y_coord = grd_rcvr[1]
            metric_val = _get_OB_Metric(rcvr_x_coord, rcvr_y_coord)
            if self.combobox_grid_metric.get() == "RC":
                grd_rcvr[2] = str(metric_val[0])
                grd_rcvr[3] = str(metric_val[1])
            else:
                grd_rcvr[2] = str(metric_val)

            # if self.combobox_grid_metric.get() == "NC":
            #     grd_rcvr[2] = str( _get_NC(rcvr_x_coord, rcvr_y_coord) )
            # elif self.combobox_grid_metric.get() == "dBA":
            #     grd_rcvr[2] = str(round(_get_dBA(rcvr_x_coord, rcvr_y_coord), 1 ) )
            # else:
            #     print(self.combobox_grid_metric.get())
            #     raise ValueError("No metric selected")


        # colorscale = [x for x in range(25, 65, 5)]
        # colorlist = [
        #     "green3",
        #     "blue",
        #     "yellow3",
        #     "DarkOrange1",
        #     "OrangeRed2",
        #     "maroon2",
        #     "purple",
        #     "cyan3",
        # ]
        self.parent.func_vars.grid_receiver_coords = grid_receiver_list.copy()
        self.parent.editor.full_redraw()
        # for grid_rcvr in grid_receiver_list:
        #     x = self.parent.editor.world_to_px(grid_rcvr[0])
        #     y = self.parent.editor.world_to_px(grid_rcvr[1])
        #     level = grid_rcvr[2]
        #     textcolor = "black"
        #     consider_level = int(round(float(level), 0))
        #     for colorrange, color in zip(colorscale, colorlist):
        #         if consider_level >= colorrange:
        #             textcolor = color

        #     # gr_id = ",".join(grid_rcvr)
        #     gr_id = self.parent.editor.canvas.create_text(
        #         (x, y),
        #         # tag=gr_id,
        #         text=str(consider_level),
        #         font=GRID_FONT,
        #         fill=textcolor,
        #     )
        #     self.parent.func_vars.grid_receivers_on_canvas.append(gr_id)

    def set_scale(self):
        self.parent.editor.canvas.bind(
            "<ButtonPress-1>", self.parent.editor.setting_scale_leftMouseClick
        )
        self.parent.editor.canvas.bind(
            "<B1-Motion>", self.parent.editor.setting_scale_leftMouseMove
        )
        self.parent.editor.canvas.bind(
            "<ButtonRelease-1>", self.parent.editor.setting_scale_leftMouseRelease
        )

        self.parent.pane_eqmt_info.status_label.configure(text="Status: Setting Scale")
        self.parent.pane_eqmt_info.entryBox1.delete(0, "end")
        self.parent.pane_eqmt_info.entryBox1.insert(0, "distance (ft)")
        self.parent.pane_eqmt_info.entryBox1.focus()

    def draw_equipment(self):
        self.parent.editor.canvas.bind(
            "<ButtonPress-1>", self.parent.editor.drawing_eqmt_leftMouseClick
        )
        self.parent.editor.canvas.bind(
            "<B1-Motion>", self.parent.editor.drawing_eqmt_leftMouseMove
        )
        self.parent.editor.canvas.bind(
            "<ButtonRelease-1>", self.parent.editor.drawing_eqmt_leftMouseRelease
        )

        self.parent.pane_eqmt_info.status_label.configure(
            text="Status: Drawing Equipment"
        )

    def draw_receiver(self):
        self.parent.editor.canvas.bind(
            "<ButtonPress-1>", self.parent.editor.drawing_rcvr_leftMouseClick
        )
        self.parent.editor.canvas.bind(
            "<B1-Motion>", self.parent.editor.drawing_rcvr_leftMouseMove
        )
        self.parent.editor.canvas.bind(
            "<ButtonRelease-1>", self.parent.editor.drawing_rcvr_leftMouseRelease
        )
        self.parent.pane_eqmt_info.status_label.configure(
            text="Status: Drawing Receiver"
        )

    def draw_barrier(self):
        self.parent.editor.canvas.bind(
            "<ButtonPress-1>", self.parent.editor.drawing_barrier_leftMouseClick
        )
        self.parent.editor.canvas.bind(
            "<B1-Motion>", self.parent.editor.drawing_barrier_leftMouseMove
        )
        self.parent.editor.canvas.bind(
            "<ButtonRelease-1>", self.parent.editor.drawing_barrier_leftMouseRelease
        )
        self.parent.pane_eqmt_info.status_label.configure(
            text="Status: Drawing Barrier"
        )

    def measure(self):
        self.parent.editor.canvas.bind(
            "<ButtonPress-1>", self.parent.editor.measureing_leftMouseClick
        )
        self.parent.editor.canvas.bind(
            "<B1-Motion>", self.parent.editor.measureing_leftMouseMove
        )
        self.parent.editor.canvas.bind(
            "<ButtonRelease-1>", self.parent.editor.measureing_leftMouseRelease
        )
        self.parent.pane_eqmt_info.status_label.configure(text="Status: Measuring")


class Pane_Eqmt_Info(tk.Frame):
    def __init__(self, parent):
        tk.Frame.__init__(self, parent)
        self.parent = parent
        self.update_est_noise_levels()

        self.myFont = tk.font.nametofont("TkTextFont")

        self.entryBox1 = tk.Entry(self, font=(None, 15), width=36)
        self.entryBox1.insert(0, "input scale & eqmt_tag names here prior to setting")
        self.entryBox1.bind("<FocusIn>", self.entryBox1_select_all)
        self.entryBox1.bind("<Return>", self.entryBox1_unfocus)

        scaleIndicatorLabelText = (
            "Scale: "
            + str(round(self.parent.func_vars.scale_line_distance_px, 0))
            + " px = "
            + str(self.parent.func_vars.known_distance_ft)
            + " ft"
        )

        self.exportList_button = tk.Button(
            self,
            text="Export Tag List",
            command=self.onExportListButton,
            font=(None, 15),
        )
        self.scaleIndicatorLabel = tk.Label(
            self,
            text=scaleIndicatorLabelText,
            borderwidth=2,
            relief="solid",
            font=(None, 15),
        )
        self.status_label = tk.Label(
            self, text="Status: Idle", borderwidth=2, relief="solid", font=(None, 15)
        )
        self.measurement_label = tk.Label(
            self, text="Measurement: ", borderwidth=2, relief="solid", font=(None, 15)
        )
        self.equipment_list_label = tk.Label(self, text="Equipment", font=(None, 15))
        self.receiver_list_label = tk.Label(self, text="Receivers", font=(None, 15))
        self.barrier_list_label = tk.Label(self, text="Barriers", font=(None, 15))
        self.ignore_matrix_label = tk.Label(self, text="Ignore", font=(None, 15))
        self.directivity_matrix_label = tk.Label(
            self, text="Directivity", font=(None, 15)
        )
        self.specific_bar_matrix_label = tk.Label(
            self, text="Specific Barrier", font=(None, 15)
        )
        self.generateEqmtTree()
        self.generateRcvrTree()
        self.generateBarrierTree()
        self.generateIgnoreMatrixTree()
        self.generateDirectivityMatrixTree()
        self.generateSpecificBarrerMatrixTree()

        self.equipment_tree.bind("<Double-1>", self.open_item_editor_window)
        self.receiver_tree.bind("<Double-1>", self.open_item_editor_window)
        self.barrier_tree.bind("<Double-1>", self.open_item_editor_window)
        self.deselect_item_from_trees()

        self.entryBox1.grid(row=0, column=0, padx=0, pady=0, sticky=tk.N + tk.W)
        self.exportList_button.grid(row=1, column=0, padx=0, pady=0, sticky=tk.N + tk.W)
        self.scaleIndicatorLabel.grid(
            row=2, column=0, padx=0, pady=0, sticky=tk.N + tk.W
        )
        self.status_label.grid(row=3, column=0, padx=0, pady=0, sticky=tk.N + tk.W)
        self.measurement_label.grid(row=4, column=0, padx=0, pady=0, sticky=tk.N + tk.W)

        self.equipment_list_label.grid(
            row=5, column=0, padx=0, pady=10, sticky=tk.N + tk.W
        )
        self.equipment_tree.grid(
            row=6, column=0, padx=0, pady=0, columnspan=3, sticky=tk.N + tk.W
        )

        self.receiver_list_label.grid(
            row=7, column=0, padx=0, pady=10, sticky=tk.N + tk.W
        )
        self.receiver_tree.grid(row=8, column=0, padx=0, pady=0, sticky=tk.N + tk.W)
        self.ignore_matrix_label.grid(
            row=7, column=1, padx=0, pady=10, sticky=tk.N + tk.W
        )
        self.ignore_matrix_tree.grid(
            row=8, column=1, padx=10, pady=0, sticky=tk.N + tk.W
        )

        self.barrier_list_label.grid(
            row=9, column=0, padx=10, pady=10, sticky=tk.N + tk.W
        )
        self.barrier_tree.grid(row=10, column=0, padx=10, pady=0, sticky=tk.N + tk.W)
        self.directivity_matrix_label.grid(
            row=9, column=1, padx=10, pady=10, sticky=tk.N + tk.W
        )
        self.directivity_matrix_tree.grid(
            row=10, column=1, padx=10, pady=0, sticky=tk.N + tk.W
        )
        self.specific_bar_matrix_label.grid(
            row=9, column=2, padx=10, pady=10, sticky=tk.N + tk.W
        )
        self.specific_bar_matrix_tree.grid(
            row=10, column=2, padx=10, pady=0, sticky=tk.N + tk.W
        )

    def generateEqmtTree(self):
        try:  # delete tree if already exists
            self.equipment_tree.delete(*self.equipment_tree.get_children())
            self.equipment_tree_rows = []
            for i in self.parent.func_vars.equipment_list:
                self.equipment_tree_rows.append(
                    [
                        round(i.count, 2),
                        i.eqmt_tag,
                        i.path,
                        i.make,
                        i.model,
                        round(i.sound_level, 1),
                        round(i.sound_ref_dist, 2),
                        round(i.tested_q, 1),
                        round(i.installed_q, 1),
                        round(i.insertion_loss, 1),
                        round(i.x_coord, 2),
                        round(i.y_coord, 2),
                        round(i.z_coord, 2),
                    ]
                )

            for i, value in enumerate(self.equipment_tree_rows):
                self.equipment_tree.insert("", "end", values=value, tags=self.myFont)

        except AttributeError:
            self.equipment_tree_columns = [
                "count",
                "tag",
                "path",
                "make",
                "model",
                "sound_level",
                "sound_ref_dist",
                "Q (tested)",
                "Q (installed)",
                "IL",
                "x",
                "y",
                "z",
            ]
            self.equipment_tree_rows = []
            self.maxWidths = []

            # create widths
            for item in self.equipment_tree_columns:
                self.maxWidths.append(self.myFont.measure(str(item)))

            # create wors with eqmt data
            for i in self.parent.func_vars.equipment_list:
                self.equipment_tree_rows.append(
                    [
                        round(i.count, 2),
                        i.eqmt_tag,
                        i.path,
                        i.make,
                        i.model,
                        round(i.sound_level, 1),
                        round(i.sound_ref_dist, 2),
                        round(i.tested_q, 1),
                        round(i.installed_q, 1),
                        round(i.insertion_loss, 1),
                        round(i.x_coord, 2),
                        round(i.y_coord, 2),
                        round(i.z_coord, 2),
                    ]
                )

            # getting max widths
            for col_idx in range(len(self.equipment_tree_rows[0])):
                maxWidth = self.maxWidths[col_idx]
                for row in self.equipment_tree_rows:
                    try:
                        currentWidth = self.myFont.measure(
                            str(round(float(row[col_idx])))
                        )
                    except ValueError:
                        currentWidth = self.myFont.measure(str(row[col_idx]))
                    if currentWidth > maxWidth:
                        maxWidth = currentWidth
                self.maxWidths[col_idx] = maxWidth

            # initialize tree
            self.equipment_tree = tk.ttk.Treeview(
                self, columns=self.equipment_tree_columns, show="headings"
            )

            # add rows and colmns to tree
            for col, maxWidth in zip(self.equipment_tree_columns, self.maxWidths):
                self.equipment_tree.heading(col, text=col)
                self.equipment_tree.column(
                    col, minwidth=15, width=maxWidth + 25, stretch=0
                )
            for i, value in enumerate(self.equipment_tree_rows):
                self.equipment_tree.insert("", "end", values=value, tags=self.myFont)
                # sizing
                if i == len(self.equipment_tree_rows) - 1:
                    for col in self.equipment_tree_columns:
                        if col in ("eqmt_tag", "model"):
                            width_mult = 10
                            self.equipment_tree.column(
                                col,
                                minwidth=20,
                                width=len(value) * width_mult,
                                stretch=0,
                            )

    def generateRcvrTree(self):
        try:  # delete tree if already exists
            self.receiver_tree.delete(*self.receiver_tree.get_children())
            self.receiver_tree_rows = []
            for i in self.parent.func_vars.receiver_list:
                self.receiver_tree_rows.append(
                    [
                        i.r_name,
                        round(i.x_coord, 2),
                        round(i.y_coord, 2),
                        round(i.z_coord, 2),
                        round(i.sound_limit, 1),
                        round(i.predicted_sound_level, 1),
                    ]
                )
            for i, value in enumerate(self.receiver_tree_rows):
                self.receiver_tree.insert("", "end", values=value, tags=self.myFont)

        except AttributeError:
            self.receiver_tree_columns = [
                "R#",
                "x",
                "y",
                "z",
                "dBA limit",
                "est. level",
            ]
            self.receiver_tree_rows = []
            self.maxWidths = []

            # create widths
            for item in self.receiver_tree_columns:
                self.maxWidths.append(self.myFont.measure(str(item)))

            # create rows with rcvr data
            for i in self.parent.func_vars.receiver_list:
                self.receiver_tree_rows.append(
                    [
                        i.r_name,
                        round(i.x_coord, 2),
                        round(i.y_coord, 2),
                        round(i.z_coord, 2),
                        round(i.sound_limit, 1),
                        round(i.predicted_sound_level, 1),
                    ]
                )
            print(self.receiver_tree_rows)

            # getting max widths
            for col_idx in range(len(self.receiver_tree_rows[0])):
                maxWidth = self.maxWidths[col_idx]
                for row in self.receiver_tree_rows:
                    currentWidth = self.myFont.measure(str(row[col_idx]))
                    if currentWidth > maxWidth:
                        maxWidth = currentWidth
                self.maxWidths[col_idx] = maxWidth

            # initializing receiver tree
            self.receiver_tree = tk.ttk.Treeview(
                self, columns=self.receiver_tree_columns, show="headings"
            )

            # adding columns and rows
            for col, maxWidth in zip(self.receiver_tree_columns, self.maxWidths):
                self.receiver_tree.heading(col, text=col)
                self.receiver_tree.column(
                    col, minwidth=15, width=maxWidth + 25, stretch=0
                )
            for i, value in enumerate(self.receiver_tree_rows):
                self.receiver_tree.insert("", "end", values=value, tags=self.myFont)

    def generateBarrierTree(self):
        try:  # delete tree if already exists
            self.barrier_tree.delete(*self.barrier_tree.get_children())
            self.barrier_tree_rows = []
            for i in self.parent.func_vars.barrier_list:
                self.barrier_tree_rows.append(
                    [
                        i.barrier_name,
                        round(i.x0_coord, 2),
                        round(i.y0_coord, 2),
                        round(i.z0_coord, 2),
                        round(i.x1_coord, 2),
                        round(i.y1_coord, 2),
                        round(i.z1_coord, 2),
                    ]
                )
            for i, value in enumerate(self.barrier_tree_rows):
                self.barrier_tree.insert("", "end", values=value, tags=self.myFont)

        except AttributeError:
            self.barrier_tree_columns = [
                "barrier_name",
                "x0",
                "y0",
                "z0",
                "x1",
                "y1",
                "z1",
            ]
            self.barrier_tree_rows = []
            self.maxWidths = []

            # create widths
            for item in self.barrier_tree_columns:
                self.maxWidths.append(self.myFont.measure(str(item)))

            # create rows with barrier data
            for i in self.parent.func_vars.barrier_list:
                self.barrier_tree_rows.append(
                    [
                        i.barrier_name,
                        round(i.x0_coord, 2),
                        round(i.y0_coord, 2),
                        round(i.z0_coord, 2),
                        round(i.x1_coord, 2),
                        round(i.y1_coord, 2),
                        round(i.z1_coord, 2),
                    ]
                )

            # getting max widths
            for col_idx in range(len(self.barrier_tree_rows[0])):
                maxWidth = self.maxWidths[col_idx]
                for row in self.barrier_tree_rows:
                    currentWidth = self.myFont.measure(str(row[col_idx]))
                    if currentWidth > maxWidth:
                        maxWidth = currentWidth
                self.maxWidths[col_idx] = maxWidth

            # initializing barrier tree
            self.barrier_tree = tk.ttk.Treeview(
                self, columns=self.barrier_tree_columns, show="headings"
            )

            # adding columns and rows
            for col, maxWidth in zip(self.barrier_tree_columns, self.maxWidths):
                self.barrier_tree.heading(col, text=col)
                self.barrier_tree.column(
                    col, minwidth=15, width=maxWidth + 25, stretch=0
                )
            for i, value in enumerate(self.barrier_tree_rows):
                self.barrier_tree.insert("", "end", values=value, tags=self.myFont)

        self.equipment_tree.bind("<ButtonRelease-1>", self.select_item_from_eqmt_tree)
        self.receiver_tree.bind("<ButtonRelease-1>", self.select_item_from_rcvr_tree)
        self.barrier_tree.bind("<ButtonRelease-1>", self.select_item_from_barrier_tree)

    def generateIgnoreMatrixTree(self):
        # todo need to add the eqmt label to the tree
        self.ignore_matrix_tree_columns = ["eqmt"]
        for rcvr in self.parent.func_vars.receiver_list:
            self.ignore_matrix_tree_columns.append(str(rcvr.r_name))
        self.ignore_matrix_tree_rows = []
        for eqmt, ignore_list in zip(
            self.parent.func_vars.equipment_list, self.parent.func_vars.ignore_matrix
        ):
            self.ignore_matrix_tree_rows.append([eqmt.eqmt_tag] + ignore_list.copy())
        self.maxWidths = []

        # create widths
        for item in self.ignore_matrix_tree_columns:
            self.maxWidths.append(self.myFont.measure(str(item)))

        # getting max widths
        for col_idx in range(len(self.ignore_matrix_tree_rows[0])):
            maxWidth = self.maxWidths[col_idx]
            for row in self.ignore_matrix_tree_rows:
                currentWidth = self.myFont.measure(str(row[col_idx]))
                if currentWidth > maxWidth:
                    maxWidth = currentWidth
            self.maxWidths[col_idx] = maxWidth

        # initializing barrier tree
        self.ignore_matrix_tree = tk.ttk.Treeview(
            self, columns=self.ignore_matrix_tree_columns, show="headings"
        )

        # adding columns and rows
        for i, col in enumerate(self.ignore_matrix_tree_columns):
            self.ignore_matrix_tree.heading(col, text=col)
            if i == 0:
                self.ignore_matrix_tree.column(
                    col, minwidth=5, width=maxWidth + 85, stretch=0
                )
            else:
                self.ignore_matrix_tree.column(
                    col, minwidth=5, width=maxWidth + 5, stretch=0
                )

        for i, row in enumerate(self.ignore_matrix_tree_rows):
            txt = [x if x != None else "_" for x in row]
            self.ignore_matrix_tree.insert("", "end", values=txt, tags=self.myFont)

    def generateDirectivityMatrixTree(self):
        # todo need to add the eqmt label to the tree
        self.dir_matrix_tree_columns = ["eqmt"]
        for rcvr in self.parent.func_vars.receiver_list:
            self.dir_matrix_tree_columns.append(str(rcvr.r_name))
        self.dir_matrix_tree_rows = []
        for eqmt, dir_list in zip(
            self.parent.func_vars.equipment_list,
            self.parent.func_vars.directivity_matrix,
        ):
            self.dir_matrix_tree_rows.append([eqmt.eqmt_tag] + dir_list.copy())
        self.maxWidths = []

        # create widths
        for item in self.dir_matrix_tree_columns:
            self.maxWidths.append(self.myFont.measure(str(item)))

        # getting max widths
        for col_idx in range(len(self.dir_matrix_tree_rows[0])):
            maxWidth = self.maxWidths[col_idx]
            for row in self.dir_matrix_tree_rows:
                currentWidth = self.myFont.measure(str(row[col_idx]))
                if currentWidth > maxWidth:
                    maxWidth = currentWidth
            self.maxWidths[col_idx] = maxWidth

        # initializing dir tree
        self.directivity_matrix_tree = tk.ttk.Treeview(
            self, columns=self.dir_matrix_tree_columns, show="headings"
        )

        # adding columns and rows
        for i, col in enumerate(self.dir_matrix_tree_columns):
            self.directivity_matrix_tree.heading(col, text=col)
            if i == 0:
                self.directivity_matrix_tree.column(
                    col, minwidth=25, width=maxWidth + 85, stretch=0
                )
            else:
                self.directivity_matrix_tree.column(
                    col, minwidth=25, width=maxWidth + 5, stretch=0
                )

        for i, row in enumerate(self.dir_matrix_tree_rows):
            txt = [x if x != 0 else "_" for x in row]
            self.directivity_matrix_tree.insert("", "end", values=txt, tags=self.myFont)

    def generateSpecificBarrerMatrixTree(self):
        # todo need to add the eqmt label to the tree
        self.specbar_matrix_tree_columns = ["eqmt"]
        for rcvr in self.parent.func_vars.receiver_list:
            self.specbar_matrix_tree_columns.append(str(rcvr.r_name))
        self.specbar_matrix_tree_rows = []
        for eqmt, dir_list in zip(
            self.parent.func_vars.equipment_list,
            self.parent.func_vars.specific_bar_matrix,
        ):
            self.specbar_matrix_tree_rows.append([eqmt.eqmt_tag] + dir_list.copy())
        self.maxWidths = []

        # create widths
        for item in self.specbar_matrix_tree_columns:
            self.maxWidths.append(self.myFont.measure(str(item)))

        # getting max widths
        for col_idx in range(len(self.specbar_matrix_tree_rows[0])):
            maxWidth = self.maxWidths[col_idx]
            for row in self.specbar_matrix_tree_rows:
                currentWidth = self.myFont.measure(str(row[col_idx]))
                if currentWidth > maxWidth:
                    maxWidth = currentWidth
            self.maxWidths[col_idx] = maxWidth

        # initializing dir tree
        self.specific_bar_matrix_tree = tk.ttk.Treeview(
            self, columns=self.specbar_matrix_tree_columns, show="headings"
        )

        # adding columns and rows
        for i, col in enumerate(self.specbar_matrix_tree_columns):
            self.specific_bar_matrix_tree.heading(col, text=col)
            if i == 0:
                self.specific_bar_matrix_tree.column(
                    col, minwidth=25, width=maxWidth + 85, stretch=0
                )
            else:
                self.specific_bar_matrix_tree.column(
                    col, minwidth=25, width=maxWidth + 5, stretch=0
                )

        for i, row in enumerate(self.specbar_matrix_tree_rows):
            txt = [x if x is not None else "_" for x in row]
            self.specific_bar_matrix_tree.insert(
                "", "end", values=txt, tags=self.myFont
            )

    def ARI_interpolation(self, pld, lowerIL, upperIL, lowerPLD, upperPLD):
        diff_in_reduction = (pld - lowerPLD) / (upperPLD - lowerPLD)
        change_IL = upperIL - lowerIL
        barrier_IL = lowerIL + change_IL * diff_in_reduction
        return int(round(barrier_IL, 0))

    def ARI_barrier_IL_calc(
        self,
        eqmt_x,
        eqmt_y,
        eqmt_z,
        bar_x0,
        bar_y0,
        bar_z0,
        bar_x1,
        bar_y1,
        bar_z1,
        rcvr_x,
        rcvr_y,
        rcvr_z,
    ):
        # fixing escape on error with same barrier coordinate or same eqmt/receiver x/y
        if eqmt_x == rcvr_x:
            eqmt_x += 0.0001
            # print("corrected eqmt_x==rcvr_x error")
        if eqmt_y == rcvr_y:
            eqmt_y += 0.0001
            # print("corrected eqmt_y==rcvr_y error")
        if bar_x0 == bar_x1:
            bar_x0 += 0.0001
            # print("corrected bar_x0==bar_x1 error")
        if bar_y0 == bar_y1:
            bar_y0 += 0.0001
            # print("corrected bar_y0==bar_y1 error")
        # testing if line of sight is broken along HORIZONTAL plane
        eqmt_point = utils.Point(eqmt_x, eqmt_y)
        receiver_point = utils.Point(rcvr_x, rcvr_y)
        bar_start_point = utils.Point(bar_x0, bar_y0)
        bar_end_point = utils.Point(bar_x1, bar_y1)
        if not utils.doIntersect(
            eqmt_point, receiver_point, bar_start_point, bar_end_point
        ):
            # print("barrier fails horizontal test")
            return 0

        try:
            m_source2receiver = (rcvr_y - eqmt_y) / (rcvr_x - eqmt_x)
        except ZeroDivisionError:
            return 0
        try:
            m_bar_start2end = (bar_y0 - bar_y1) / (bar_x0 - bar_x1)
        except ZeroDivisionError:
            return 0

        b_source2receiver = eqmt_y - (eqmt_x * m_source2receiver)
        b_bar_start2end = bar_y0 - (bar_x0 * m_bar_start2end)
        intersection_x = (b_bar_start2end - b_source2receiver) / (
            m_source2receiver - m_bar_start2end
        )
        intersection_y = m_source2receiver * intersection_x + b_source2receiver

        bar_min_z = min(bar_z0, bar_z1)
        bar_height_difference = abs(bar_z0 - bar_z1)
        bar_length = utils.distance_formula(x0=bar_x0, y0=bar_y0, x1=bar_x1, y1=bar_y1)
        bar_slope = bar_height_difference / bar_length
        if bar_z0 <= bar_z1:
            bar_dist2barxpoint = utils.distance_formula(
                x0=intersection_x, y0=intersection_y, x1=bar_x0, y1=bar_y0
            )
        else:
            bar_dist2barxpoint = utils.distance_formula(
                x0=intersection_x, y0=intersection_y, x1=bar_x1, y1=bar_y1
            )

        bar_height_to_use = bar_slope * bar_dist2barxpoint + bar_min_z

        # testing if line of sight is broken vertically
        if bar_height_to_use < eqmt_z and bar_height_to_use < rcvr_z:
            # print("barrier fails easy vertical test")
            return 0

        distance_source2receiver_horizontal = utils.distance_formula(
            x0=eqmt_x, y0=eqmt_y, x1=rcvr_x, y1=rcvr_y
        )
        distance_source2bar_horizontal = utils.distance_formula(
            x0=eqmt_x, y0=eqmt_y, x1=intersection_x, y1=intersection_y
        )
        distance_barrier2receiever_straight = (
            distance_source2receiver_horizontal - distance_source2bar_horizontal
        )
        distance_source2receiver_propogation = math.sqrt(
            distance_source2receiver_horizontal**2 + (rcvr_z - eqmt_z) ** 2
        )
        distance_source2barrier_top = math.sqrt(
            (bar_height_to_use - eqmt_z) ** 2 + distance_source2bar_horizontal**2
        )
        distance_receiver2barrier_top = math.sqrt(
            (bar_height_to_use - rcvr_z) ** 2 + distance_barrier2receiever_straight**2
        )
        path_length_difference = (
            distance_source2barrier_top
            + distance_receiver2barrier_top
            - distance_source2receiver_propogation
        )

        # testing if line of sight is broken along VERTICAL plane
        eqmt_point = utils.Point(0, eqmt_z)
        receiver_point = utils.Point(distance_source2receiver_horizontal, rcvr_z)
        bar_start_point = utils.Point(distance_source2bar_horizontal, 0)
        bar_end_point = utils.Point(distance_source2bar_horizontal, bar_height_to_use)
        if not utils.doIntersect(
            eqmt_point, receiver_point, bar_start_point, bar_end_point
        ):
            # print("barrier fails vertical test")
            return 0

        pld = path_length_difference
        if 0 < pld and pld <= 0.5:
            barrier_IL = self.ARI_interpolation(pld, 0, 4, 0, 0.5)
        elif 0.5 < pld and pld <= 1:
            barrier_IL = self.ARI_interpolation(pld, 4, 7, 0.5, 1)
        elif 1 < pld and pld <= 2:
            barrier_IL = self.ARI_interpolation(pld, 7, 10, 1, 2)
        elif 2 < pld and pld <= 3:
            barrier_IL = self.ARI_interpolation(pld, 10, 12, 2, 3)
        elif 3 < pld and pld <= 6:
            barrier_IL = self.ARI_interpolation(pld, 12, 15, 3, 6)
        elif 6 < pld and pld <= 12:
            barrier_IL = self.ARI_interpolation(pld, 15, 17, 6, 12)
        elif 12 < pld:
            barrier_IL = 17
        else:
            barrier_IL = 0

        return [
            barrier_IL,
            bar_height_to_use,
            distance_source2receiver_horizontal,
            distance_source2bar_horizontal,
            distance_source2barrier_top,
            distance_receiver2barrier_top,
            distance_source2receiver_propogation,
            path_length_difference,
            "ARI",
        ]

    def OB_fresnel_barrier_IL_calc(
        self,
        eqmt_x,
        eqmt_y,
        eqmt_z,
        hz63,
        hz125,
        hz250,
        hz500,
        hz1000,
        hz2000,
        hz4000,
        hz8000,
        eqmt_level,
        bar_x0,
        bar_y0,
        bar_z0,
        bar_x1,
        bar_y1,
        bar_z1,
        rcvr_x,
        rcvr_y,
        rcvr_z,
    ):
        # fixing escape on error with same barrier coordinate
        if bar_x0 == bar_x1:
            bar_x0 += 0.0001
            # print("corrected bar_x0==bar_x1 error")
        if bar_y0 == bar_y1:
            bar_y0 += 0.0001
            # print("corrected bar_y0==bar_y1 error")
        ob_levels_list = [hz63, hz125, hz250, hz500, hz1000, hz2000, hz4000, hz8000]
        ob_bands_list = [63, 125, 250, 500, 1000, 2000, 4000, 8000]
        # testing if line of sight is broken along horizontal plane
        eqmt_point = utils.Point(eqmt_x, eqmt_y)
        receiver_point = utils.Point(rcvr_x, rcvr_y)
        bar_start_point = utils.Point(bar_x0, bar_y0)
        bar_end_point = utils.Point(bar_x1, bar_y1)
        if not utils.doIntersect(
            eqmt_point, receiver_point, bar_start_point, bar_end_point
        ):
            # print("barrier fails horizontal test")
            return 0
        try:
            m_source2receiver = (rcvr_y - eqmt_y) / (rcvr_x - eqmt_x)
        except ZeroDivisionError:
            return 0
        try:
            m_bar_start2end = (bar_y0 - bar_y1) / (bar_x0 - bar_x1)
        except ZeroDivisionError:
            return 0

        b_source2receiver = eqmt_y - (eqmt_x * m_source2receiver)
        b_bar_start2end = bar_y0 - (bar_x0 * m_bar_start2end)
        intersection_x = (b_bar_start2end - b_source2receiver) / (
            m_source2receiver - m_bar_start2end
        )
        intersection_y = m_source2receiver * intersection_x + b_source2receiver

        bar_min_z = min(bar_z0, bar_z1)
        bar_height_difference = abs(bar_z0 - bar_z1)
        bar_length = utils.distance_formula(x0=bar_x0, y0=bar_y0, x1=bar_x1, y1=bar_y1)
        bar_slope = bar_height_difference / bar_length
        if bar_z0 <= bar_z1:
            bar_dist2barxpoint = utils.distance_formula(
                x0=intersection_x, y0=intersection_y, x1=bar_x0, y1=bar_y0
            )
        else:
            bar_dist2barxpoint = utils.distance_formula(
                x0=intersection_x, y0=intersection_y, x1=bar_x1, y1=bar_y1
            )

        bar_height_to_use = bar_slope * bar_dist2barxpoint + bar_min_z

        # testing if line of sight is broken vertically
        if bar_height_to_use < eqmt_z and bar_height_to_use < rcvr_z:
            # print("barrier fails easy vertical test")
            return 0

        distance_source2receiver_horizontal = utils.distance_formula(
            x0=eqmt_x, y0=eqmt_y, x1=rcvr_x, y1=rcvr_y
        )
        distance_source2bar_horizontal = utils.distance_formula(
            x0=eqmt_x, y0=eqmt_y, x1=intersection_x, y1=intersection_y
        )
        distance_barrier2receiever_straight = (
            distance_source2receiver_horizontal - distance_source2bar_horizontal
        )
        distance_source2receiver_propogation = math.sqrt(
            distance_source2receiver_horizontal**2 + (rcvr_z - eqmt_z) ** 2
        )
        distance_source2barrier_top = math.sqrt(
            (bar_height_to_use - eqmt_z) ** 2 + distance_source2bar_horizontal**2
        )
        distance_receiver2barrier_top = math.sqrt(
            (bar_height_to_use - rcvr_z) ** 2 + distance_barrier2receiever_straight**2
        )
        path_length_difference = (
            distance_source2barrier_top
            + distance_receiver2barrier_top
            - distance_source2receiver_propogation
        )

        # testing if line of sight is broken along VERTICAL plane
        eqmt_point = utils.Point(0, eqmt_z)
        receiver_point = utils.Point(distance_source2receiver_horizontal, rcvr_z)
        bar_start_point = utils.Point(distance_source2bar_horizontal, 0)
        bar_end_point = utils.Point(distance_source2bar_horizontal, bar_height_to_use)
        if not utils.doIntersect(
            eqmt_point, receiver_point, bar_start_point, bar_end_point
        ):
            # print("barrier fails vertical test")
            return 0

        speed_of_sound = 1128
        fresnel_num_list = [
            (2 * path_length_difference) / (speed_of_sound / ob) for ob in ob_bands_list
        ]

        line_point_correction = (
            0  # assume no line/point source correction 0 for point, -5 for line
        )
        barrier_finite_infinite_correction = 1.0  # assume infinite barrier see Mehta for correction under finite barrier.
        Kb_barrier_constant = 5  # assume Kb (barrier constant) for wall = 5, berm = 8
        barrier_attenuate_limit = 20  # wall limit = 20 berm limit = 23

        ob_barrier_attenuation_list = []
        for N in fresnel_num_list:
            n_d = math.sqrt(2 * math.pi * N)
            ob_barrier_attenuation = (
                (20 * math.log10(n_d / math.tanh(n_d)))
                + Kb_barrier_constant
                + line_point_correction
            ) ** barrier_finite_infinite_correction

            if ob_barrier_attenuation > barrier_attenuate_limit:
                ob_barrier_attenuation = barrier_attenuate_limit
            ob_barrier_attenuation_list.append(ob_barrier_attenuation)

        ob_attenuated_levels_list = [
            x - y for x, y in zip(ob_levels_list, ob_barrier_attenuation_list)
        ]
        ob_a_weighting_list = [-26.2, -16.1, -8.6, -3.2, -0, 1.2, 1, -1.1]
        ob_attenuated_aweighted_levels_list = [
            x + y for x, y in zip(ob_attenuated_levels_list, ob_a_weighting_list)
        ]

        attenuated_aweighted_level = acoustics.decibel.dbsum(
            ob_attenuated_aweighted_levels_list
        )

        barrier_IL = eqmt_level - attenuated_aweighted_level

        return [
            round(barrier_IL, 1),
            bar_height_to_use,
            distance_source2receiver_horizontal,
            distance_source2bar_horizontal,
            distance_source2barrier_top,
            distance_receiver2barrier_top,
            distance_source2receiver_propogation,
            path_length_difference,
            "OB-Fresnel",
        ]

    def spec_bar_check(self, b, e_idx, r_idx):
        bar_mat_cur_line = self.parent.func_vars.specific_bar_matrix[e_idx][r_idx]
        if bar_mat_cur_line is None:
            return False
        bar_mat_cur_line = [x.strip() for x in bar_mat_cur_line.split(",")]
        # SAFETY NET: check that all spec'd bars are actually listed
        real_bars = set([x.barrier_name for x in self.parent.func_vars.barrier_list])
        all_bars = set(bar_mat_cur_line) | real_bars
        if len(all_bars) != len(self.parent.func_vars.barrier_list):
            e = self.parent.func_vars.equipment_list[e_idx].eqmt_tag
            r = self.parent.func_vars.receiver_list[r_idx].r_name
            raise NameError(
                f"this spec'd bar doesn't exist: {all_bars - real_bars} shown for {e}, {r}"
            )
        if b.barrier_name not in bar_mat_cur_line:
            return False
        return True

    def update_est_noise_levels(self):
        barrierListForExcelOutput_curData = []
        self.barrierListForExcelOutput = [
            [
                "barrier loss",
                "eqmt",
                "rcvr",
                "bar",
                "eqmt height",
                "rcvr height",
                "bar height",
                "source to receiver",
                "source to bar (ft)",
                "source to bar top",
                "rcvr to bar top",
                "direct path",
                "PLD",
                "Barrier method",
                "noise data (if OB Fresnel used)",
            ]
        ]
        for rcvr_index, rcvr in enumerate(self.parent.func_vars.receiver_list):
            print(
                f"r_name: {rcvr.r_name} x: {rcvr.x_coord}, y: {rcvr.y_coord}, z: {rcvr.z_coord}"
            )
            sound_pressure = 0
            for eqmt_index, eqmt in enumerate(self.parent.func_vars.equipment_list):
                if self.parent.func_vars.ignore_matrix[eqmt_index][rcvr_index] == None:
                    if eqmt.sound_ref_dist == 0:
                        sound_power = eqmt.sound_level + 10 * math.log10(eqmt.count)
                    else:
                        q = eqmt.tested_q  # need to update this
                        r = eqmt.sound_ref_dist * 0.308
                        lp = eqmt.sound_level
                        b = q / (4 * math.pi * r**2)
                        sound_power = (
                            lp + abs(10 * math.log10(b)) + 10 * math.log10(eqmt.count)
                        )
                    distance = math.sqrt(
                        (rcvr.x_coord - eqmt.x_coord) ** 2
                        + (rcvr.y_coord - eqmt.y_coord) ** 2
                        + (rcvr.z_coord - eqmt.z_coord) ** 2
                    )
                    try:
                        directivity_loss = self.parent.func_vars.directivity_matrix[
                            eqmt_index
                        ][rcvr_index]
                        q = eqmt.installed_q
                        r = distance * 0.308
                        attenuation = abs(10 * math.log10(q / (4 * math.pi * r**2)))
                        used_barrier_name = None
                        used_barrier_obj = None
                        barrier_IL = 0
                        if (
                            TAKE_ARI_BARRIER == True
                            and TAKE_OB_FRESNAL_BARRIER == False
                        ):
                            for bar in self.parent.func_vars.barrier_list:
                                if (
                                    self.parent.func_vars.use_specific_bar_bool.get()
                                    is True
                                    and self.spec_bar_check(bar, eqmt_index, rcvr_index)
                                    is False
                                ):
                                    continue
                                barrier_info_list = self.ARI_barrier_IL_calc(
                                    eqmt.x_coord,
                                    eqmt.y_coord,
                                    eqmt.z_coord,
                                    bar.x0_coord,
                                    bar.y0_coord,
                                    bar.z0_coord,
                                    bar.x1_coord,
                                    bar.y1_coord,
                                    bar.z1_coord,
                                    rcvr.x_coord,
                                    rcvr.y_coord,
                                    rcvr.z_coord,
                                )
                                barrier_IL_test = (
                                    barrier_info_list[0]
                                    if barrier_info_list != 0
                                    else 0
                                )
                                if barrier_IL_test > barrier_IL:
                                    barrier_IL = barrier_IL_test
                                    used_barrier_name = str(bar.barrier_name + " - ari")
                                    used_barrier_obj = bar
                                    barrierListForExcelOutput_curData = (
                                        [
                                            barrier_IL,
                                            eqmt.eqmt_tag,
                                            rcvr.r_name,
                                            bar.barrier_name,
                                            round(eqmt.z_coord, 1),
                                            round(rcvr.z_coord, 1),
                                            round(barrier_info_list[1], 1),
                                            round(barrier_info_list[2], 1),
                                            round(barrier_info_list[3], 1),
                                            round(barrier_info_list[4], 1),
                                            round(barrier_info_list[5], 1),
                                            round(barrier_info_list[6], 1),
                                            round(barrier_info_list[7], 1),
                                            barrier_info_list[8],
                                            eqmt.hz63,
                                            eqmt.hz125,
                                            eqmt.hz250,
                                            eqmt.hz500,
                                            eqmt.hz1000,
                                            eqmt.hz2000,
                                            eqmt.hz4000,
                                            eqmt.hz8000,
                                        ]
                                        if barrier_info_list != 0
                                        else [0]
                                    )

                        elif (
                            TAKE_ARI_BARRIER == True and TAKE_OB_FRESNAL_BARRIER == True
                        ):
                            for bar in self.parent.func_vars.barrier_list:
                                if (
                                    self.parent.func_vars.use_specific_bar_bool.get()
                                    is True
                                    and self.spec_bar_check(bar, eqmt_index, rcvr_index)
                                    is False
                                ):
                                    continue
                                if None not in [
                                    eqmt.hz63,
                                    eqmt.hz125,
                                    eqmt.hz250,
                                    eqmt.hz500,
                                    eqmt.hz1000,
                                    eqmt.hz2000,
                                    eqmt.hz4000,
                                    eqmt.hz8000,
                                ]:
                                    barrier_info_list = self.OB_fresnel_barrier_IL_calc(
                                        eqmt.x_coord,
                                        eqmt.y_coord,
                                        eqmt.z_coord,
                                        eqmt.hz63,
                                        eqmt.hz125,
                                        eqmt.hz250,
                                        eqmt.hz500,
                                        eqmt.hz1000,
                                        eqmt.hz2000,
                                        eqmt.hz4000,
                                        eqmt.hz8000,
                                        eqmt.sound_level,
                                        bar.x0_coord,
                                        bar.y0_coord,
                                        bar.z0_coord,
                                        bar.x1_coord,
                                        bar.y1_coord,
                                        bar.z1_coord,
                                        rcvr.x_coord,
                                        rcvr.y_coord,
                                        rcvr.z_coord,
                                    )
                                    barrier_IL_test = (
                                        barrier_info_list[0]
                                        if barrier_info_list != 0
                                        else 0
                                    )
                                    barriermethod = " - OB_fresnel"
                                else:
                                    barrier_info_list = self.ARI_barrier_IL_calc(
                                        eqmt.x_coord,
                                        eqmt.y_coord,
                                        eqmt.z_coord,
                                        bar.x0_coord,
                                        bar.y0_coord,
                                        bar.z0_coord,
                                        bar.x1_coord,
                                        bar.y1_coord,
                                        bar.z1_coord,
                                        rcvr.x_coord,
                                        rcvr.y_coord,
                                        rcvr.z_coord,
                                    )
                                    barrier_IL_test = (
                                        barrier_info_list[0]
                                        if barrier_info_list != 0
                                        else 0
                                    )
                                    barriermethod = " - ari"
                                if barrier_IL_test > barrier_IL:
                                    barrier_IL = barrier_IL_test
                                    used_barrier_name = str(
                                        bar.barrier_name + barriermethod
                                    )
                                    used_barrier_obj = bar
                                    barrierListForExcelOutput_curData = (
                                        [
                                            int(round(barrier_IL, 0)),
                                            eqmt.eqmt_tag,
                                            rcvr.r_name,
                                            bar.barrier_name,
                                            round(eqmt.z_coord, 1),
                                            round(rcvr.z_coord, 1),
                                            round(barrier_info_list[1], 1),
                                            round(barrier_info_list[2], 1),
                                            round(barrier_info_list[3], 1),
                                            round(barrier_info_list[4], 1),
                                            round(barrier_info_list[5], 1),
                                            round(barrier_info_list[6], 1),
                                            round(barrier_info_list[7], 1),
                                            barrier_info_list[8],
                                            eqmt.hz63,
                                            eqmt.hz125,
                                            eqmt.hz250,
                                            eqmt.hz500,
                                            eqmt.hz1000,
                                            eqmt.hz2000,
                                            eqmt.hz4000,
                                            eqmt.hz8000,
                                        ]
                                        if barrier_info_list != 0
                                        else [0]
                                    )
                        try:
                            self.barrierListForExcelOutput.append(
                                barrierListForExcelOutput_curData
                            )
                        except UnboundLocalError:
                            print("Barrier Calculation Block Error")

                        barrierListForExcelOutput_curData = []
                        # print(eqmt.eqmt_tag, " - ", barrier_IL, int(barrier_IL), int(round(barrier_IL, 0)))
                        spl = (
                            sound_power
                            - eqmt.insertion_loss
                            - attenuation
                            - barrier_IL
                            - directivity_loss
                        )
                        # if barriermethod == ' - OB_fresnel':
                        print(
                            f"eqmt: __{eqmt.eqmt_tag}, rcvr: __{rcvr.r_name}, bar: __{used_barrier_name}, barrier IL: __{barrier_IL}"
                        )
                        self.parent.func_vars.e_to_r_with_bar[eqmt][rcvr][
                            "bar_obj"
                        ] = used_barrier_obj
                        self.parent.func_vars.e_to_r_with_bar[eqmt][rcvr][
                            "bar_il"
                        ] = barrier_IL
                    except (ValueError, ZeroDivisionError):
                        # print("MATH DOMAIN ERROR OCCURED")
                        spl = 1000

                elif (
                    self.parent.func_vars.ignore_matrix[eqmt_index][rcvr_index] != None
                ):
                    self.barrierListForExcelOutput.append(
                        barrierListForExcelOutput_curData
                    )
                    spl = 0
                sound_pressure += 10 ** (spl / 10)
                # print(f"eqmt, x: {eqmt.x_coord}, y: {eqmt.y_coord}, z: {eqmt.z_coord}, lwa: {round(sound_power,0)}, IL: {round(eqmt.insertion_loss,0)}, distance: {round(distance,1)}, attenuation: {round(attenuation,1)}")
            rcvr.predicted_sound_level = round(10 * math.log10(sound_pressure), 1)
            #     print(f"predicted sound level: {rcvr.predicted_sound_level}")
            # print(f"distance: {distance}")
            # for listy in self.barrierListForExcelOutput:
            #     print(listy, "/n")

    def select_item_from_eqmt_tree(self, event):
        self.deselect_item_from_trees()
        self.focused_tree_children = self.equipment_tree.get_children()
        self.focused_line = self.equipment_tree.focus()
        self.current_equipment = self.equipment_tree.item(self.focused_line)["values"]
        print(self.current_equipment)

    def select_item_from_rcvr_tree(self, event):
        self.deselect_item_from_trees()
        self.focused_tree_children = self.receiver_tree.get_children()
        self.focused_line = self.receiver_tree.focus()
        self.current_receiver = self.receiver_tree.item(self.focused_line)["values"]
        if self.parent.func_vars.e_to_r_shapes_bool.get():
            self.parent.pane_toolbox.draw_eqmt_to_rcvr_shapes()
        else:
            for shape in self.parent.editor.e_to_r_shapes:
                self.parent.editor.canvas.delete(shape)
            self.parent.editor.e_to_r_shapes.clear()
        print(self.current_receiver)

    def select_item_from_barrier_tree(self, event):
        self.deselect_item_from_trees()
        self.focused_tree_children = self.barrier_tree.get_children()
        self.focused_line = self.barrier_tree.focus()
        self.current_barrier = self.barrier_tree.item(self.focused_line)["values"]
        print(self.current_barrier)

    def deselect_item_from_trees(self):
        self.current_barrier = None
        self.current_receiver = None
        self.current_equipment = None
        self.focused_tree_children = None

    def onExportListButton(self):
        wb = openpyxl.load_workbook(XL_TEMP_FILEPATH, keep_vba=True, data_only=False)
        ws = wb[SHEET_NAME]

        # eqmt
        for obj in self.parent.func_vars.equipment_list:
            for row in ws.iter_rows():
                if row[EQMT_NAME_COL].value == None:
                    break
                if row[EQMT_NAME_COL].value.replace(" ", "-") == obj.eqmt_tag.replace(
                    " ", "-"
                ):
                    row[EQMT_X_COORD_COL].value = obj.x_coord
                    row[EQMT_Y_COORD_COL].value = obj.y_coord

        # receivers
        for obj in self.parent.func_vars.receiver_list:
            for row in ws.iter_rows():
                if row[RCVR_NAME_COL].value == None:
                    break
                if row[RCVR_NAME_COL].value.replace(" ", "-") == obj.r_name.replace(
                    " ", "-"
                ):
                    row[RCVR_X_COORD_COL].value = obj.x_coord
                    row[RCVR_Y_COORD_COL].value = obj.y_coord

        for obj in self.parent.func_vars.barrier_list:
            for row in ws.iter_rows(min_row=BAR_START_ROW, max_row=100):
                if row[BAR_NAME_COL].value == None:
                    break
                if row[BAR_NAME_COL].value.replace(
                    " ", "-"
                ) == obj.barrier_name.replace(" ", "-"):
                    row[BAR_X0_COORD_COL].value = obj.x0_coord
                    row[BAR_Y0_COORD_COL].value = obj.y0_coord
                    row[BAR_Z0_COORD_COL].value = obj.z0_coord
                    row[BAR_X1_COORD_COL].value = obj.x1_coord
                    row[BAR_Y1_COORD_COL].value = obj.y1_coord
                    row[BAR_Z1_COORD_COL].value = obj.z1_coord

        barCalcListNum = 1
        totalEqmtCount = len(self.parent.func_vars.equipment_list)
        for col in BAR_IL_COL_RANGE:
            for row in ws.iter_rows(min_row=2, max_row=2 + totalEqmtCount - 1):
                if barCalcListNum > len(self.barrierListForExcelOutput) - 1:
                    break
                if not self.barrierListForExcelOutput[barCalcListNum]:
                    row[col].value = None
                else:
                    row[col].value = self.barrierListForExcelOutput[barCalcListNum][0]
                    print(self.barrierListForExcelOutput[barCalcListNum][0])
                barCalcListNum += 1

        # saving scale
        """ using the cell reference doesn't work...."""
        # KNOWN_DISTANCE_FT_CELL.value = self.parent.func_vars.known_distance_ft
        # CALE_LINE_DISTANCE_PX_CELL.value = self.parent.func_vars.scale_line_distance_px
        ws["AE20"] = self.parent.func_vars.known_distance_ft
        ws["AF20"] = self.parent.func_vars.scale_line_distance_px

        # save spec bar bool
        """ using the cell reference doesn't work...."""
        # USE_SPECIFIC_BAR_BOOL_CELL.value = self.parent.func_vars.use_specific_bar_bool.get()
        ws["AC19"] = self.parent.func_vars.use_specific_bar_bool.get()

        print("saving")
        wb.save(filename=XL_FILEPATH_SAVE)
        print("saved")
        # wb.close()

    def entryBox1_unfocus(self, event):
        self.status_label.focus()

    def entryBox1_select_all(self, event):
        text = self.entryBox1.get()
        self.entryBox1.selection_range(0, len(text))

    def save_changes(self):
        offset = 20
        if self.current_equipment:
            # self, count, eqmt_tag, path, make, model, sound_level, sound_ref_dist, tested_q, installed_q, insertion_loss, x_coord, y_coord, z_coord
            self.current_obj.count = float(self.count_input.get())
            self.current_obj.eqmt_tag = self.eqmt_tag_input.get()
            self.current_obj.path = self.path_input.get()
            self.current_obj.make = self.make_input.get()
            self.current_obj.model = self.model_input.get()
            self.current_obj.sound_level = float(self.sound_level_input.get())
            self.current_obj.sound_ref_dist = float(self.sound_ref_dist_input.get())
            self.current_obj.tested_q = float(self.tested_q_input.get())
            self.current_obj.installed_q = float(self.installed_q_input.get())
            self.current_obj.insertion_loss = float(self.insertion_loss_input.get())
            self.current_obj.x_coord = float(self.x_coord_input.get())
            self.current_obj.y_coord = float(self.y_coord_input.get())
            self.current_obj.z_coord = float(self.z_coord_input.get())

            self.eqmt_tagged = self.parent.editor.canvas.gettags(
                self.current_obj.eqmt_tag
            )
            self.eqmt_num = self.eqmt_tagged[0]
            self.eqmt_ids = self.parent.editor.canvas.find_withtag(
                self.current_obj.eqmt_tag
            )
            self.current_shape = self.eqmt_ids[0]
            self.current_text = self.eqmt_ids[1]

            x = self.current_obj.x_coord / self.parent.func_vars.master_scale
            y = self.current_obj.y_coord / self.parent.func_vars.master_scale
            self.parent.editor.canvas.coords(
                self.current_shape, x + offset, y + offset, x - offset, y - offset
            )
            self.parent.editor.canvas.coords(self.current_text, x, y)

        if self.current_receiver:
            # self, r_name, x_coord, y_coord, z_coord, sound_limit, predicted_sound_level
            self.current_obj.r_name = self.r_name_input.get()
            self.current_obj.x_coord = float(self.x_coord_input.get())
            self.current_obj.y_coord = float(self.y_coord_input.get())
            self.current_obj.z_coord = float(self.z_coord_input.get())
            self.current_obj.sound_limit = float(self.sound_limit_input.get())

            self.rcvr_tagged = self.parent.editor.canvas.gettags(
                self.current_obj.r_name
            )
            self.rcvr_num = self.rcvr_tagged[0]
            self.rcvr_ids = self.parent.editor.canvas.find_withtag(
                self.current_obj.r_name
            )
            self.current_shape = self.rcvr_ids[0]
            self.current_text = self.rcvr_ids[1]

            x = self.current_obj.x_coord / self.parent.func_vars.master_scale
            y = self.current_obj.y_coord / self.parent.func_vars.master_scale
            self.parent.editor.canvas.coords(
                self.current_shape, x + offset, y + offset, x - offset, y - offset
            )
            self.parent.editor.canvas.coords(self.current_text, x, y)

        if self.current_barrier:
            # self, barrier_name, x0_coord, y0_coord, z0_coord, x1_coord, y1_coord, z1_coord
            self.current_obj.barrier_name = self.barrier_name_input.get()
            self.current_obj.x0_coord = float(self.x0_coord_input.get())
            self.current_obj.y0_coord = float(self.y0_coord_input.get())
            self.current_obj.z0_coord = float(self.z0_coord_input.get())
            self.current_obj.x1_coord = float(self.x1_coord_input.get())
            self.current_obj.y1_coord = float(self.y1_coord_input.get())
            self.current_obj.z1_coord = float(self.z1_coord_input.get())

            self.barr_tagged = self.parent.editor.canvas.gettags(
                self.current_obj.barrier_name
            )
            self.barr_num = self.barr_tagged[0]
            self.barr_ids = self.parent.editor.canvas.find_withtag(
                self.current_obj.barrier_name
            )
            self.current_shape = self.barr_ids[0]
            self.current_text = self.barr_ids[1]

            print(self.current_obj.x0_coord)
            print(self.current_obj.y0_coord)
            print(self.current_obj.x1_coord)
            print(self.current_obj.y1_coord)

            x0 = self.current_obj.x0_coord / self.parent.func_vars.master_scale
            y0 = self.current_obj.y0_coord / self.parent.func_vars.master_scale
            x1 = self.current_obj.x1_coord / self.parent.func_vars.master_scale
            y1 = self.current_obj.y1_coord / self.parent.func_vars.master_scale

            self.parent.editor.canvas.coords(self.current_shape, x0, y0, x1, y1)
            self.parent.editor.canvas.coords(
                self.current_text, x0 + (x1 - x0) / 2, y0 + (y1 - y0) / 2
            )
            print("Hey", 2.85 / self.parent.func_vars.master_scale)

        self.update_est_noise_levels()
        self.generateEqmtTree()
        self.generateRcvrTree()
        self.generateBarrierTree()
        self.newWindow.destroy()

    def open_item_editor_window(self, event):
        self.newWindow = tk.Toplevel()
        self.newWindow.title("item editor")
        self.newWindow.geometry("500x500")

        if self.current_equipment:
            # self, count, eqmt_tag, path, make, model, sound_level, sound_ref_dist, tested_q, installed_q, insertion_loss, x_coord, y_coord, z_coord
            for obj in self.parent.func_vars.equipment_list:
                if obj.eqmt_tag == self.current_equipment[1]:
                    self.current_obj = obj
                    break

            self.count_label = tk.Label(
                self.newWindow, text="count", borderwidth=2, font=(None, 15)
            )
            self.eqmt_tag_label = tk.Label(
                self.newWindow, text="eqmt_tag", borderwidth=2, font=(None, 15)
            )
            self.path_label = tk.Label(
                self.newWindow, text="path", borderwidth=2, font=(None, 15)
            )
            self.make_label = tk.Label(
                self.newWindow, text="make", borderwidth=2, font=(None, 15)
            )
            self.model_label = tk.Label(
                self.newWindow, text="model", borderwidth=2, font=(None, 15)
            )
            self.sound_level_label = tk.Label(
                self.newWindow, text="sound_level", borderwidth=2, font=(None, 15)
            )
            self.sound_ref_dist_label = tk.Label(
                self.newWindow, text="sound_ref_dist", borderwidth=2, font=(None, 15)
            )
            self.tested_q_label = tk.Label(
                self.newWindow, text="tested_q", borderwidth=2, font=(None, 15)
            )
            self.installed_q_label = tk.Label(
                self.newWindow, text="installed_q", borderwidth=2, font=(None, 15)
            )
            self.insertion_loss_label = tk.Label(
                self.newWindow, text="insertion_loss", borderwidth=2, font=(None, 15)
            )
            self.x_coord_label = tk.Label(
                self.newWindow, text="x_coord", borderwidth=2, font=(None, 15)
            )
            self.y_coord_label = tk.Label(
                self.newWindow, text="y_coord", borderwidth=2, font=(None, 15)
            )
            self.z_coord_label = tk.Label(
                self.newWindow, text="z_coord", borderwidth=2, font=(None, 15)
            )

            self.count_input = tk.Entry(self.newWindow, font=(None, 15), width=24)
            self.eqmt_tag_input = tk.Entry(self.newWindow, font=(None, 15), width=24)
            self.path_input = tk.Entry(self.newWindow, font=(None, 15), width=24)
            self.make_input = tk.Entry(self.newWindow, font=(None, 15), width=24)
            self.model_input = tk.Entry(self.newWindow, font=(None, 15), width=24)
            self.sound_level_input = tk.Entry(self.newWindow, font=(None, 15), width=24)
            self.sound_ref_dist_input = tk.Entry(
                self.newWindow, font=(None, 15), width=24
            )
            self.tested_q_input = tk.Entry(self.newWindow, font=(None, 15), width=24)
            self.installed_q_input = tk.Entry(self.newWindow, font=(None, 15), width=24)
            self.insertion_loss_input = tk.Entry(
                self.newWindow, font=(None, 15), width=24
            )
            self.x_coord_input = tk.Entry(self.newWindow, font=(None, 15), width=24)
            self.y_coord_input = tk.Entry(self.newWindow, font=(None, 15), width=24)
            self.z_coord_input = tk.Entry(self.newWindow, font=(None, 15), width=24)

            self.count_label.grid(row=0, column=0, sticky=tk.N + tk.W)
            self.eqmt_tag_label.grid(row=1, column=0, sticky=tk.N + tk.W)
            self.path_label.grid(row=2, column=0, sticky=tk.N + tk.W)
            self.make_label.grid(row=3, column=0, sticky=tk.N + tk.W)
            self.model_label.grid(row=4, column=0, sticky=tk.N + tk.W)
            self.sound_level_label.grid(row=5, column=0, sticky=tk.N + tk.W)
            self.sound_ref_dist_label.grid(row=6, column=0, sticky=tk.N + tk.W)
            self.tested_q_label.grid(row=7, column=0, sticky=tk.N + tk.W)
            self.installed_q_label.grid(row=8, column=0, sticky=tk.N + tk.W)
            self.insertion_loss_label.grid(row=9, column=0, sticky=tk.N + tk.W)
            self.x_coord_label.grid(row=10, column=0, sticky=tk.N + tk.W)
            self.y_coord_label.grid(row=11, column=0, sticky=tk.N + tk.W)
            self.z_coord_label.grid(row=12, column=0, sticky=tk.N + tk.W)

            self.count_input.grid(row=0, column=1, sticky=tk.N + tk.W)
            self.eqmt_tag_input.grid(row=1, column=1, sticky=tk.N + tk.W)
            self.path_input.grid(row=2, column=1, sticky=tk.N + tk.W)
            self.make_input.grid(row=3, column=1, sticky=tk.N + tk.W)
            self.model_input.grid(row=4, column=1, sticky=tk.N + tk.W)
            self.sound_level_input.grid(row=5, column=1, sticky=tk.N + tk.W)
            self.sound_ref_dist_input.grid(row=6, column=1, sticky=tk.N + tk.W)
            self.tested_q_input.grid(row=7, column=1, sticky=tk.N + tk.W)
            self.installed_q_input.grid(row=8, column=1, sticky=tk.N + tk.W)
            self.insertion_loss_input.grid(row=9, column=1, sticky=tk.N + tk.W)
            self.x_coord_input.grid(row=10, column=1, sticky=tk.N + tk.W)
            self.y_coord_input.grid(row=11, column=1, sticky=tk.N + tk.W)
            self.z_coord_input.grid(row=12, column=1, sticky=tk.N + tk.W)

            self.count_input.insert(0, self.current_obj.count)
            self.eqmt_tag_input.insert(0, self.current_obj.eqmt_tag)
            self.path_input.insert(0, self.current_obj.path)
            self.make_input.insert(0, self.current_obj.make)
            self.model_input.insert(0, self.current_obj.model)
            self.sound_level_input.insert(0, self.current_obj.sound_level)
            self.sound_ref_dist_input.insert(0, self.current_obj.sound_ref_dist)
            self.tested_q_input.insert(0, self.current_obj.tested_q)
            self.installed_q_input.insert(0, self.current_obj.installed_q)
            self.insertion_loss_input.insert(0, self.current_obj.insertion_loss)
            self.x_coord_input.insert(0, self.current_obj.x_coord)
            self.y_coord_input.insert(0, self.current_obj.y_coord)
            self.z_coord_input.insert(0, self.current_obj.z_coord)

        if self.current_receiver:
            # self, r_name, x_coord, y_coord, z_coord, sound_limit, predicted_sound_level
            for obj in self.parent.func_vars.receiver_list:
                if obj.r_name == self.current_receiver[0]:
                    self.current_obj = obj
                    break

            self.r_name_label = tk.Label(
                self.newWindow, text="r_name", borderwidth=2, font=(None, 15)
            )
            self.x_coord_label = tk.Label(
                self.newWindow, text="x_coord", borderwidth=2, font=(None, 15)
            )
            self.y_coord_label = tk.Label(
                self.newWindow, text="y_coord", borderwidth=2, font=(None, 15)
            )
            self.z_coord_label = tk.Label(
                self.newWindow, text="z_coord", borderwidth=2, font=(None, 15)
            )
            self.sound_limit_label = tk.Label(
                self.newWindow, text="sound_limit", borderwidth=2, font=(None, 15)
            )

            self.r_name_input = tk.Entry(self.newWindow, font=(None, 15), width=24)
            self.x_coord_input = tk.Entry(self.newWindow, font=(None, 15), width=24)
            self.y_coord_input = tk.Entry(self.newWindow, font=(None, 15), width=24)
            self.z_coord_input = tk.Entry(self.newWindow, font=(None, 15), width=24)
            self.sound_limit_input = tk.Entry(self.newWindow, font=(None, 15), width=24)

            self.r_name_label.grid(row=0, column=0, sticky=tk.N + tk.W)
            self.x_coord_label.grid(row=1, column=0, sticky=tk.N + tk.W)
            self.y_coord_label.grid(row=2, column=0, sticky=tk.N + tk.W)
            self.z_coord_label.grid(row=3, column=0, sticky=tk.N + tk.W)
            self.sound_limit_label.grid(row=4, column=0, sticky=tk.N + tk.W)

            self.r_name_input.grid(row=0, column=1, sticky=tk.N + tk.W)
            self.x_coord_input.grid(row=1, column=1, sticky=tk.N + tk.W)
            self.y_coord_input.grid(row=2, column=1, sticky=tk.N + tk.W)
            self.z_coord_input.grid(row=3, column=1, sticky=tk.N + tk.W)
            self.sound_limit_input.grid(row=4, column=1, sticky=tk.N + tk.W)

            self.r_name_input.insert(0, self.current_obj.r_name)
            self.x_coord_input.insert(0, self.current_obj.x_coord)
            self.y_coord_input.insert(0, self.current_obj.y_coord)
            self.z_coord_input.insert(0, self.current_obj.z_coord)
            self.sound_limit_input.insert(0, self.current_obj.sound_limit)

        if self.current_barrier:
            # self, barrier_name, x0_coord, y0_coord, z0_coord, x1_coord, y1_coord, z1_coord
            for obj in self.parent.func_vars.barrier_list:
                if obj.barrier_name == self.current_barrier[0]:
                    self.current_obj = obj
                    break

            self.barrier_name_label = tk.Label(
                self.newWindow, text="barrier_name", borderwidth=2, font=(None, 15)
            )
            self.x0_coord_label = tk.Label(
                self.newWindow, text="x0_coord", borderwidth=2, font=(None, 15)
            )
            self.y0_coord_label = tk.Label(
                self.newWindow, text="y0_coord", borderwidth=2, font=(None, 15)
            )
            self.z0_coord_label = tk.Label(
                self.newWindow, text="z0_coord", borderwidth=2, font=(None, 15)
            )
            self.x1_coord_label = tk.Label(
                self.newWindow, text="x1_coord", borderwidth=2, font=(None, 15)
            )
            self.y1_coord_label = tk.Label(
                self.newWindow, text="y1_coord", borderwidth=2, font=(None, 15)
            )
            self.z1_coord_label = tk.Label(
                self.newWindow, text="z1_coord", borderwidth=2, font=(None, 15)
            )

            self.barrier_name_input = tk.Entry(
                self.newWindow, font=(None, 15), width=24
            )
            self.x0_coord_input = tk.Entry(self.newWindow, font=(None, 15), width=24)
            self.y0_coord_input = tk.Entry(self.newWindow, font=(None, 15), width=24)
            self.z0_coord_input = tk.Entry(self.newWindow, font=(None, 15), width=24)
            self.x1_coord_input = tk.Entry(self.newWindow, font=(None, 15), width=24)
            self.y1_coord_input = tk.Entry(self.newWindow, font=(None, 15), width=24)
            self.z1_coord_input = tk.Entry(self.newWindow, font=(None, 15), width=24)

            self.barrier_name_label.grid(row=0, column=0, sticky=tk.N + tk.W)
            self.x0_coord_label.grid(row=1, column=0, sticky=tk.N + tk.W)
            self.y0_coord_label.grid(row=2, column=0, sticky=tk.N + tk.W)
            self.z0_coord_label.grid(row=3, column=0, sticky=tk.N + tk.W)
            self.x1_coord_label.grid(row=4, column=0, sticky=tk.N + tk.W)
            self.y1_coord_label.grid(row=5, column=0, sticky=tk.N + tk.W)
            self.z1_coord_label.grid(row=6, column=0, sticky=tk.N + tk.W)

            self.barrier_name_input.grid(row=0, column=1, sticky=tk.N + tk.W)
            self.x0_coord_input.grid(row=1, column=1, sticky=tk.N + tk.W)
            self.y0_coord_input.grid(row=2, column=1, sticky=tk.N + tk.W)
            self.z0_coord_input.grid(row=3, column=1, sticky=tk.N + tk.W)
            self.x1_coord_input.grid(row=4, column=1, sticky=tk.N + tk.W)
            self.y1_coord_input.grid(row=5, column=1, sticky=tk.N + tk.W)
            self.z1_coord_input.grid(row=6, column=1, sticky=tk.N + tk.W)

            self.barrier_name_input.insert(0, self.current_obj.barrier_name)
            self.x0_coord_input.insert(0, self.current_obj.x0_coord)
            self.y0_coord_input.insert(0, self.current_obj.y0_coord)
            self.z0_coord_input.insert(0, self.current_obj.z0_coord)
            self.x1_coord_input.insert(0, self.current_obj.x1_coord)
            self.y1_coord_input.insert(0, self.current_obj.y1_coord)
            self.z1_coord_input.insert(0, self.current_obj.z1_coord)

        self.save_changes_button = tk.Button(
            self.newWindow,
            text="Save Changes",
            command=self.save_changes,
            font=(None, 15),
        )
        self.save_changes_button.grid(row=15, column=1, columnspan=2, sticky=tk.N)


class Main_Application(tk.Frame):
    def __init__(self, parent):
        tk.Frame.__init__(self)  # , parent
        self.parent = parent

        self.func_vars = FuncVars(self)
        self.editor = Editor(self)
        self.pane_toolbox = Pane_Toolbox(self)
        self.pane_eqmt_info = Pane_Eqmt_Info(self)

        self.editor.grid(row=0, rowspan=2, column=0, stick=tk.N)
        self.pane_toolbox.grid(row=0, column=1, padx=20, pady=20, stick=tk.N + tk.W)
        self.pane_eqmt_info.grid(row=1, column=1, padx=20, pady=20, stick=tk.N)


def main():
    # Initialize GLFW before Tkinter so its DPI awareness call (SetProcessDPIAwareness)
    # happens first. If done later (e.g. on first "View 3D" click), Windows re-scales
    # the already-open Tkinter window, making it shrink unexpectedly.
    import glfw
    glfw.init()
    glfw.terminate()

    root = tk.Tk()
    mainApp = Main_Application(root)
    mainApp.pack(side="top", fill="both", expand=True)
    root.geometry("+0+0")  # puts window in top left
    root.mainloop()


if __name__ == "__main__":
    main()
