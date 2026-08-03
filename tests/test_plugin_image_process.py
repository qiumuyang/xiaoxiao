from io import BytesIO
from pathlib import Path

import numpy as np
import requests
from PIL import Image

out = Path("image_proc_test_output")
out.mkdir(exist_ok=True)


def random_image(width: int, height: int):
    arr = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    im = Image.fromarray(arr)
    return arr, im


def random_image2(width: int, height: int):
    url = f"https://picsum.photos/{width}/{height}"
    resp = requests.get(url)
    im = Image.open(BytesIO(resp.content))
    arr = np.array(im)
    return arr, im


def test_reflect():
    from src.plugins.image.process import Reflect

    shapes = ((25, 25), (20, 25), (20, 20), (25, 20), (127, 127), (128, 128))
    l2r = Reflect("L2R")
    for shape in shapes:
        w = shape[0]
        arr, im = random_image(*shape)
        res = np.array(l2r.process(im))
        left = res[:, : w // 2]
        right = res[:, w - w // 2 :]
        assert np.array_equal(left, np.fliplr(right))
        img_non_cover = arr[:, : w - w // 2]
        res_non_cover = res[:, : w - w // 2]
        assert np.array_equal(img_non_cover, res_non_cover)

    r2l = Reflect("R2L")
    for shape in shapes:
        w = shape[0]
        arr, im = random_image(*shape)
        res = np.array(r2l.process(im))
        right = res[:, w - w // 2 :]
        left = res[:, : w // 2]
        assert np.array_equal(right, np.fliplr(left))
        img_non_cover = arr[:, w - w // 2 :]
        res_non_cover = res[:, w - w // 2 :]
        assert np.array_equal(img_non_cover, res_non_cover)

    t2b = Reflect("T2B")
    for shape in shapes:
        h = shape[1]
        arr, im = random_image(*shape)
        res = np.array(t2b.process(im))
        top = res[: h // 2, :]
        bottom = res[h - h // 2 :, :]
        assert np.array_equal(top, np.flipud(bottom))
        img_non_cover = arr[: h - h // 2, :]
        res_non_cover = res[: h - h // 2, :]
        assert np.array_equal(img_non_cover, res_non_cover)


def test_gif_frame_without_duration(monkeypatch):
    """GIF 帧缺失 duration key 时不应抛 KeyError，落到默认 100ms。"""
    from src.plugins.image.process import Reflect

    frames = [random_image(30, 30)[1], random_image(30, 30)[1]]
    for f in frames:
        f.info.pop("duration", None)
    io = BytesIO()
    frames[0].save(
        io,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        loop=0,
    )
    io.seek(0)
    im = Image.open(io)
    result = Reflect("L2R").process(im)
    assert result is not None
    reopened = Image.open(result)
    assert reopened.is_animated
    assert reopened.n_frames == 2
    # 缺省 duration 兜底到 100ms：写回的 GIF 每帧都应带 duration
    for i in range(reopened.n_frames):
        reopened.seek(i)
        assert reopened.info.get("duration") == 100


def test_gif_frame_with_zero_duration():
    """duration 为 0 时同样落到默认 100ms，不抛异常。"""
    from src.plugins.image.process import Reflect

    frames = [random_image(30, 30)[1], random_image(30, 30)[1]]
    for f in frames:
        f.info["duration"] = 0
    io = BytesIO()
    frames[0].save(
        io,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        loop=0,
    )
    io.seek(0)
    im = Image.open(io)
    result = Reflect("L2R").process(im)
    assert result is not None
    reopened = Image.open(result)
    assert reopened.is_animated
    assert reopened.n_frames == 2
    for i in range(reopened.n_frames):
        reopened.seek(i)
        assert reopened.info.get("duration") == 100


def test_imops():
    from src.plugins.image.process.imops import TileScript

    ops = TileScript()
    tests = [
        ((400, 200), "A -> A|A'"),
        ((128, 128), "A -> A@90"),
        ((201, 402), "A|_1px|B -> A|A'"),
        ((300, 200), "A1|B2|C1;D10px|E1|F2 -> F|E|D;C|B|A'"),
        ((128, 128), "A|B<3>;C|D -> A|B;A^|B^"),
    ]

    ops_out = out / "imops"
    ops_out.mkdir(exist_ok=True)

    tbl = str.maketrans(
        {
            "|": "_",
            ";": "_",
            " ": "",
            ">": "",
            "<": "",
            "-": "",
            "^": "v",
            "'": "h",
            "@": "",
        }
    )

    for i, (shape, script) in enumerate(tests):
        _arr, im = random_image2(*shape)
        im.save(ops_out / f"test_{i + 1}_{shape[0]}x{shape[1]}_input.png")
        try:
            res = ops.process(im, script)
        except Exception as e:
            print(f"Error processing {shape} with script {script}: {e}")
            raise
        assert isinstance(res, Image.Image)
        res.save(
            ops_out / f"test_{i + 1}_{shape[0]}x{shape[1]}_{script.translate(tbl)}.png"
        )
