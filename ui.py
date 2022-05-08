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

    def show_relative_error(self):
        return self.settings.show_relative_error

    def get_backpropagation_blur_strength(self) -> float:
        return self.deblur_settings.backpropagation_blur_strength

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

        self.autoplay = True

    def set_original_image(self, surf: pygame.Surface, filename: str = None):
        self.original_image_file = filename
        self.original_image = surf

        if self.original_image is not None and self.target_image_file is None:
            self.set_target_image(self.get_blur_settings().do_blur(self.original_image))

    def set_target_image(self, surf: pygame.Surface, filename: str = None):
        self.target_image_file = filename
        self.target_image = surf

        self.simulation.set_target_image(surf)
        self.simulation.reset()

    def get_blur_settings(self) -> 'BlurSettings':
        return self.blur_settings

    def get_deblur_settings(self) -> 'BlurSettings':
        return self.simulation.deblur_settings

    def get_simulation_settings(self) -> 'SimulationSettings':
        return self.simulation.settings

    def regenerate_target_image(self):
        if self.target_image_file is not None:
            pass  # we're not using a generated target image, no-op
        elif self.original_image is not None:
            self.set_target_image(self.get_blur_settings().do_blur(self.original_image))
        else:
            self.set_target_image(None)


class BlurSettings:

    def __init__(self):
        self.blur_type = "gaussian"
        self.max_radius = 100
        self.radius = 15
        self.backpropagation_blur_strength = 1.0
        self.bonus_params = {}

    def do_blur(self, surf, strength=1.0):
        effective_radius = round(strength * self.radius)
        if effective_radius > 0:
            my_blur = blurs.get_blur_func(self.blur_type)
            return my_blur(surf, effective_radius, params=self.bonus_params)
        else:
            return surf.copy()


class SimulationSettings:

    def __init__(self):
        self.iteration_limit = 50
        self.start_intensity = 4
        self.end_intensity = 3
        self.intensity_curve = "linear"
        self.show_relative_error = True

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


def title_case(text):
    return " ".join(map(lambda w: w[0:1].upper() + w[1:] if len(w) >= 2 else w.upper(), text.split(" ")))


class Modes(enum.Enum):

    DEBLUR = "deblur"
    BLUR_AND_DEBLUR = "blur_deblur"


LINE_HEIGHT = 24
SHORT_LABEL_WIDTH = 6 * 24
SMALL_GAP = 4


class ControlPanel:

    def __init__(self, rect, manager):
        self.panel = self.build_panel(rect, manager)
        self.item_layouts = []

        self.insets = (5, 0, 10, 0)

    def build_panel(self, rect, manager):
        return pygame_gui.elements.UIPanel(rect, starting_layer_height=2, manager=manager)

    def update(self, rect: pygame.Rect):
        if rect is None or rect.width <= self.insets[0] * 2 or rect.height <= self.insets[1] * 2:
            self.panel.hide()
        else:
            self.panel.show()
            self.panel.set_relative_position(rect.topleft)
            self.panel.set_dimensions(rect.size)

            rect = pygame.Rect(rect.x + self.insets[0],
                               rect.y + self.insets[1],
                               rect.width - (self.insets[0] + self.insets[2]),
                               rect.height - (self.insets[1] + self.insets[3]))

            y = self.insets[1]
            for (item, height) in self.item_layouts:
                if isinstance(item, list):
                    exact_space = 0
                    total_weight = 0
                    for (subitem, weight) in item:
                        if isinstance(weight, int):
                            exact_space += weight
                        elif isinstance(weight, float):
                            total_weight += weight
                    x = self.insets[0]
                    flex_space = max(0, rect.width - exact_space)
                    for (subitem, weight) in item:
                        subitem_width = weight if isinstance(weight, int) else round(flex_space * weight / total_weight)
                        subitem.set_relative_position((x, y))
                        subitem.set_dimensions((subitem_width, height))
                        x += subitem_width
                elif item is not None:
                    item.set_relative_position((self.insets[0], y))
                    item.set_dimensions((rect.width, height))
                y += height

    def get_minimum_height(self):
        return sum(map(lambda x: x[1], self.item_layouts))


