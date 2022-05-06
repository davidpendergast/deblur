import enum

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


class Modes(enum.Enum):

    DEBLUR = "deblur"
    BLUR_AND_DEBLUR = "blur_deblur"


class DeblurController:

    def __init__(self, rect, manager, deblur_settings):
        self.settings = deblur_settings

        self.container = pygame_gui.elements.UIScrollingContainer(relative_rect=rect, manager=manager)
        self.title_label = pygame_gui.elements.UILabel(relative_rect=pygame.Rect(0, 0, rect.width, 24), text="Deblur",
                                                       manager=manager, container=self.container,
                                                       anchors={"left": "left", "top": "top", "right": "right", "bottom": "bottom"})

    def set_rect(self, rect):
        if rect is None or rect.width <= 0 or rect.height <= 0:
            self.container.hide()
        else:
            self.container.show()
            self.container.set_relative_position(rect.topleft)
            self.container.set_dimensions(rect.size)

    def handle_event(self, event):
        pass

    def update(self, rect, dt):
        pass


class ViewItems(enum.Enum):

    TARGET_IMAGE_PANE = "target_img"
    ORIGINAL_IMAGE_PANE = "original_img"
    OUTPUT_IMAGE_PANE = "output_img"
    BLURRED_OUTPUT_IMAGE_PANE = "blurred_output_img"
    ERROR_IMAGE = "error_img"

    BLUR_CONTROLS = "blur_controls"
    SIMULATION_CONTROLS = "simulation_controls"
    DEBLUR_CONTROLS = "deblur_controls"


