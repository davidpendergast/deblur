import cv2
import numpy
import pygame
import blurs
import typing
import math


class AbstractIterativeDeblurrer:

    def __init__(self):
        pass

    def get_target_image(self) -> pygame.Surface:
        raise NotImplementedError()

    def set_target_image(self, surf: pygame.Surface):
        raise NotImplementedError()

    def get_output_image(self) -> pygame.Surface:
        raise NotImplementedError()

    def get_blurred_output_image(self) -> pygame.Surface:
        raise NotImplementedError()

    def get_initial_guess(self) -> pygame.Surface:
        target = self.get_target_image()
        return None if target is None else target.copy()

    def do_blur(self, surf: pygame.Surface, strength=1.0) -> pygame.Surface:
        raise NotImplementedError()

    def get_error_image(self) -> typing.Optional[pygame.Surface]:
        return None

    def get_error(self) -> float:
        raise NotImplementedError()

    def get_iteration_limit(self) -> int:
        raise NotImplementedError()

    def get_iteration(self) -> int:
        raise NotImplementedError()

    def is_finished_iterating(self):
        return self.get_iteration() >= self.get_iteration_limit() > 0

    def step(self):
        raise NotImplementedError()

    def reset(self):
        raise NotImplementedError()


class AbstractIterativeGhastDeblurrer(AbstractIterativeDeblurrer):

    def __init__(self):
        super().__init__()
        self.target = None

        self.img: typing.Optional[pygame.Surface] = None
        self.iter_count = 0

        self.current_error = -1.0
        self.blurred_img = None
        self.target_minus_blurred_img = None
        self.target_minus_blurred_img_blurred = None
        self.blurred_img_minus_target = None
        self.blurred_img_minus_target_blurred = None
        self.combined_error_image = None

        self.reset()

    def set_target_image(self, surf: pygame.Surface):
        self.target = surf
        self.reset()

    def get_target_image(self) -> pygame.Surface:
        return self.target

    def get_output_image(self) -> pygame.Surface:
        return self.img

    def get_blurred_output_image(self):
        return self.blurred_img

    def get_error_image(self):
        return self.combined_error_image

    def get_error(self) -> float:
        return self.current_error

    def get_correction_intensity(self, iteration):
        raise NotImplementedError()

    def get_backpropagation_blur_strength(self) -> float:
        return 1.0

    def show_relative_error(self):
        raise NotImplementedError()

    def get_iteration(self) -> int:
        return self.iter_count

    def step(self):
        if self.img is None:
            return

        if None in (self.target_minus_blurred_img_blurred, self.blurred_img_minus_target_blurred):
            self._calc_derived_images()

        blur_dist_array = pygame.surfarray.pixels3d(self.target_minus_blurred_img_blurred)
        blur_anti_dist_array = pygame.surfarray.pixels3d(self.blurred_img_minus_target_blurred)
        correction_intensity = self.get_correction_intensity(self.iter_count)

        new_img_int8 = pygame.surfarray.array3d(self.img)
        new_img = new_img_int8.astype(numpy.float64)
        rand = numpy.random.rand(*new_img.shape)

        new_img[:] = new_img + blur_dist_array * (rand * correction_intensity)
        new_img[:] = new_img - blur_anti_dist_array * (rand * correction_intensity)
        new_img[:] = numpy.minimum(new_img, 255)
        new_img[:] = numpy.maximum(new_img, 0)

        new_img_int8[:] = new_img.astype(numpy.int8, casting='unsafe')
        pygame.surfarray.blit_array(self.img, new_img_int8)

        self._calc_derived_images()
        self.iter_count += 1

    def reset(self, iter_count=True, img=True):
        if iter_count:
            self.iter_count = 0

        self.img = self.get_initial_guess() if (self.img is None or img) else self.img
        self.blurred_img = None if self.img is None else self.do_blur(self.img)

        self.target_minus_blurred_img: pygame.Surface = None
        self.target_minus_blurred_img_blurred: pygame.Surface = None
        self.blurred_img_minus_target: pygame.Surface = None
        self.blurred_img_minus_target_blurred: pygame.Surface = None
        self.combined_error_image: pygame.Surface = None
        self.current_error = -1.0

        self._calc_derived_images()

    def _calc_derived_images(self):
        self.blurred_img = None if self.img is None else self.do_blur(self.img)

        if self.img is None or self.get_target_image() is None:
            self.blurred_img_minus_target = None
            self.target_minus_blurred_img = None
            self.target_minus_blurred_img_blurred = None
            self.blurred_img_minus_target_blurred = None
            self.combined_error_image = None
            self.current_error = -1
            return

        self.target_minus_blurred_img, self.blurred_img_minus_target = self._calc_distance_in_both_directions(
            self.blurred_img, self.get_target_image())

        bp_blur_strength = self.get_backpropagation_blur_strength()
        self.target_minus_blurred_img_blurred = self.do_blur(self.target_minus_blurred_img, strength=bp_blur_strength)
        self.blurred_img_minus_target_blurred = self.do_blur(self.blurred_img_minus_target, strength=bp_blur_strength)

        # img_array = pygame.surfarray.pixels3d(self.img)
        # blurred_img_array = pygame.surfarray.pixels3d(self.blurred_img)
        # tgt_array = pygame.surfarray.pixels3d(self.get_target_image())
        tgt_minus_blurred_img_array = pygame.surfarray.pixels3d(self.target_minus_blurred_img)
        blurred_img_minus_tgt_array = pygame.surfarray.pixels3d(self.blurred_img_minus_target)
        # tgt_minus_blurred_img_blurred_array = pygame.surfarray.pixels3d(self.target_minus_blurred_img_blurred)
        # blurred_img_minus_tgt_blurred_array = pygame.surfarray.pixels3d(self.blurred_img_minus_target_blurred)

        combo = numpy.maximum(tgt_minus_blurred_img_array, blurred_img_minus_tgt_array)
        self.current_error = numpy.mean(combo)

        max_error = numpy.max(combo)
        if self.show_relative_error() and self.current_error > 0:
            combo[:] = combo * (255 / max_error)

        self.combined_error_image = self.img.copy()
        pygame.surfarray.blit_array(self.combined_error_image, combo)

    def _calc_distance_in_both_directions(self, img, target) -> typing.Tuple[pygame.Surface, pygame.Surface]:
        if img is None or target is None:
            return None, None
        else:
            target_channels = self._color_channel_refs(target)
            res = img.copy()
            for i, channel in enumerate(self._color_channel_refs(res)):
                too_low = target_channels[i] > channel
                channel[too_low] = (target_channels[i] - channel)[too_low]
                channel[~too_low] = 0

            res_anti = img.copy()
            for i, channel in enumerate(self._color_channel_refs(res_anti)):
                too_high = channel > target_channels[i]
                channel[too_high] = (channel - target_channels[i])[too_high]
                channel[~too_high] = 0

            return res, res_anti

    def _color_channel_refs(self, img):
        return [
            pygame.surfarray.pixels_red(img),
            pygame.surfarray.pixels_green(img),
            pygame.surfarray.pixels_blue(img)
        ]