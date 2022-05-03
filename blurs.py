import pygame
import cv2


def box(img: pygame.Surface, radius, params=None) -> pygame.Surface:
    """
    Performs a "Box Filter" blur.
    """
    res = img.copy()
    px = pygame.surfarray.array3d(res)
    cv2.blur(px, ksize=(radius, radius), dst=px)
    pygame.surfarray.blit_array(res, px)
    return res


def gaussian(img: pygame.Surface, radius, params=None) -> pygame.Surface:
    """
    Performs a Gaussian blur.
    """
    # radius has to be odd or else cv2 will complain.
    r = radius if radius % 2 == 1 else radius + 1

    # the choice of sigma is a bit arbitrary here, but Mathmatica's GaussianMatrix function uses r / 2 by default
    # if it's unspecified. So I guess we'll do the same. In practice this means that a gaussian blur of "X pixels"
    # can mean different things in two different apps.
    sigma = r / 2

    res = img.copy()
    px = pygame.surfarray.array3d(res)
    cv2.GaussianBlur(px, (r, r), sigma, dst=px)
    pygame.surfarray.blit_array(res, px)
    return res


_ALL_BLURS = {
    "box": box,
    "gaussian": gaussian
}


def get_all_blurs():
    return list(_ALL_BLURS.keys())


def get_blur_func(name):
    if name in _ALL_BLURS:
        return _ALL_BLURS[name]
    else:
        raise ValueError(f"Unrecognized blur style: {name}")