class BlurControlPanel(ControlPanel):

    def __init__(self, rect, manager, state, deblur=False):
        super().__init__(rect, manager)
        self.is_deblur = deblur
        self.state = state
        self.settings = state.get_blur_settings() if not self.is_deblur else state.get_deblur_settings()

        Deb = "Deb" if self.is_deblur else "B"  # the *only* valid reason to have an uppercase var name
        de = "de" if self.is_deblur else ""

        self.title_label = pygame_gui.elements.UILabel(
            pygame.Rect(0, 0, rect.width, 24), f"{Deb}lur Settings",
            manager=manager, container=self.panel,
        )

        self.blur_type_selector = pygame_gui.elements.UIDropDownMenu(
            list(map(title_case, blurs.get_all_blurs())),
            title_case(self.settings.blur_type),
            pygame.Rect(0, 24, rect.width, 24),
            manager, container=self.panel,
            object_id=f"#{de}blur_blur_type"
        )

        self.radius_slider = pygame_gui.elements.UIHorizontalSlider(
            pygame.Rect(0, 69, rect.width, 24), self.settings.radius, (0.0, self.settings.max_radius), manager,
            container=self.panel, click_increment=1, object_id=f"#{de}blur_radius"
        )

        self.radius_label = pygame_gui.elements.UILabel(
            pygame.Rect(0, 48, rect.width, 24), f"Radius: {self.settings.radius}",
            manager=manager, container=self.panel,
            object_id=pygame_gui.core.ObjectID(class_id="@left_aligned", object_id="label")
        )

        if self.is_deblur:
            self.advanced_options_label = pygame_gui.elements.UILabel(
                rect, "Advanced Options",
                manager=manager, container=self.panel,
            )

            self.start_intensity_label = pygame_gui.elements.UILabel(
                rect, "Start Intensity: -1",
                manager=manager, container=self.panel,
                object_id=pygame_gui.core.ObjectID(class_id="@left_aligned", object_id="label")
            )

            self.end_intensity_label = pygame_gui.elements.UILabel(
                rect, "End Intensity: -1",
                manager=manager, container=self.panel,
                object_id=pygame_gui.core.ObjectID(class_id="@left_aligned", object_id="label")
            )

            self.correction_intensity_lower_slider = pygame_gui.elements.UIHorizontalSlider(
                rect, int(self.state.get_simulation_settings().start_intensity * 10), (0, 50), manager,
                container=self.panel, click_increment=1, object_id="#lower_intensity_slider"
            )

            self.correction_intensity_upper_slider = pygame_gui.elements.UIHorizontalSlider(
                rect, int(self.state.get_simulation_settings().end_intensity * 10), (0, 50), manager,
                container=self.panel, click_increment=1, object_id="#upper_intensity_slider"
            )

            self.backpropagation_blur_strength_label = pygame_gui.elements.UILabel(
                rect, "Anti-Blur: 100%", manager=manager, container=self.panel,
                object_id=pygame_gui.core.ObjectID(class_id="@left_aligned", object_id="label")
            )

            self.backpropagation_blur_strength_slider = pygame_gui.elements.UIHorizontalSlider(
                rect, int(self.state.get_deblur_settings().backpropagation_blur_strength * 100), (0, 150), manager,
                container=self.panel, click_increment=1, object_id="#bp_blur_strength_slider",
            )

        self.item_layouts = [
            (self.title_label, LINE_HEIGHT),
            (None, SMALL_GAP),
            (self.blur_type_selector, LINE_HEIGHT),
            ([(self.radius_label, SHORT_LABEL_WIDTH), (self.radius_slider, 1.0)], LINE_HEIGHT)
        ]

        if self.is_deblur:
            self.item_layouts.extend([
                (None, SMALL_GAP),
                (self.advanced_options_label, LINE_HEIGHT),
                ([(self.start_intensity_label, SHORT_LABEL_WIDTH), (self.correction_intensity_lower_slider, 1.0)], LINE_HEIGHT),
                ([(self.end_intensity_label, SHORT_LABEL_WIDTH), (self.correction_intensity_upper_slider, 1.0)], LINE_HEIGHT),
                ([(self.backpropagation_blur_strength_label, SHORT_LABEL_WIDTH), (self.backpropagation_blur_strength_slider, 1.0)], LINE_HEIGHT)
            ])
        self.item_layouts.append((None, SMALL_GAP))

        self.update(rect)

    def update(self, rect):
        self.radius_label.set_text(f"Radius: {self.settings.radius}")

        if self.is_deblur:
            simul_settings = self.state.get_simulation_settings()  # TODO this should probably be in blur settings
            self.start_intensity_label.set_text(f"High Power: {simul_settings.start_intensity:.1f}")
            self.end_intensity_label.set_text(  f"Low Power:  {simul_settings.end_intensity:.1f}")

            bp_blur_str = int(self.state.get_deblur_settings().backpropagation_blur_strength * 100)
            self.backpropagation_blur_strength_label.set_text( f"Anti-Blur:  {bp_blur_str}%")

        super().update(rect)


