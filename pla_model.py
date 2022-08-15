# Author: Craig Harris
# GitHub Username: cxhx441
# Description:

class Point():
    def __init__(self, xyz_coords: tuple) -> None:
        self.x_pos, self.y_pos, self.z_pos = xyz_coords

    def get_coords(self):
        return self.x_pos, self.y_pos

    def move_up(self, y):
        self.y_pos -= y

    def move_down(self, y):
        self.y_pos += y

    def move_right(self, x):
        self.x_pos += x

    def move_left(self, x):
        self.x_pos -= x


class NoiseLevel:
    def __init__(self, dBA: float, octave_bands: list[float] = None):
        if octave_bands is None:
            self.dBA = dBA
        self.octave_bands = octave_bands
        self.dBA = dBA


class Source(Point):
    def __init__(self,
                 xyz_coords: tuple,
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
    def __init__(self,
                 xyz_coords: tuple,
                 dBA_limit: int,
                 dBA: float = None
                 ) -> None:
        super().__init__(xyz_coords)
        self.dBA_limit = dBA_limit
        self.dBA = dBA






