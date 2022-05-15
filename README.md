# Deblur
A tool that analyzes and reverses blurs on images.

You can either download the windows executable from [itch.io](https://ghastly.itch.io/deblur), or run it from source by installing the dependencies in `requirements.txt` and launching `entry_point.py`. 

Note that this is not an automated tool and it only works if you know how the image was blurred (blur type and radius). It also only supports Gaussian, Box-Filter, and Median-Filter blurs currently.

## Methodology
This uses an iterative "guess and check" approach that converges to an optimal unblurred image, concieved by me (although I'm guessing it's been thought of before).

The basic idea is that you have:
- `x`: the original non-blurred image (not known)
- `b`: a blurring function (known)
- `x'` a blurred version of `x`, such that `x' = b(x)` (known)

And you want to find `x`. 

So you make an initial guess of `x` (which can be anything really. This implementation uses `x'` as the initial guess, but random noise would work too). Call that guess `y`. Then you compute `y' = b(y)` by blurring `y`. Next, you compare `y'` (the blurred guess) to `x'` by subtracting them. This gives you an "error image" (containing negative values, potentially) `e = x' - y'`.

So now, you know that pixels with high absolute values in `e` are places where `y` (your guess) isn't blurring properly. So that implies that the pixels in `y` near the high-error pixels in `e` aren't correct. So (and this is the clever part) we *blur `e`* (the error image), and scale its pixels by some random noise, and then add it to `y` to generate our next guess.

So we get the new guess `y_next = y' + b(e) * random_scaling`, and importantly, it's almost guaranteed that `y_next` will have less per-pixel error than `y`. we repeat until an optimal guess is found (optimal meaning the average absolute error is minimized). 

At that point, you can tweak the blurring function (changing the radius, for example) or mess with the random scaling to try to make it generate a more visually-pleasing result.

## Blurring and deblurring some pixel art
![Alt text](/assets/resync_demo.png?raw=true "assets/resync_demo.png")

From the left, the images are `x`, `x'`, and `y`.

## Deblurring a photo of people
![Alt text](/assets/people_demo.png?raw=true "people_demo.png")

From the top left, the images are (top row) `x'`, `y`, and (bottom row) `y'` and `e`.

## Deblurring a photo of a building
![Alt text](/assets/building_demo.png?raw=true "building_demo.png")

From the top left, the images are (top row) `x'`, `y`, and (bottom row) `y'` and `e`.
