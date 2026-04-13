import math
import os
import threading

import glfw
import numpy as np
import OpenGL.GL as gl
import OpenGL.GLU as glu
from PIL import Image, ImageDraw


class SceneData:
    """Thread-safe snapshot of scene objects. Copy-on-create from main thread."""

    def __init__(self, equipment_list, receiver_list, barrier_list, e_to_r_list,
                 master_scale=1.0, image_size_factor=1.0, image_path="bed_image.png"):
        self.equipment = [
            {"tag": e.eqmt_tag, "x": e.x_coord, "y": e.y_coord, "z": e.z_coord}
            for e in equipment_list
        ]
        self.receivers = [
            {
                "name": r.r_name,
                "x": r.x_coord,
                "y": r.y_coord,
                "z": r.z_coord,
                "level": r.predicted_sound_level
                if isinstance(r.predicted_sound_level, (int, float))
                else None,
            }
            for r in receiver_list
        ]
        self.barriers = [
            {
                "name": b.barrier_name,
                "x0": b.x0_coord,
                "y0": b.y0_coord,
                "z0": b.z0_coord,
                "x1": b.x1_coord,
                "y1": b.y1_coord,
                "z1": b.z1_coord,
            }
            for b in barrier_list
        ]
        self.e_to_r = [
            {
                "x0": e2r[0],
                "y0": e2r[1],
                "z0": e2r[2],
                "x1": e2r[3],
                "y1": e2r[4],
                "z1": e2r[5],
                "r": e2r[6],
                "g": e2r[7],
                "b": e2r[8],
            }
            for e2r in e_to_r_list
        ]
        self.master_scale = master_scale  # feet per pixel
        self.image_size_factor = image_size_factor
        self.image_path = image_path


class OrbitCamera:
    """Z-up orbit camera (azimuth/elevation around a target point)."""

    def __init__(self):
        self.target = np.array([0.0, 0.0, 0.0])
        self.radius = 300.0
        self.azimuth = 270.0   # degrees around Z axis (S camera, looking N → world +X goes right)
        self.elevation = 30.0  # degrees above XY plane
        self.fov = 45.0

    def position(self):
        az = math.radians(self.azimuth)
        el = math.radians(self.elevation)
        x = self.target[0] + self.radius * math.cos(el) * math.cos(az)
        y = self.target[1] + self.radius * math.cos(el) * math.sin(az)
        z = self.target[2] + self.radius * math.sin(el)
        return np.array([x, y, z])

    def apply(self, width, height):
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glLoadIdentity()
        aspect = width / max(height, 1)
        near = max(self.radius * 0.001, 0.1)
        far = self.radius * 10.0
        glu.gluPerspective(self.fov, aspect, near, far)

        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glLoadIdentity()
        pos = self.position()
        glu.gluLookAt(
            pos[0], pos[1], pos[2],
            self.target[0], self.target[1], self.target[2],
            0.0, 0.0, 1.0,  # Z-up
        )

    def orbit(self, daz, del_):
        self.azimuth += daz
        self.elevation = max(-85.0, min(85.0, self.elevation + del_))

    def zoom(self, factor):
        self.radius = max(1.0, min(100000.0, self.radius * factor))

    def pan(self, dx_world, dy_world):
        """Move target in the camera's right and up vectors (includes Z)."""
        az = math.radians(self.azimuth)
        right = np.array([-math.sin(az), math.cos(az), 0.0])
        view_dir = self.target - self.position()
        view_dir /= np.linalg.norm(view_dir)
        up = np.cross(right, view_dir)
        up = -up / np.linalg.norm(up)
        self.target += right * dx_world + up * dy_world


