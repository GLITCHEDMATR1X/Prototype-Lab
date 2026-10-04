"""HoloSpace Region in-world route sentinel.

This folder is not a standalone level and does not create a second screen.
HoloVerse mounts HoloSpace through CommandHubApp.activate_holospace_region_from_mode,
which runs the existing Region 8 warp/cockpit system inside the live HoloVerse window.
"""

ROUTE_ID = "holospace_region"
LAUNCH_TYPE = "in_world_region"
TARGET_REGION_NUMBER = 8


def route_manifest():
    return {
        "id": ROUTE_ID,
        "launch_type": LAUNCH_TYPE,
        "target_region_number": TARGET_REGION_NUMBER,
        "same_window": True,
        "placeholder": False,
        "separate_screen": False,
    }


if __name__ == "__main__":
    print("HoloSpace Region is an in-world HoloVerse route. Launch HoloVerse main.py and enter Region 8 from MatrixCore/Orbit.")
