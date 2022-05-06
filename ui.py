
import pygame
import pygame_gui
import deblur
import blurs

import typing


class UiControlledIterativeGhastDeblurrer(deblur.AbstractIterativeGhastDeblurrer):

    def __init__(self, settings: 'SimulationSettings', deblur_settings: 'BlurSettings'):
        super().__init__()
        self.settings = settings
        self.deblur_settings = deblur_settings

    def get_correction_intensity(self, iteration):
        return self.settings.get_correction_intensity(iteration)

    def do_blur(self, surf: pygame.Surface, strength=1.0) -> pygame.Surface:
        return self.deblur_settings.do_blur(surf, strength=strength)

    def get_iteration_limit(self) -> int:
        return self.settings.iteration_limit


class State:

    def __init__(self, blur_settings=None, deblur_settings=None, simulation_settings=None):
        self.original_image_file = None
        self.original_image = None

        self.target_image_file = None
        self.target_image = None

        self.blur_settings = blur_settings or BlurSettings()
        self.simulation = UiControlledIterativeGhastDeblurrer(simulation_settings or SimulationSettings(),
                                                              deblur_settings or BlurSettings())

    def set_original_image(self, surf: pygame.Surface, filename: str = None):
        self.original_image_file = filename
        self.original_image = surf

    def set_target_image(self, surf: pygame.Surface, filename: str = None):
        self.target_image_file = filename
        self.target_image = surf

        self.simulation.set_target_image(surf)
        self.simulation.reset()

    def get_blur_settings(self):
        return self.blur_settings

    def get_deblur_settings(self):
        return self.simulation.deblur_settings

    def get_simulation_settings(self):
        return self.simulation.settings


class BlurSettings:

    def __init__(self):
        self.blur_type = "box"
        self.radius = 3
        self.bonus_params = {}

    def do_blur(self, surf, strength=1.0):
        my_blur = blurs.get_blur_func(self.blur_type)
        return my_blur(surf, round(strength * self.radius), params=self.bonus_params)


class SimulationSettings:

    def __init__(self):
        self.iteration_limit = 100
        self.start_intensity = 4
        self.end_intensity = 3
        self.intensity_curve = "linear"

    def get_correction_intensity(self, iterations):
        if iterations >= self.iteration_limit:
            return self.end_intensity
        elif iterations <= 0:
            return self.start_intensity
        elif self.intensity_curve == "linear":
            return self.start_intensity + (iterations / self.iteration_limit) * (self.end_intensity - self.start_intensity)
        else:
            raise ValueError(f"Unknown intensity_curve style: {self.intensity_curve}")


def split_rect(rect: pygame.Rect, n: int, horizontally=True) -> typing.List[pygame.Rect]:
    if horizontally:
        xs = [int(rect[2] / n * i) for i in range(n + 1)]
        return [pygame.Rect(xs[i], rect[1], xs[i + 1] - xs[i], rect[3]) for i in range(n)]
    else:
        ys = [int(rect[3] / n * i) for i in range(n + 1)]
        return [pygame.Rect(rect[0], ys[i], rect[2], ys[i + 1] - ys[i]) for i in range(n)]


def render_in_rect_responsibly(img: pygame.Surface, rect: pygame.Rect, dest: pygame.Surface, integer_upscale_only=True):
    if img is not None:
        w, h = img.get_size()

        scale = min(rect.width / w, rect.height / h)
        if scale > 1 and integer_upscale_only:
            scale = int(scale)
        scaled_img = pygame.transform.scale(img, (int(w * scale), int(h * scale)))

        x = rect.centerx - scaled_img.get_width() // 2
        y = rect.centery - scaled_img.get_height() // 2
        dest.blit(scaled_img, (x, y))


_ALL_MODES = []

def _new_mode(name) -> str:
    _ALL_MODES.append(name)
    return name


class Modes:
    DEBLUR = _new_mode("deblur")
    BLUR_AND_DEBLUR = _new_mode("blur_deblur")

    @staticmethod
    def all_modes():
        return _ALL_MODES