class View3D:
    """GLFW OpenGL window. Call run() from a daemon thread."""

    def __init__(self, scene_data: SceneData):
        self._scene = scene_data
        self._window = None
        self._camera = OrbitCamera()
        self._mouse_last = None
        self._mouse_button = None
        self._viewport_size = (1024, 768)
        self._ground_tex = None
        self._ground_img_w = 0
        self._ground_img_h = 0
        self._scene_bounds = {"x_min": 0, "x_max": 100, "y_min": 0, "y_max": 100}
        self._label_cache = {}  # text -> (tex_id, w, h)

    def run(self):
        if not glfw.init():
            raise RuntimeError("GLFW init failed")
        try:
            glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 2)
            glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 1)
            self._window = glfw.create_window(1024, 768, "3D Acoustic View", None, None)
            if not self._window:
                raise RuntimeError("GLFW window creation failed")
            glfw.make_context_current(self._window)
            glfw.swap_interval(1)
            self._setup_gl()
            self._load_ground_texture()
            self._compute_scene_bounds()
            self._auto_fit_camera()
            self._register_callbacks()

            while not glfw.window_should_close(self._window):
                self._render()
                glfw.swap_buffers(self._window)
                glfw.poll_events()
        finally:
            for entry in self._label_cache.values():
                try:
                    gl.glDeleteTextures([entry[0]])
                except Exception:
                    pass
            if self._ground_tex is not None:
                try:
                    gl.glDeleteTextures([self._ground_tex])
                except Exception:
                    pass
            if self._window:
                glfw.destroy_window(self._window)
            glfw.terminate()

    def _setup_gl(self):
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_LIGHTING)
        gl.glEnable(gl.GL_LIGHT0)
        gl.glEnable(gl.GL_COLOR_MATERIAL)
        gl.glColorMaterial(gl.GL_FRONT_AND_BACK, gl.GL_AMBIENT_AND_DIFFUSE)
        gl.glLightfv(gl.GL_LIGHT0, gl.GL_POSITION, [1.0, 1.0, 2.0, 0.0])
        gl.glLightfv(gl.GL_LIGHT0, gl.GL_DIFFUSE, [0.9, 0.9, 0.9, 1.0])
        gl.glLightfv(gl.GL_LIGHT0, gl.GL_AMBIENT, [0.3, 0.3, 0.3, 1.0])
        gl.glClearColor(0.15, 0.15, 0.2, 1.0)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

    def _load_ground_texture(self):
        path = self._scene.image_path
        if not os.path.exists(path):
            return
        img = Image.open(path).convert("RGBA")
        # img = img.transpose(Image.FLIP_TOP_BOTTOM)
        isf = self._scene.image_size_factor
        self._ground_img_w = img.width * isf
        self._ground_img_h = img.height * isf
        img_array = np.array(img, dtype=np.uint8)

        tex_id = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA,
                        img.width, img.height, 0,
                        gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, img_array)
        self._ground_tex = tex_id

    def _compute_scene_bounds(self):
        xs = ([e["x"] for e in self._scene.equipment]
              + [r["x"] for r in self._scene.receivers]
              + [b["x0"] for b in self._scene.barriers]
              + [b["x1"] for b in self._scene.barriers])
        ys = ([e["y"] for e in self._scene.equipment]
              + [r["y"] for r in self._scene.receivers]
              + [b["y0"] for b in self._scene.barriers]
              + [b["y1"] for b in self._scene.barriers])

        # Include image bounds if available
        if self._ground_img_w > 0 and self._scene.master_scale > 0:
            ms = self._scene.master_scale
            xs += [0.0, self._ground_img_w * ms]
            ys += [0.0, self._ground_img_h * ms]

        if not xs:
            xs = [0.0, 100.0]
            ys = [0.0, 100.0]

        margin = max((max(xs) - min(xs) + max(ys) - min(ys)) * 0.05, 10.0)
        self._scene_bounds = {
            "x_min": min(xs) - margin,
            "x_max": max(xs) + margin,
            "y_min": min(ys) - margin,
            "y_max": max(ys) + margin,
        }

    def _auto_fit_camera(self):
        b = self._scene_bounds
        cx = (b["x_min"] + b["x_max"]) / 2
        cy = (b["y_min"] + b["y_max"]) / 2

        # Vertical centroid from objects
        zs = ([e["z"] for e in self._scene.equipment]
              + [r["z"] for r in self._scene.receivers])
        cz = float(np.mean(zs)) if zs else 0.0

        self._camera.target = np.array([cx, cy, cz])
        span = max(b["x_max"] - b["x_min"], b["y_max"] - b["y_min"])
        self._camera.radius = max(span * 0.9, 50.0)

    def _register_callbacks(self):
        glfw.set_mouse_button_callback(self._window, self._on_mouse_button)
        glfw.set_cursor_pos_callback(self._window, self._on_cursor_pos)
        glfw.set_scroll_callback(self._window, self._on_scroll)
        glfw.set_framebuffer_size_callback(self._window, self._on_resize)
        w, h = glfw.get_framebuffer_size(self._window)
        self._viewport_size = (w, h)

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def _render(self):

        w, h = self._viewport_size
        gl.glViewport(0, 0, w, h)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        self._camera.apply(w, h)

        gl.glPushMatrix()
        gl.glScale(1.0, -1.0, 1.0) # Flip X-axis, keep Y and Z the same

        if self._ground_tex is not None:
            self._draw_ground_image()
        else:
            self._draw_ground_grid()
        self._draw_axes()
        self._draw_barriers()
        self._draw_equipment()
        self._draw_receivers()
        self._draw_e_to_r()

        gl.glPopMatrix()

        # HUD drawn last (2D overlay, no depth)
        self._draw_scale_bar()

    def _draw_ground_image(self):
        ms = self._scene.master_scale
        if ms <= 0:
            return
        w_world = self._ground_img_w * ms
        h_world = self._ground_img_h * ms

        gl.glDisable(gl.GL_LIGHTING)
        gl.glEnable(gl.GL_TEXTURE_2D)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._ground_tex)
        gl.glColor4f(1.0, 1.0, 1.0, 1.0)
        # Drawn slightly below Z=0 to avoid z-fighting with barrier bases
        z = -0.05
        gl.glBegin(gl.GL_QUADS)
        gl.glTexCoord2f(0.0, 0.0); gl.glVertex3f(0.0,     0.0,     z)
        gl.glTexCoord2f(1.0, 0.0); gl.glVertex3f(w_world, 0.0,     z)
        gl.glTexCoord2f(1.0, 1.0); gl.glVertex3f(w_world, h_world, z)
        gl.glTexCoord2f(0.0, 1.0); gl.glVertex3f(0.0,     h_world, z)
        gl.glEnd()
        gl.glDisable(gl.GL_TEXTURE_2D)
        gl.glEnable(gl.GL_LIGHTING)

    def _draw_ground_grid(self):
        b = self._scene_bounds
        x_min = math.floor(b["x_min"] / 10) * 10
        x_max = math.ceil(b["x_max"] / 10) * 10
        y_min = math.floor(b["y_min"] / 10) * 10
        y_max = math.ceil(b["y_max"] / 10) * 10

        gl.glDisable(gl.GL_LIGHTING)
        gl.glColor3f(0.3, 0.3, 0.3)
        gl.glLineWidth(1.0)
        gl.glBegin(gl.GL_LINES)
        step = 10.0
        x = x_min
        while x <= x_max:
            gl.glVertex3f(x, y_min, 0.0)
            gl.glVertex3f(x, y_max, 0.0)
            x += step
        y = y_min
        while y <= y_max:
            gl.glVertex3f(x_min, y, 0.0)
            gl.glVertex3f(x_max, y, 0.0)
            y += step
        gl.glEnd()
        gl.glEnable(gl.GL_LIGHTING)

    def _draw_axes(self):
        length = max(self._camera.radius * 0.15, 20.0)
        gl.glDisable(gl.GL_LIGHTING)
        gl.glLineWidth(3.0)
        gl.glBegin(gl.GL_LINES)
        gl.glColor3f(1.0, 0.2, 0.2); gl.glVertex3f(0, 0, 0); gl.glVertex3f(length, 0, 0)
        gl.glColor3f(0.2, 1.0, 0.2); gl.glVertex3f(0, 0, 0); gl.glVertex3f(0, length, 0)
        gl.glColor3f(0.2, 0.4, 1.0); gl.glVertex3f(0, 0, 0); gl.glVertex3f(0, 0, length)
        gl.glEnd()
        gl.glLineWidth(1.0)
        gl.glEnable(gl.GL_LIGHTING)

    def _draw_e_to_r(self):
        for l in self._scene.e_to_r:
            x0, y0, z0 = l["x0"], l["y0"], l["z0"]
            x1, y1, z1 = l["x1"], l["y1"], l["z1"]
            r, g, b = l["r"], l["g"], l["b"]
            gl.glDisable(gl.GL_LIGHTING)
            gl.glLineWidth(1.0)
            gl.glBegin(gl.GL_LINES)
            gl.glColor3f(r, g, b); gl.glVertex3f(x0, y0, z0); gl.glVertex3f(x1, y1, z1)
            gl.glEnd()
            gl.glLineWidth(1.0)
            gl.glEnable(gl.GL_LIGHTING)

    def _draw_barriers(self):
        for b in self._scene.barriers:
            h = max(b["z0"], b["z1"])
            if h <= 0:
                h = 10.0
            x0, y0, x1, y1 = b["x0"], b["y0"], b["x1"], b["y1"]

            dx, dy = x1 - x0, y1 - y0
            length = math.sqrt(dx * dx + dy * dy)
            nx, ny = (-dy / length, dx / length) if length > 0 else (0.0, 1.0)

            gl.glEnable(gl.GL_LIGHTING)
            gl.glColor4f(0.5, 0.55, 0.7, 0.85)
            gl.glBegin(gl.GL_QUADS)
            gl.glNormal3f(nx, ny, 0.0)
            gl.glVertex3f(x0, y0, 0.0)
            gl.glVertex3f(x1, y1, 0.0)
            gl.glVertex3f(x1, y1, h)
            gl.glVertex3f(x0, y0, h)
            gl.glEnd()

            gl.glDisable(gl.GL_LIGHTING)
            gl.glColor3f(0.2, 0.25, 0.5)
            gl.glLineWidth(2.0)
            gl.glBegin(gl.GL_LINE_LOOP)
            gl.glVertex3f(x0, y0, 0.0)
            gl.glVertex3f(x1, y1, 0.0)
            gl.glVertex3f(x1, y1, h)
            gl.glVertex3f(x0, y0, h)
            gl.glEnd()
            gl.glLineWidth(1.0)
            gl.glEnable(gl.GL_LIGHTING)

    def _draw_equipment(self):
        size = max(self._camera.radius * 0.012, 1.5)
        for e in self._scene.equipment:
            gl.glColor3f(0.2, 0.85, 0.2)
            self._draw_box(e["x"], e["y"], e["z"], size)

    def _draw_receivers(self):
        for r in self._scene.receivers:
            level = r["level"]
            if level is not None:
                clamped = max(40.0, min(90.0, level))
                size = 2.0 + (clamped - 40.0) / 50.0 * 6.0
                gl.glColor3f(0.9, 0.15, 0.15)
            else:
                size = 2.0
                gl.glColor3f(0.55, 0.55, 0.55)
            base_size = max(self._camera.radius * 0.008, 1.0)
            radius = base_size * (size / 4.0)
            self._draw_sphere(r["x"], r["y"], r["z"], radius)

    # ------------------------------------------------------------------
    # Scale bar HUD
    # ------------------------------------------------------------------

    def _draw_scale_bar(self):
        w, h = self._viewport_size
        # World units per screen pixel at the target distance
        world_per_px = (self._camera.radius
                        * math.tan(math.radians(self._camera.fov / 2))
                        * 2.0 / max(h, 1))
        # Pick a nice bar length that's ~15% of screen width
        target_world = world_per_px * w * 0.15
        nice = [1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000]
        bar_world = min(nice, key=lambda x: abs(x - target_world))
        bar_px = bar_world / world_per_px

        # Switch to 2D orthographic overlay
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glPushMatrix()
        gl.glLoadIdentity()
        gl.glOrtho(0, w, 0, h, -1, 1)
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glPushMatrix()
        gl.glLoadIdentity()
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_LIGHTING)

        margin = 20.0
        bar_y = margin + 10.0
        bar_x0 = margin
        bar_x1 = margin + bar_px
        tick = 8.0
        pad = 6.0

        # Background box
        gl.glColor4f(0.0, 0.0, 0.0, 0.55)
        gl.glBegin(gl.GL_QUADS)
        gl.glVertex2f(bar_x0 - pad,  bar_y - tick - pad)
        gl.glVertex2f(bar_x1 + pad,  bar_y - tick - pad)
        gl.glVertex2f(bar_x1 + pad,  bar_y + tick + 26.0)
        gl.glVertex2f(bar_x0 - pad,  bar_y + tick + 26.0)
        gl.glEnd()

        # Bar line and end ticks
        gl.glColor3f(1.0, 0.95, 0.2)
        gl.glLineWidth(2.0)
        gl.glBegin(gl.GL_LINES)
        gl.glVertex2f(bar_x0, bar_y);       gl.glVertex2f(bar_x1, bar_y)
        gl.glVertex2f(bar_x0, bar_y - tick); gl.glVertex2f(bar_x0, bar_y + tick)
        gl.glVertex2f(bar_x1, bar_y - tick); gl.glVertex2f(bar_x1, bar_y + tick)
        gl.glEnd()
        gl.glLineWidth(1.0)

        # Text label via PIL texture
        label = f"{bar_world} ft"
        entry = self._get_label_texture(label)
        if entry:
            tex_id, tex_w, tex_h = entry
            gl.glEnable(gl.GL_TEXTURE_2D)
            gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
            gl.glColor4f(1.0, 1.0, 1.0, 1.0)
            tx = (bar_x0 + bar_x1) / 2.0 - tex_w / 2.0
            ty = bar_y + tick + 4.0
            gl.glBegin(gl.GL_QUADS)
            gl.glTexCoord2f(0, 0); gl.glVertex2f(tx,         ty)
            gl.glTexCoord2f(1, 0); gl.glVertex2f(tx + tex_w, ty)
            gl.glTexCoord2f(1, 1); gl.glVertex2f(tx + tex_w, ty + tex_h)
            gl.glTexCoord2f(0, 1); gl.glVertex2f(tx,         ty + tex_h)
            gl.glEnd()
            gl.glDisable(gl.GL_TEXTURE_2D)

        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_LIGHTING)
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glPopMatrix()
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glPopMatrix()

    def _get_label_texture(self, text):
        if text in self._label_cache:
            return self._label_cache[text]
        try:
            img_w, img_h = 160, 24
            img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.text((2, 2), text, fill=(255, 240, 100, 220))
            img_array = np.flipud(np.array(img, dtype=np.uint8))

            tex_id = gl.glGenTextures(1)
            gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA,
                            img_w, img_h, 0,
                            gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, img_array)
            entry = (tex_id, img_w, img_h)
            self._label_cache[text] = entry
            return entry
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------

    def _draw_box(self, cx, cy, cz, size):
        h = size / 2.0
        faces = [
            ((0,  0,  1), [(-h, -h,  h), ( h, -h,  h), ( h,  h,  h), (-h,  h,  h)]),
            ((0,  0, -1), [(-h, -h, -h), (-h,  h, -h), ( h,  h, -h), ( h, -h, -h)]),
            ((1,  0,  0), [( h, -h, -h), ( h,  h, -h), ( h,  h,  h), ( h, -h,  h)]),
            ((-1, 0,  0), [(-h, -h, -h), (-h, -h,  h), (-h,  h,  h), (-h,  h, -h)]),
            ((0,  1,  0), [(-h,  h, -h), (-h,  h,  h), ( h,  h,  h), ( h,  h, -h)]),
            ((0, -1,  0), [(-h, -h, -h), ( h, -h, -h), ( h, -h,  h), (-h, -h,  h)]),
        ]
        gl.glBegin(gl.GL_QUADS)
        for normal, verts in faces:
            gl.glNormal3f(*normal)
            for v in verts:
                gl.glVertex3f(cx + v[0], cy + v[1], cz + v[2])
        gl.glEnd()

    def _draw_sphere(self, cx, cy, cz, radius):
        gl.glPushMatrix()
        gl.glTranslatef(cx, cy, cz)
        quad = glu.gluNewQuadric()
        glu.gluSphere(quad, radius, 16, 12)
        glu.gluDeleteQuadric(quad)
        gl.glPopMatrix()

    # ------------------------------------------------------------------
    # GLFW callbacks
    # ------------------------------------------------------------------

    def _on_mouse_button(self, window, button, action, mods):
        if action == glfw.PRESS:
            x, y = glfw.get_cursor_pos(window)
            self._mouse_last = (x, y)
            shift = mods & glfw.MOD_SHIFT
            ctrl = mods & glfw.MOD_CONTROL
            if button == glfw.MOUSE_BUTTON_LEFT:
                if shift:
                    self._mouse_button = "pan"
                elif ctrl:
                    self._mouse_button = "dolly"
                else:
                    self._mouse_button = "orbit"
            elif button == glfw.MOUSE_BUTTON_MIDDLE:
                self._mouse_button = "drag"   # XY ground-plane drag
            elif button == glfw.MOUSE_BUTTON_RIGHT:
                self._mouse_button = "dolly"
        elif action == glfw.RELEASE:
            self._mouse_button = None
            self._mouse_last = None

    def _on_cursor_pos(self, window, x, y):
        if self._mouse_last is None or self._mouse_button is None:
            return
        dx = x - self._mouse_last[0]
        dy = y - self._mouse_last[1]
        self._mouse_last = (x, y)

        if self._mouse_button == "orbit":
            self._camera.orbit(dx * 0.3, -dy * 0.3)
        elif self._mouse_button == "dolly":
            self._camera.zoom(1.0 + dy * 0.01)
        elif self._mouse_button == "pan":
            _, h = self._viewport_size
            scale = (self._camera.radius
                     * math.tan(math.radians(self._camera.fov / 2))
                     * 2.0 / max(h, 1))
            self._camera.pan(-dx * scale, dy * scale)
        elif self._mouse_button == "drag":
            # Translate target in world XY plane (ground follows cursor)
            _, h = self._viewport_size
            scale = (self._camera.radius
                     * math.tan(math.radians(self._camera.fov / 2))
                     * 2.0 / max(h, 1))
            az = math.radians(self._camera.azimuth)
            # Camera right in XY: perpendicular to azimuth direction
            right_x = -math.sin(az)
            right_y =  math.cos(az)
            # Camera forward in XY: direction from camera toward target, projected flat
            fwd_x = -math.cos(az)
            fwd_y = -math.sin(az)
            # Drag right → scene moves right; drag down → scene moves forward
            self._camera.target[0] += right_x * dx * scale
            self._camera.target[1] += right_y * dx * scale
            self._camera.target[0] -= fwd_x * dy * scale
            self._camera.target[1] -= fwd_y * dy * scale

    def _on_scroll(self, window, xoff, yoff):
        self._camera.zoom(0.9 ** yoff)

    def _on_resize(self, window, w, h):
        self._viewport_size = (max(w, 1), max(h, 1))