class MainWindow:

    def __init__(self, size=(640, 480)):
        self.state: State = State()

        # viewing options
        self.view_mode = Modes.DEBLUR
        self.autoplay = True
        self.hide_controls = False
        self.integer_upscale = False

        self.blur_controls = None
        self.simulation_controls = None
        self.deblur_controls = None

        self._base_size = size
        self._fps = 60
        self._clock = None
        self._ui_manager = None

    def set_view_mode(self, mode):
        self.view_mode = mode

    def get_layout(self):
        layout = {key: None for key in ViewItems}
        full_rect = pygame.display.get_surface().get_rect()

        if self.view_mode == Modes.DEBLUR:
            top_ratio = 0.666 if not self.hide_controls else 1.0
            image_rect = pygame.Rect(full_rect[0], full_rect[1], full_rect[2], full_rect[3] * top_ratio)
            vert_split = split_rect(image_rect, 2, horizontally=False)
            split_2x2 = split_rect(vert_split[0], 2) + split_rect(vert_split[1], 2)

            layout[ViewItems.TARGET_IMAGE_PANE] = split_2x2[0]
            layout[ViewItems.OUTPUT_IMAGE_PANE] = split_2x2[1]
            layout[ViewItems.BLURRED_OUTPUT_IMAGE_PANE] = split_2x2[2]
            layout[ViewItems.ERROR_IMAGE] = split_2x2[3]

            if not self.hide_controls:
                controls_rect = pygame.Rect(full_rect[0], image_rect[1] + image_rect[3], full_rect[2],
                                            full_rect[1] + full_rect[3] - (image_rect[1] + image_rect[3]))
                bottom_2x1 = split_rect(controls_rect, 2, horizontally=True)
                layout[ViewItems.SIMULATION_CONTROLS] = bottom_2x1[0]
                layout[ViewItems.DEBLUR_CONTROLS] = bottom_2x1[1]

            return layout
        elif self.view_mode == Modes.BLUR_AND_DEBLUR:
            top_ratio = 0.666 if not self.hide_controls else 1.0
            image_rect = pygame.Rect(full_rect[0], full_rect[1], full_rect[2], full_rect[3] * top_ratio)
            split_3x1 = split_rect(image_rect, 3, horizontally=True)

            layout[ViewItems.ORIGINAL_IMAGE_PANE] = split_3x1[0]
            layout[ViewItems.TARGET_IMAGE_PANE] = split_3x1[1]
            layout[ViewItems.OUTPUT_IMAGE_PANE] = split_3x1[2]

            if not self.hide_controls:
                controls_rect = pygame.Rect(full_rect[0], image_rect[1] + image_rect[3], full_rect[2],
                                            full_rect[1] + full_rect[3] - (image_rect[1] + image_rect[3]))
                bottom_3x1 = split_rect(controls_rect, 3, horizontally=True)

                layout[ViewItems.BLUR_CONTROLS] = bottom_3x1[0]
                layout[ViewItems.SIMULATION_CONTROLS] = bottom_3x1[1]
                layout[ViewItems.DEBLUR_CONTROLS] = bottom_3x1[2]

        return layout

    def _update_ui_positions(self, layout):
        controls = {
            ViewItems.SIMULATION_CONTROLS: self.simulation_controls,
            ViewItems.BLUR_CONTROLS: self.blur_controls,
            ViewItems.DEBLUR_CONTROLS: self.deblur_controls
        }
        for key, rect in layout.items():
            if key in controls:
                if controls[key] is not None:
                    controls[key].set_rect(rect)

    def _update(self, dt, layout):
        self._update_ui_positions(layout)
        self._ui_manager.update(dt)

        simul = self.state.simulation
        if self.autoplay and simul.get_iteration() < simul.get_iteration_limit():
            simul.step()

        caption = f"DEBLUR [iter={simul.get_iteration()}, error={simul.get_error():.2f}]"
        pygame.display.set_caption(caption)

    def _render(self, layout):
        screen = pygame.display.get_surface()
        screen.fill((0, 0, 0))

        self._render_layout(layout)
        self._ui_manager.draw_ui(screen)

    def _render_layout(self, layout):
        images = {
            ViewItems.TARGET_IMAGE_PANE: self.state.target_image,
            ViewItems.OUTPUT_IMAGE_PANE: self.state.simulation.get_output_image(),
            ViewItems.BLURRED_OUTPUT_IMAGE_PANE: self.state.simulation.get_blurred_output_image(),
            ViewItems.ERROR_IMAGE: self.state.simulation.get_error_image()
        }
        screen = pygame.display.get_surface()
        for key, rect in layout.items():
            if key in images and rect is not None and rect.width >= 0 and rect.height >= 0:
                render_in_rect_responsibly(images[key], rect, screen, integer_upscale_only=self.integer_upscale)

    def run(self):
        pygame.init()

        pygame.display.set_mode(self._base_size, pygame.RESIZABLE)

        self._clock = pygame.time.Clock()
        self._ui_manager = pygame_gui.UIManager(self._base_size)

        self.deblur_controls = DeblurController(pygame.Rect(100, 100, 200, 200), self._ui_manager, self.state.get_deblur_settings())

        running = True
        while running:
            dt = self._clock.tick(self._fps) / 1000.0

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
                        all_modes = [m for m in Modes]
                        mode_idx = all_modes.index(self.view_mode)
                        self.view_mode = all_modes[(mode_idx + 1) % len(all_modes)]
                        print(f"INFO: set viewing mode to {self.view_mode} [toggle with M]")
                    elif e.key == pygame.K_i:
                        self.integer_upscale = not self.integer_upscale
                        print(f"INFO: integer upscaling only set to {self.integer_upscale} [toggle with I]")
                    elif e.key == pygame.K_SPACE:
                        self.state.simulation.step()
                self._ui_manager.process_events(e)

            layout = self.get_layout()

            self._update(dt, layout)
            self._render(layout)

            pygame.display.flip()


if __name__ == "__main__":
    win = MainWindow()
    # win.state.set_original_image(pygame.image.load("data/3x3_circle_in_10x10_orig.png"))
    # win.state.set_target_image(pygame.image.load("data/3x3_circle_in_10x10.png"))
    win.state.set_original_image(pygame.image.load("data/splash.png"))
    win.state.set_target_image(pygame.image.load("data/splash_blurred_15.png"))

    win.state.simulation.deblur_settings.blur_type = "gaussian"
    win.state.simulation.deblur_settings.radius = 15

    win.run()

