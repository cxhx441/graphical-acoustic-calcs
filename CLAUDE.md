# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
python main.py
```

The app reads from a hardcoded `.xlsm` file (`XL_FILEPATH` at the top of `main.py`) on startup. You must have a valid Excel workbook present before launching. There are no automated tests.

## Installing Dependencies

```bash
pip install -r requirements.txt
```

Actual installed versions may differ from `requirements.txt` (e.g., `glfw==2.10.0`, `PyOpenGL==3.1.10`). The venv is at `.venv/`.

## Architecture

Everything lives in `main.py` (single-file app) except:
- `opengl_view.py` — standalone OpenGL 3D viewer window (GLFW, daemon thread)
- `BarrierPlotExporter.py` — matplotlib barrier geometry plots for report export
- `utils.py` — geometry helpers (line intersection, color utils, distance formula)

### Data Flow

On startup, `main.py` reads all equipment, receiver, and barrier data from the Excel workbook into `FuncVars`, which is the central data store. All coordinates are stored in **feet** (`x_coord`, `y_coord`, `z_coord`). The canvas displays objects at pixel positions = `coord_ft / master_scale`.

**`master_scale`** = `known_distance_ft / scale_line_distance_px` — feet per pixel. This is set via the "Set Image Scale" tool and stored in `FuncVars`. The scale is also persisted to Excel cells `AE20`/`AF20`.

### UI Layout

The root `tk.Tk` window contains three panes:
- **`Editor`** (`tk.Frame`) — scrollable Tkinter canvas with `bed_image.png` as the background. Handles all mouse interactions for placing/drawing equipment, receivers, and barriers. `image_size_factor=1.5` scales the image display.
- **`Pane_EqmtInfo`** — right-side panel with ttk treeviews for equipment, receivers, and barriers. Displays predicted sound levels, handles selection, and contains the acoustic calculation logic.
- **`Pane_Toolbox`** — toolbar at top with buttons for mode switching (draw equipment/receiver/barrier, set scale, export, View 3D).

### Coordinate System

- Canvas pixel space: origin at top-left, Y increases downward
- World space (feet): `coord = canvas_px * master_scale`
- Z coordinate is elevation in feet (0 = ground)
- The 3D view uses the same world-space coordinates; `opengl_view.py`'s ground quad spans `(0,0)` to `(img_w * master_scale * image_size_factor, img_h * master_scale * image_size_factor)`

### Acoustic Calculation

Noise levels are computed in `Pane_EqmtInfo.update_est_noise_levels()`. It iterates all equipment→receiver pairs, applies distance attenuation, directivity, and barrier insertion loss (using either ARI or octave-band Fresnel method depending on the `TAKE_*` booleans read from Excel). Results update `receiver.predicted_sound_level`.

### 3D View (`opengl_view.py`)

Launched via `Pane_Toolbox.open_3d_view()` in a daemon thread. `SceneData` copies all data on the main thread before handing off. Uses fixed-function OpenGL 2.1 (compatibility context) with GLFW. Camera is a Z-up azimuth/elevation orbit camera.

Mouse controls: left-drag = orbit, right-drag = dolly, middle-drag = XY ground-plane pan, scroll = zoom.