def set_enabled(comp_list, val):
    if not isinstance(comp_list, list):
        comp_list = [comp_list]
    for comp in comp_list:
        if val:
            comp.enable()
        else:
            comp.disable()


class SimulationControlPanel(ControlPanel):

    def __init__(self, rect, manager, state):
        super().__init__(rect, manager)
        self.state = state

        self.title_label = pygame_gui.elements.UILabel(
            pygame.Rect(0, 0, rect.width, 24), f"Simulation",
            manager=manager, container=self.panel,
        )

        self.stop_button = pygame_gui.elements.UIButton(
            rect, "⏹", manager, container=self.panel,
            tool_tip_text="Reset and pause the simulation.",
            object_id=pygame_gui.core.ObjectID(
                class_id="@emoji_label",
                object_id="#simulation_stop"
            )
        )

        self.restart_button = pygame_gui.elements.UIButton(
            rect, "🔄", manager, container=self.panel,
            tool_tip_text="Restart the simulation.",
            object_id=pygame_gui.core.ObjectID(
                class_id="@emoji_label",
                object_id="#simulation_restart"
            )
        )

        self.reset_button = pygame_gui.elements.UIButton(
            rect, "⏩", manager, container=self.panel,
            tool_tip_text="Reset iterations to 0 (but leave image unchanged).",
            object_id=pygame_gui.core.ObjectID(
                class_id="@emoji_label",
                object_id="#simulation_reset"
            )
        )

        self.play_pause_button = pygame_gui.elements.UIButton(
            rect, "▶", manager, container=self.panel,
            tool_tip_text="Play or pause.",
            object_id=pygame_gui.core.ObjectID(
                class_id="@emoji_label",
                object_id="#simulation_play_pause"
            )
        )

        self.step_button = pygame_gui.elements.UIButton(
            rect, "⏭", manager, container=self.panel,
            tool_tip_text="Perform a single iteration.",
            object_id=pygame_gui.core.ObjectID(
                class_id="@emoji_label",
                object_id="#simulation_step"
            )
        )

        self.error_label = pygame_gui.elements.UILabel(
            rect, f"Error: {0.0}",
            manager=manager, container=self.panel,
        )

        self.iterations_label = pygame_gui.elements.UILabel(
            rect, f"Iteration: -1",
            manager=manager, container=self.panel
        )

        self.max_iterations_label = pygame_gui.elements.UILabel(
            rect, "Iteration Limit: ", manager, container=self.panel,
            object_id=pygame_gui.core.ObjectID(class_id="@left_aligned", object_id="label")
        )

        self.max_iterations_slider = pygame_gui.elements.UIHorizontalSlider(
            rect, self.state.get_simulation_settings().iteration_limit, (0, 250), manager,
            container=self.panel, click_increment=1, object_id=f"#simulation_iteration_limit"
        )

        self.item_layouts = [
            (self.title_label, LINE_HEIGHT),
            (None, SMALL_GAP),
            ([(self.iterations_label, 0.5), (self.error_label, 0.5)], LINE_HEIGHT),
            ([
                (self.stop_button, 1.0),
                (self.restart_button, 1.0),
                (self.play_pause_button, 1.0),
                (self.reset_button, 1.0),
                (self.step_button, 1.0)
            ], LINE_HEIGHT),
            (None, SMALL_GAP),
            ([(self.max_iterations_label, SHORT_LABEL_WIDTH), (self.max_iterations_slider, 1.0)], LINE_HEIGHT),
            (None, LINE_HEIGHT * 2)
        ]

        self.update(rect)

    def update(self, rect):
        simul: deblur.AbstractIterativeGhastDeblurrer = self.state.simulation

        self.iterations_label.set_text(f"Iteration: {simul.get_iteration()}/{simul.get_iteration_limit()}")
        self.error_label.set_text(f"Error: {simul.get_error():.2f}")

        self.play_pause_button.set_text("⏸" if self.state.autoplay else "▶")

        super().update(rect)


class ViewItems(enum.Enum):

    TARGET_IMAGE_PANE = "target_img"
    ORIGINAL_IMAGE_PANE = "original_img"
    OUTPUT_IMAGE_PANE = "output_img"
    BLURRED_OUTPUT_IMAGE_PANE = "blurred_output_img"
    ERROR_IMAGE_PANE = "error_img"

    BLUR_CONTROLS = "blur_controls"
    SIMULATION_CONTROLS = "simulation_controls"
    DEBLUR_CONTROLS = "deblur_controls"


