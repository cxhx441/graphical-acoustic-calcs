import matplotlib.pyplot as plt
from pathlib import Path
import shutil
import os

def exportBarrierPlots(imported_list):
    if os.path.exists("barrierScreenshots"):
        shutil.rmtree("barrierScreenshots")
    Path("barrierScreenshots").mkdir(parents=True, exist_ok=True)

    curItemNum = 1
    totlItenNum = len(imported_list)

    plt.figure(figsize=(15, 10))
    
    ax = plt.subplot(1, 1, 1)
    box = ax.get_position()
    ax.set_position([box.x0, 0.2, box.width, box.height*.9])

    for listy in imported_list:
        if not listy:
            print(f"({curItemNum}/{totlItenNum}) - no data")
            curItemNum +=1
            continue
        BARRIER_ATTENUATION = listy[0]
        EQMT = listy[1]
        RCVR = listy[2]
        BAR = listy[3]
        EQMT_HEIGHT = listy[4]
        RCVR_HEIGHT = listy[5]
        BAR_HEIGHT = listy[6]
        SOURCE_TO_RECEIVER = listy[7]
        SOURCE_TO_BAR = listy[8]
        SOURCE_TO_TOP_BAR = listy[9]
        RCVR_TO_TOP_BAR = listy[10]
        DIRECT_PATH = listy[11]
        PLD = listy[12]
        REDUCTION_METHOD = listy[13]

        TITLE = f"from {EQMT} to {RCVR} across {BAR}"

        propogation_path_x = [0, SOURCE_TO_BAR, SOURCE_TO_RECEIVER]
        propogation_path_y = [EQMT_HEIGHT, BAR_HEIGHT, RCVR_HEIGHT]
        straight_path_x = [0, SOURCE_TO_RECEIVER]
        straight_path_y = [EQMT_HEIGHT, RCVR_HEIGHT]
        barrier_line_x = [SOURCE_TO_BAR, SOURCE_TO_BAR]
        barrier_line_y = [0, BAR_HEIGHT]
        source_point_y = [EQMT_HEIGHT]
        rcvr_point_x = [SOURCE_TO_RECEIVER]
        rcvr_point_y = [RCVR_HEIGHT]

        plt.plot(propogation_path_x, propogation_path_y, linewidth=3, color='red', label='Propogation Path')
        plt.plot(straight_path_x, straight_path_y, linewidth=1, color='blue', label='Direct Path')
        plt.plot(barrier_line_x, barrier_line_y, linewidth=3, color='magenta', label='Barrier - Min 4lb/ft2, \n Unperforated')

        plt.scatter([0], source_point_y, linewidth=4, color='blue', label='Source')
        plt.scatter(rcvr_point_x, rcvr_point_y, linewidth=4, color='green', label='Receiver')

        plt.xlim(0, SOURCE_TO_RECEIVER+10)
        plt.ylim(0, max(EQMT_HEIGHT, RCVR_HEIGHT, BAR_HEIGHT)+10)

        plt.title(TITLE, fontsize=10)
        plt.xlabel('Height (ft)', fontsize=12)
        plt.ylabel('Distance (ft)', fontsize=12)
        plt.suptitle("Noise Barrier - Geometry", fontsize=16)
        plt.grid(which='major', axis='both', color='gray', linestyle='-.', linewidth=0.5)

        # Put a legend to the right of the current axis
        ax.legend(loc='upper center', bbox_to_anchor=(0.92, -.065))

        col1 = 0
        col2 = 0.40 * (SOURCE_TO_RECEIVER+10)
        plt.text(col1, -10, f"A = {SOURCE_TO_TOP_BAR} ft, B = {RCVR_TO_TOP_BAR} ft, D = {DIRECT_PATH} ft", fontsize=10)
        plt.text(col1, -14, f"Path-Length Difference = {PLD} ft", fontsize=10)
        plt.text(col1, -18, f"Barrier Reduction per {REDUCTION_METHOD} Method: {BARRIER_ATTENUATION} dB", fontsize=10)
        plt.text(col2, -10, f"Source Height: {EQMT_HEIGHT} ft", fontsize=10)
        plt.text(col2, -14, f"Barrier Location: X = {SOURCE_TO_BAR} ft, Y = {BAR_HEIGHT} ft", fontsize=10)
        plt.text(col2, -18, f"Receiver Location: X = {SOURCE_TO_RECEIVER} ft, Y = {RCVR_HEIGHT} ft", fontsize=10)

        filepath = f"barrierScreenshots/{TITLE}.png"
        # plt.savefig(filepath, dpi=100, pad_inches=0.1)
        plt.savefig(filepath)
        plt.cla()
        print(f"({curItemNum}/{totlItenNum}) - {TITLE}")
        curItemNum +=1

    print("done exportBarrierPlots")
