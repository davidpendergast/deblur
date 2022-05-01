import cv2
import numpy
import pygame
import blurs
import typing


class Simulation:

    def __init__(self, target_file: str, blur_func, blur_radius, iterations=100, intensity_range=(4, 2), start_with='target', original_file: str = None):
        """
        target_file: the blurred image file to reconstruct.
        blur_func: a function from Surface, radius -> Surface that performs a blur.
        blur_radius: radius of the blur.
        iterations: number of iterations to perform.
        intensity_range: how "intense" the corrections should be at the start and end of the simulation.
        start_with: what image to start with. Choices are:
            'target' = start with the target_file image.
            'noise' = start with random noise.
            color name = start with a solid color (e.g. "white", or "red").
            color tuple = start with a solid color (e.g. (255, 255, 255) or (255, 0, 0)).
            'average' = start with a solid color that's the average color of the target image.
        original_file: the original, un-blurred image we're trying to reconstruct. This isn't used for anything other
                       than displaying it.
        """
        self.target_filename = target_file
        self.target = pygame.image.load(target_file)
        self.target_channels = [
            pygame.surfarray.array_red(self.target),
            pygame.surfarray.array_green(self.target),
            pygame.surfarray.array_blue(self.target),
        ]
        self.original = None if original_file is None else pygame.image.load(original_file)
        self.blur_func = blur_func
        self.blur_radius = blur_radius

        self.iterations = iterations
        self.intensity_range = intensity_range
        self.start_with = start_with

        self.img = self.target.copy()
        self.blurred_img = None

        self.distance = None
        self.blurred_distance = None
        self.anti_distance = None
        self.blurred_anti_distance = None

        self.error = None
        self.step_count = None

        self.restart()

    def get_output(self):
        return self.img

    def get_error(self):
        return self.error

    def restart(self):
        self.img = self.target.copy()
        if self.start_with == 'target':
            pass  # start with blurred image
        elif self.start_with == 'noise':
            self._randomize(self.img)
        elif self.start_with == 'average':
            self.img.fill(pygame.transform.average_color(self.img, self.img.get_rect()))
        elif isinstance(self.start_with, (tuple, str)):
            self.img.fill(self.start_with)  # start with solid
        else:
            raise ValueError(f"Unrecognized 'start_with' value: {self.start_with}")

        self.blurred_img = None
        self.distance = None
        self.blurred_distance = None
        self.anti_distance = None
        self.blurred_anti_distance = None
        self.error = -1
        self.step_count = 0
        self._calc_derived_images()

    def step(self):
        blur_dist_array = pygame.surfarray.pixels3d(self.blurred_distance)
        blur_anti_dist_array = pygame.surfarray.pixels3d(self.blurred_anti_distance)
        rand_scaling = max(self.intensity_range[0] * (1 - self.step_count / self.iterations), self.intensity_range[1])

        new_img_int8 = pygame.surfarray.array3d(self.img)
        new_img = new_img_int8.astype(numpy.float64)
        rand = numpy.random.rand(*new_img.shape)

        new_img[:] = new_img + blur_dist_array * (rand * rand_scaling)
        new_img[:] = new_img - blur_anti_dist_array * (rand * rand_scaling)
        new_img[:] = numpy.minimum(new_img, 255.999)
        new_img[:] = numpy.maximum(new_img, 0)

        new_img_int8[:] = new_img.astype(numpy.int8, casting='unsafe')
        pygame.surfarray.blit_array(self.img, new_img_int8)

        self._calc_derived_images()
        self.step_count += 1

    def _calc_derived_images(self):
        self.blurred_img = self.blur_func(self.img, self.blur_radius)
        self.distance, self.anti_distance = self._calc_distance_from_target(self.blurred_img)
        self.blurred_distance = self.blur_func(self.distance, self.blur_radius)
        self.blurred_anti_distance = self.blur_func(self.anti_distance, self.blur_radius)

        self.error = (numpy.mean(pygame.surfarray.pixels3d(self.distance)) +
                      numpy.mean(pygame.surfarray.pixels3d(self.anti_distance))) / 3

    def _calc_distance_from_target(self, img):
        res = img.copy()
        for i, channel in enumerate(self._get_color_channel_refs(res)):
            too_low = self.target_channels[i] > channel
            channel[too_low] = (self.target_channels[i] - channel)[too_low]
            channel[~too_low] = 0

        res_anti = img.copy()
        for i, channel in enumerate(self._get_color_channel_refs(res_anti)):
            too_high = channel > self.target_channels[i]
            channel[too_high] = (channel - self.target_channels[i])[too_high]
            channel[~too_high] = 0

        return res, res_anti

    def _get_color_channel_refs(self, img):
        return [
            pygame.surfarray.pixels_red(img),
            pygame.surfarray.pixels_green(img),
            pygame.surfarray.pixels_blue(img)
        ]

    def _randomize(self, img):
        px = pygame.surfarray.pixels3d(img)
        rand_array = numpy.random.randint(0x000000, 0xFFFFFF, px.size, dtype=numpy.uint32).reshape(px.shape)
        pygame.surfarray.blit_array(img, rand_array)


if __name__ == "__main__":
    pygame.init()

    simulation = Simulation("data/splash_blurred_15.png", blurs.get_blur_func("box"), 15, original_file="data/splash.png", intensity_range=(4, 3), iterations=100)
    # simulation = Simulation("data/3x3_circle_in_10x10.png", get_box_filter_func(), 3, original_file="data/3x3_circle_in_10x10_orig.png")

    W, H = simulation.target.get_size()

    screen = pygame.display.set_mode((W * 4, H * 2), pygame.SCALED | pygame.RESIZABLE)
    clock = pygame.time.Clock()

    auto_play = True

    running = True
    while running:
        space_pressed = False
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_SPACE:
                    space_pressed = True
                    auto_play = False
                elif e.key == pygame.K_r:
                    print("INFO: restarting simulation")
                    simulation.restart()
                elif e.key == pygame.K_p:
                    auto_play = not auto_play

        if (auto_play and simulation.step_count < simulation.iterations) or space_pressed:
            simulation.step()
            print(f"INFO: Average error per pixel at iteration {simulation.step_count} is {simulation.get_error()}")

        screen = pygame.display.get_surface()

        to_blit = [
            [simulation.img, simulation.original, simulation.distance, simulation.anti_distance],
            [simulation.blurred_img, simulation.target, simulation.blurred_distance, simulation.blurred_anti_distance]
        ]
        screen.fill((0, 0, 0))
        for y in range(len(to_blit)):
            for x in range(len(to_blit[0])):
                if to_blit[y][x] is not None:
                    screen.blit(to_blit[y][x], (x * W, y * H))

        pygame.display.set_caption(f"Deblur [{simulation.target_filename}] (Iter={simulation.step_count}, Error={simulation.error:.3f})")

        pygame.display.flip()
        clock.tick(20)