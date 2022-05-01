
import pygame
import pygame_gui
import deblur


class State:

    def __init__(self):
        self.original_image_file = None
        self.original_image = None

        self.blurred_image_file = None
        self.blurred_image = None

        self.blur_settings = BlurSettings()
        self.deblur_settings = BlurSettings()

        self.simulation = Simulation(self)
        self.simulation_settings = SimulationSettings()

    def set_original_image(self, surf: pygame.Surface, filename: str = None):
        self.original_image_file = filename
        self.original_image = pygame.image.load(self.original_image_file)

    def set_blurred_image(self, surf: pygame.Surface, filename: str = None):
        self.blurred_image_file = filename
        self.blurred_image = surf


class BlurSettings:

    def __init__(self):
        self.blur_type = "box"
        self.blur_params = {"radius": 10}


class SimulationSettings:

    def __init__(self):
        self.iteration_limit = 100
        self.start_intensity = 3
        self.end_intensity = 1
        self.intensity_curve = "linear"
        self.blur_and_unblur = True
        self.autoplay = True
