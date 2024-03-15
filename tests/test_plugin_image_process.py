import numpy as np
from PIL import Image

from src.plugins.image.process import Reflect


def random_image(width: int, height: int):
    arr = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    im = Image.fromarray(arr)
    return arr, im


def test_reflect():
    shapes = ((25, 25), (20, 25), (20, 20), (25, 20), (127, 127), (128, 128))
    l2r = Reflect("L2R")
    for shape in shapes:
        w = shape[0]
        arr, im = random_image(*shape)
        res = np.array(l2r.process(im))
        left = res[:, :w // 2]
        right = res[:, w - w // 2:]
        assert np.array_equal(left, np.fliplr(right))
        img_non_cover = arr[:, :w - w // 2]
        res_non_cover = res[:, :w - w // 2]
        assert np.array_equal(img_non_cover, res_non_cover)

    r2l = Reflect("R2L")
    for shape in shapes:
        w = shape[0]
        arr, im = random_image(*shape)
        res = np.array(r2l.process(im))
        right = res[:, w - w // 2:]
        left = res[:, :w // 2]
        assert np.array_equal(right, np.fliplr(left))
        img_non_cover = arr[:, w - w // 2:]
        res_non_cover = res[:, w - w // 2:]
        assert np.array_equal(img_non_cover, res_non_cover)

    t2b = Reflect("T2B")
    for shape in shapes:
        h = shape[1]
        arr, im = random_image(*shape)
        res = np.array(t2b.process(im))
        top = res[:h // 2, :]
        bottom = res[h - h // 2:, :]
        assert np.array_equal(top, np.flipud(bottom))
        img_non_cover = arr[:h - h // 2, :]
        res_non_cover = res[:h - h // 2, :]
        assert np.array_equal(img_non_cover, res_non_cover)
