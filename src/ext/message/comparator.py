from io import BytesIO
from typing import Awaitable, Callable

import imagehash
from nonebot.adapters.onebot.v11 import Message
from PIL import Image

from src.utils.log import logger_wrapper
from src.utils.persistence.filestore import FileStorage

from .segment import MessageSegment

logger = logger_wrapper(__name__)


class MessageComparator:

    async def __call__(self, message1: Message, message2: Message) -> bool:
        """Compare two messages for equality."""
        if len(message1) != len(message2):
            return False

        for seg1, seg2 in zip(message1, message2):
            if seg1.type != seg2.type:
                return False

            if not self._has_custom_comparator(seg1.type):
                if seg1.data != seg2.data:
                    return False
            else:
                comparator = self._get_comparator(seg1.type)

                if not await comparator(MessageSegment.from_onebot(seg1),
                                        MessageSegment.from_onebot(seg2)):
                    return False

        return True

    def _has_custom_comparator(self, segment_type: str) -> bool:
        return hasattr(self, segment_type)

    def _get_comparator(
        self, segment_type: str
    ) -> Callable[[MessageSegment, MessageSegment], Awaitable[bool]]:
        return getattr(self, segment_type)


class ImagePHashComparator(MessageComparator):

    METADATA_KEY = "phash"

    def __init__(self, threshold: int = 8) -> None:
        super().__init__()
        self.threshold = threshold

    @staticmethod
    def calculate_phash(data: bytes) -> str:
        with Image.open(BytesIO(data)) as img:
            img = img.convert("RGB")
            phash = imagehash.phash(img)
            return str(phash)

    async def image(self, seg1: MessageSegment, seg2: MessageSegment) -> bool:
        """Compare two image segments by their perceptual hash."""
        filestore = await FileStorage.get_instance()

        try:
            hash_str1 = await filestore.get_or_compute_metadata(
                filename=seg1.extract_filename(),
                key=self.METADATA_KEY,
                processor=self.calculate_phash,
            )
            hash_str2 = await filestore.get_or_compute_metadata(
                filename=seg2.extract_filename(),
                key=self.METADATA_KEY,
                processor=self.calculate_phash,
            )
        except Exception as e:
            logger.error("failed to compute image phash", exception=e)
            hash_str1 = hash_str2 = ""

        if hash_str1 and hash_str2:

            hash1 = imagehash.hex_to_hash(hash_str1)
            hash2 = imagehash.hex_to_hash(hash_str2)

            return abs(hash1 - hash2) <= self.threshold

        return seg1.extract_filename() == seg2.extract_filename()