class MainWindow:

    def __init__(self, size=(960, 480)):
        self.state: State = State()

        # viewing options
        self.view_mode = Modes.DEBLUR
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
            controls_height = max(self.simulation_controls.get_minimum_height(),
                                  self.deblur_controls.get_minimum_height())
            image_rect_height = full_rect[3] if self.hide_controls else full_rect[3] - controls_height
            image_rect = pygame.Rect(full_rect[0], full_rect[1], full_rect[2], image_rect_height)
            vert_split = split_rect(image_rect, 2, horizontally=False)
            split_2x2 = split_rect(vert_split[0], 2) + split_rect(vert_split[1], 2)

            layout[ViewItems.TARGET_IMAGE_PANE] = split_2x2[0]
            layout[ViewItems.OUTPUT_IMAGE_PANE] = split_2x2[1]
            layout[ViewItems.BLURRED_OUTPUT_IMAGE_PANE] = split_2x2[2]
            layout[ViewItems.ERROR_IMAGE_PANE] = split_2x2[3]

            if not self.hide_controls:
                controls_rect = pygame.Rect(full_rect[0], image_rect[1] + image_rect[3], full_rect[2],
                                            full_rect[1] + full_rect[3] - (image_rect[1] + image_rect[3]))
                bottom_2x1 = split_rect(controls_rect, 2, horizontally=True)
                layout[ViewItems.SIMULATION_CONTROLS] = bottom_2x1[0]
                layout[ViewItems.DEBLUR_CONTROLS] = bottom_2x1[1]

            return layout
        elif self.view_mode == Modes.BLUR_AND_DEBLUR:
            controls_height = max(self.blur_controls.get_minimum_height(),
                                  self.simulation_controls.get_minimum_height(),
                                  self.deblur_controls.get_minimum_height())
            image_rect_height = full_rect[3] if self.hide_controls else full_rect[3] - controls_height
            image_rect = pygame.Rect(full_rect[0], full_rect[1], full_rect[2], image_rect_height)
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
                    controls[key].update(rect)

    def _update(self, dt, layout):
        self._update_ui_positions(layout)
        self._ui_manager.update(dt)

        simul = self.state.simulation
        if self.state.autoplay and not simul.is_finished_iterating():
            simul.step()

        caption = f"DEBLUR [iter={simul.get_iteration()}, error={simul.get_error():.2f}, fps={self._clock.get_fps():.1f}]"
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
            ViewItems.ERROR_IMAGE_PANE: self.state.simulation.get_error_image(),
            ViewItems.ORIGINAL_IMAGE_PANE: self.state.original_image
        }
        screen = pygame.display.get_surface()
        for key, rect in layout.items():
            if key in images and rect is not None and rect.width >= 0 and rect.height >= 0:
                render_in_rect_responsibly(images[key], rect, screen, integer_upscale_only=self.integer_upscale)

    def handle_potential_ui_event(self, e):
        if e.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
            if "#deblur_blur_type" in e.ui_object_id:
                self.state.get_deblur_settings().blur_type = e.text
                self.state.simulation.reset(iter_count=True, img=False)
            elif "#blur_blur_type" in e.ui_object_id:
                self.state.get_blur_settings().blur_type = e.text
                self.state.regenerate_target_image()
        elif e.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED:
            if "#deblur_radius" in e.ui_object_id:
                if int(e.value) != self.state.get_deblur_settings().radius:
                    self.state.get_deblur_settings().radius = int(e.value)
                    self.state.simulation.reset(iter_count=True, img=False)
            elif "#blur_radius" in e.ui_object_id:
                if int(e.value) != self.state.get_blur_settings().radius:
                    self.state.get_blur_settings().radius = int(e.value)
                    self.state.regenerate_target_image()
            elif "#lower_intensity_slider" in e.ui_object_id:
                if int(e.value) / 10.0 != self.state.get_simulation_settings().start_intensity:
                    self.state.get_simulation_settings().start_intensity = int(e.value) / 10.0
                    self.state.simulation.reset(iter_count=True, img=False)
            elif "#upper_intensity_slider" in e.ui_object_id:
                if int(e.value) / 10.0 != self.state.get_simulation_settings().end_intensity:
                    self.state.get_simulation_settings().end_intensity = int(e.value) / 10.0
                    self.state.simulation.reset(iter_count=True, img=False)
            elif "#simulation_iteration_limit" in e.ui_object_id:
                if int(e.value) != self.state.get_simulation_settings().iteration_limit:
                    self.state.get_simulation_settings().iteration_limit = int(e.value)
            elif "#bp_blur_strength_slider" in e.ui_object_id:
                if int(e.value) != int(self.state.get_deblur_settings().backpropagation_blur_strength * 100):
                    self.state.get_deblur_settings().backpropagation_blur_strength = e.value / 100.0
                    self.state.simulation.reset(iter_count=True, img=False)
        elif e.type == pygame_gui.UI_BUTTON_PRESSED:
            if "#simulation_play_pause" in e.ui_object_id:
                self.state.autoplay = not self.state.autoplay
            elif "#simulation_reset" in e.ui_object_id:
                self.state.simulation.reset(iter_count=True, img=False)
                self.state.autoplay = True
            elif "#simulation_restart" in e.ui_object_id:
                self.state.simulation.reset(iter_count=True, img=True)
                self.state.autoplay = True
            elif "#simulation_stop" in e.ui_object_id:
                self.state.simulation.reset(iter_count=True, img=True)
                self.state.autoplay = False
            elif "#simulation_step" in e.ui_object_id:
                if not self.state.autoplay or self.state.simulation.is_finished_iterating():
                    self.state.simulation.step()

    def run(self):
        pygame.init()

        pygame.display.set_mode(self._base_size, pygame.RESIZABLE)

        self._clock = pygame.time.Clock()

        self._ui_manager = pygame_gui.UIManager(self._base_size)

        self._ui_manager.add_font_paths("emoji", "assets/fonts/NotoEmoji-Regular.ttf")
        self._ui_manager.preload_fonts([{'name': 'emoji', 'point_size': 14, 'style': 'regular'}])

        self._ui_manager.get_theme().load_theme("assets/theme.json")

        dummy = pygame.Rect(0, 0, 200, 200)
        self.simulation_controls = SimulationControlPanel(dummy, self._ui_manager, self.state)
        self.blur_controls = BlurControlPanel(dummy, self._ui_manager, self.state)
        self.deblur_controls = BlurControlPanel(dummy, self._ui_manager, self.state, deblur=True)

        running = True
        while running:
            dt = self._clock.tick(self._fps) / 1000.0

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif self._ui_manager.process_events(e):
                    continue  # ui manager ate the event
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_r:
                        print("INFO: resetting deblur simulation [press R]")
                        self.state.simulation.reset()
                    elif e.key == pygame.K_e:
                        sim_settings = self.state.get_simulation_settings()
                        sim_settings.show_relative_error = not sim_settings.show_relative_error
                        print(f"INFO: set relative error mode to {sim_settings.show_relative_error} [toggle with E]")
                        self.state.simulation.reset(iter_count=False, img=False)  # just refresh derived images
                    elif e.key == pygame.K_RETURN:
                        self.state.simulation.reset(iter_count=True, img=False)
                    elif e.key == pygame.K_LEFT:
                        self.state.get_deblur_settings().radius = max(0, self.state.get_deblur_settings().radius - 1)
                        self.state.simulation.reset(iter_count=True, img=False)
                    elif e.key == pygame.K_RIGHT:
                        self.state.get_deblur_settings().radius = min(self.state.get_deblur_settings().max_radius,
                                                                      self.state.get_deblur_settings().radius + 1)
                        self.state.simulation.reset(iter_count=True, img=False)
                    elif e.key == pygame.K_p:
                        self.state.autoplay = not self.state.autoplay
                        print(f"INFO: {'un' if self.state.autoplay else ''}paused simulation [toggle with P]")
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
                else:
                    self.handle_potential_ui_event(e)

            window_size = pygame.display.get_surface().get_size()
            self._ui_manager.get_root_container().set_dimensions(window_size)

            layout = self.get_layout()
            self._update(dt, layout)
            self._render(layout)

            pygame.display.flip()


if __name__ == "__main__":
    win = MainWindow()
    # win.state.set_original_image(pygame.image.load("data/3x3_circle_in_10x10_orig.png"))
    # win.state.set_target_image(pygame.image.load("data/3x3_circle_in_10x10.png"))
    # win.state.set_original_image(pygame.image.load("data/splash.png"), "data/splash.png")
    win.state.set_original_image(pygame.image.load("data/parrot.jpg"), "data/parrot.jpg")
    # win.state.set_target_image(pygame.image.load("data/splash_blurred_15.png"))

    win.state.simulation.deblur_settings.blur_type = "gaussian"
    win.state.simulation.deblur_settings.radius = 15

    win.run()

