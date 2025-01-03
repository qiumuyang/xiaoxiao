import numpy as np
import pytest

from src.utils.image.avatar import Avatar


@pytest.mark.asyncio
async def test_avatar():
    image1 = await Avatar.user(782719906)
    image2 = await Avatar.user(782719906)
    image3 = await Avatar.user(782719906)

    # assert image1 is not None
    # assert image2 is image1
    # assert image3 is image1
    # since loaded from local cache, they are different objects
    assert (np.array(image1) == np.array(image2)).all()
    assert (np.array(image1) == np.array(image3)).all()
