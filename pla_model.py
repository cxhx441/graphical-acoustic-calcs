# Author: Craig Harris
# GitHub Username: cxhx441
# Description:
import math

class Point:
    def __init__(self, xyz_coords: tuple[float]) -> None:
        self.x_pos, self.y_pos, self.z_pos = xyz_coords

    def get_coords(self):
        return self.x_pos, self.y_pos

    def get_distance(self, point: 'Point'):
        return math.sqrt(
               (self.x_pos - point.x_pos) ** 2 +
               (self.y_pos - point.y_pos) ** 2 +
               (self.z_pos - point.z_pos) ** 2
        )

    def move_up(self, y):
        self.y_pos -= y

    def move_down(self, y):
        self.y_pos += y

    def move_right(self, x):
        self.x_pos += x

    def move_left(self, x):
        self.x_pos -= x

    def move_raise(self, z):
        self.z_pos += z

    def move_lower(self, z):
        self.z_pos -= z


class NoiseLevel:
    def __init__(self, dBA: float, octave_bands: list[float] = None):
        if octave_bands is None:
            self.dBA = dBA
        self.octave_bands = octave_bands
        self.dBA = dBA


class Source(Point):
    def __init__(self,
                 xyz_coords: tuple[float],
                 count: int,
                 eqmt_tag: str,
                 path: str,
                 make: str,
                 model: str,
                 sound_ref_dist: float,
                 tested_q: float,
                 installed_q: float,
                 IL: int,
                 noise_level: NoiseLevel
                 ) -> None:
        super().__init__(xyz_coords)
        self.count = count
        self.eqmt_tag = eqmt_tag
        self.path: path
        self.make: make
        self.mode: model
        self.sound_ref_dist: sound_ref_dist
        self.tested_q: tested_q
        self.installed_q: installed_q
        self.IL: IL
        self.noise_level: noise_level


class Receiver(Point):
    def __init__(self, xyz_coords: tuple[float], dBA_limit: int, ) -> None:
        super().__init__(xyz_coords)
        self.dBA_limit = dBA_limit
        self.dBA = None


class Barrier:
    def __init__(self, start: Point, end: Point):
        self.start = start
        self.end = end

    def move_up(self, y):
        self.start.move_up(y)
        self.end.move_up(y)

    def move_down(self, y):
        self.start.move_down(y)
        self.end.move_down(y)

    def move_right(self, x):
        self.start.move_right(x)
        self.end.move_right(x)

    def move_left(self, x):
        self.start.move_left(x)
        self.end.move_left(x)

    def move_raise(self, z):
        self.start.move_raise(z)
        self.end.move_raise(z)

    def move_lower(self, z):
        self.start.move_lower(z)
        self.end.move_lower(z)