class MainWindow:

    def __init__(self, size=(640, 480)):
        self.state: State = State()

        # viewing options
        self.view_mode = Modes.all_modes()[0]
        self.autoplay = True
        self.hide_controls = False
        self.integer_upscale = False

        self._base_size = size
        self._fps = 60
        self._clock = None
        self._ui_manager = None

    def set_view_mode(self, mode):
        self.view_mode = mode

    def _pre_update(self, dt):
        pass

    def _update(self, dt):
        self._ui_manager.update(dt)

        simul = self.state.simulation
        if self.autoplay and simul.get_iteration() < simul.get_iteration_limit():
            simul.step()

        caption = f"DEBLUR [iter={simul.get_iteration()}, error={simul.get_error():.2f}]"
        pygame.display.set_caption(caption)

    def _render(self):
        screen = pygame.display.get_surface()
        screen.fill((0, 0, 0))

        if self.view_mode == Modes.BLUR_AND_DEBLUR:
            self._render_blur_and_deblur_mode()
        else:
            self._render_deblur_mode()

        self._ui_manager.draw_ui(screen)

    def _render_blur_and_deblur_mode(self):
        screen = pygame.display.get_surface()
        full_rect = screen.get_rect()

        top_ratio = 0.666 if not self.hide_controls else 1.0
        image_rect = pygame.Rect(full_rect[0], full_rect[1], full_rect[2], full_rect[3] * top_ratio)
        split_3x1 = split_rect(image_rect, 3, horizontally=True)
        images = [self.state.original_image, self.state.target_image, self.state.simulation.get_output_image()]

        for i in range(len(split_3x1)):
            render_in_rect_responsibly(images[i], split_3x1[i], screen, integer_upscale_only=True)

    def _render_deblur_mode(self):
        screen = pygame.display.get_surface()
        full_rect = screen.get_rect()

        top_ratio = 0.666 if not self.hide_controls else 1.0
        image_rect = pygame.Rect(full_rect[0], full_rect[1], full_rect[2], full_rect[3] * top_ratio)
        vert_split = split_rect(image_rect, 2, horizontally=False)
        split_2x2 = split_rect(vert_split[0], 2) + split_rect(vert_split[1], 2)

        images = [self.state.target_image, self.state.simulation.get_output_image(),
                  self.state.simulation.get_blurred_output_image(), self.state.simulation.get_error_image()]

        for i in range(len(split_2x2)):
            render_in_rect_responsibly(images[i], split_2x2[i], screen, integer_upscale_only=False)

    def run(self):
        pygame.init()

        pygame.display.set_mode(self._base_size, pygame.RESIZABLE)

        self._clock = pygame.time.Clock()
        self._ui_manager = pygame_gui.UIManager(self._base_size)

        running = True
        while running:
            dt = self._clock.tick(self._fps) / 1000.0

            self._pre_update(dt)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_r:
                        print("INFO: resetting deblur simulation [press R]")
                        self.state.simulation.reset()
                    elif e.key == pygame.K_p:
                        self.autoplay = not self.autoplay
                        print(f"INFO: {'un' if self.autoplay else ''}paused simulation [toggle with P]")
                    elif e.key == pygame.K_h:
                        self.hide_controls = not self.hide_controls
                        print(f"INFO: {'un' if not self.hide_controls else ''}hiding controls [toggle with H]")
                    elif e.key == pygame.K_m:
                        mode_idx = Modes.all_modes().index(self.view_mode)
                        self.view_mode = Modes.all_modes()[(mode_idx + 1) % len(Modes.all_modes())]
                        print(f"INFO: set viewing mode to {self.view_mode} [toggle with M]")
                    elif e.key == pygame.K_SPACE:
                        self.state.simulation.step()
                self._ui_manager.process_events(e)

            self._update(dt)
            self._render()

            pygame.display.flip()


if __name__ == "__main__":
    win = MainWindow()
    # win.state.set_original_image(pygame.image.load("data/3x3_circle_in_10x10_orig.png"))
    # win.state.set_target_image(pygame.image.load("data/3x3_circle_in_10x10.png"))
    win.state.set_original_image(pygame.image.load("data/splash.png"))
    win.state.set_target_image(pygame.image.load("data/splash_blurred_15.png"))

    win.state.simulation.deblur_settings.blur_type = "gaussian"
    win.state.simulation.deblur_settings.radius = 25

    win.run()

