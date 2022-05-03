
import pygame
import pygame_gui
import deblur
import blurs


class UiControlledIterativeGhastDeblurrer(deblur.AbstractIterativeGhastDeblurrer):

    def __init__(self, simulation_settings: 'SimulationSettings', deblur_settings: 'BlurSettings'):
        super().__init__()
        self.simulation_settings = simulation_settings
        self.deblur_settings = deblur_settings

    def get_correction_intensity(self, iteration):
        return self.simulation_settings.get_correction_intensity(iteration)

    def do_blur(self, surf: pygame.Surface, strength=1.0) -> pygame.Surface:
        return self.deblur_settings.do_blur(surf, strength=strength)

    def get_iteration_limit(self) -> int:
        return self.simulation_settings.iteration_limit


class State:

    def __init__(self):
        self.original_image_file = None
        self.original_image = None

        self.blurred_image_file = None
        self.blurred_image = None

        self.blur_settings = BlurSettings()
        self.deblur_settings = BlurSettings()
        self.simulation_settings = SimulationSettings()

        self.simulation = UiControlledIterativeGhastDeblurrer(self.simulation_settings, self.deblur_settings)

    def set_original_image(self, surf: pygame.Surface, filename: str = None):
        self.original_image_file = filename
        self.original_image = surf

    def set_blurred_image(self, surf: pygame.Surface, filename: str = None):
        self.blurred_image_file = filename
        self.blurred_image = surf


class BlurSettings:

    def __init__(self):
        self.blur_type = "box"
        self.radius = 10
        self.bonus_params = {}

    def do_blur(self, surf, strength=1.0):
        my_blur = blurs.get_blur_func(self.blur_type)
        return my_blur(surf, round(strength * self.radius), params=self.bonus_params)


class SimulationSettings:

    def __init__(self):
        self.iteration_limit = 100
        self.start_intensity = 3
        self.end_intensity = 1
        self.intensity_curve = "linear"
        self.blur_and_unblur = True
        self.autoplay = True

    def get_correction_intensity(self, iterations):
        if iterations >= self.iteration_limit:
            return self.end_intensity
        elif iterations <= 0:
            return self.start_intensity
        elif self.intensity_curve == "linear":
            return self.start_intensity + (iterations / self.iteration_limit) * (self.end_intensity - self.start_intensity)
        else:
            raise ValueError(f"Unknown intensity_curve style: {self.intensity_curve}")


class MainWindow:

    def __init__(self, size=(640, 480)):
        self.state = State()
        self._base_size = size
        self._fps = 60
        self._clock = None
        self._ui_manager = None

    def run(self):
        pygame.init()

        pygame.display.set_mode(self._base_size, pygame.RESIZABLE)

        self._clock = pygame.time.Clock()
        self._ui_manager = pygame_gui.UIManager(self._base_size)

        running = True
        while running:
            dt = self._clock.tick(self._fps) / 1000.0
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                self._ui_manager.process_events(e)

            self._ui_manager.update(dt)

            screen = pygame.display.get_surface()
            screen.fill((0, 0, 0))
            self._ui_manager.draw_ui(screen)

            pygame.display.flip()


if __name__ == "__main__":
    win = MainWindow()
    win.state.set_blurred_image(pygame.image.load("data/splash_blurred_15.png"), "data/splash_blurred_15.png")
    win.run()

