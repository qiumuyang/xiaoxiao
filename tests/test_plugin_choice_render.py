import random
from pathlib import Path
from unittest.mock import PropertyMock, patch

import pytest
from nonebot.adapters.onebot.v11.message import Message

from src.ext import MessageSegment
from src.plugins.choice.render import ChoiceRender
from src.utils.render import Interpolation
from src.utils.userlist import MessageItem, ReferenceItem, UserList

out = Path("render-test/choice")
out.mkdir(parents=True, exist_ok=True)

subjects = [
    "The system", "Reality", "Consciousness", "Time", "The observer", "Truth",
    "Identity"
]
verbs = [
    "transcends", "manifests", "disrupts", "redefines", "obscures",
    "illuminates", "questions"
]
objects = [
    "the known", "structure", "duality", "the void", "perception",
    "linear thought", "meaning"
]
qualifiers = [
    "within the limits of paradox.", "as a construct of experience.",
    "in the absence of context.", "when viewed through entropy.",
    "despite inherent contradictions.", "under recursive abstraction.",
    "in the framework of illusion."
]


def generate_sentence():
    k = random.randint(1, 3)
    return "\n".join([
        " ".join([
            random.choice(tgt)
            for tgt in [subjects, verbs, objects, qualifiers]
        ]) for _ in range(k)
    ])


@pytest.mark.asyncio
async def test_render_item_card():
    complex_msg = Message([
        MessageSegment.text("Leading text"),
        MessageSegment.image_url(filename="test_512x512.png",
                                 url="https://placehold.co/512x512.png"),
        MessageSegment.text("Trailing text"),
        MessageSegment.at(111),
        MessageSegment.face(0),
        MessageSegment.text("end")
    ])
    msg = MessageItem(content=complex_msg, creator_id=111)
    ref = ReferenceItem(name="test", creator_id=111)

    msg1 = await ChoiceRender.render_item_card(group_id=999,
                                               index=100,
                                               item=MessageItem(
                                                   content=Message("普通文本"),
                                                   creator_id=222))
    msg1.render().save(out / "message-item.png")

    msg2 = await ChoiceRender.render_item_card(group_id=999,
                                               index=100,
                                               item=msg)
    msg2.render().save(out / "message-item-complex.png")

    msg3 = await ChoiceRender.render_item_card(
        group_id=999,
        index=100,
        item=MessageItem(content=Message(
            MessageSegment.image_url(filename="test_512x256.png",
                                     url="https://placehold.co/512x256.png")),
                         creator_id=333))
    msg3.render().save(out / "message-item-image.png")

    ref = await ChoiceRender.render_item_card(group_id=999, index=79, item=ref)
    ref.render().save(out / "reference-item.png")


@pytest.mark.asyncio
async def test_render_list():
    items = sum([[
        MessageItem(content=Message(generate_sentence()), creator_id=222),
        ReferenceItem(name="test", creator_id=3481996679),
        ReferenceItem(name="test-not-exist-long-long-long",
                      creator_id=3481996679),
        MessageItem(content=Message(
            MessageSegment.image_url(filename="test_512x256.png",
                                     url="https://placehold.co/512x256.png")),
                    creator_id=333),
        MessageItem(
            content=Message([
                MessageSegment.text(generate_sentence()),
                MessageSegment.image_url(
                    filename="test_512x128.png",
                    url="https://placehold.co/512x128.png"),
            ]),
            creator_id=333,
        ),
    ] for _ in range(20)], [])
    with patch.object(UserList, "valid_references",
                      new_callable=PropertyMock) as mock:

        async def valid_references():
            return ["test"]

        mock.return_value = valid_references()

        lst = UserList(
            name="Test List",
            group_id=999,
            creator_id=3481996679,
            items=items,
        )
        result = await ChoiceRender.render_list(group_id=999, userlist=lst)
        result.render().thumbnail(max_height=2500,
                                  interpolation=Interpolation.LANCZOS).save(
                                      out / "list.png")

        for page_id in [0, 1, 100]:
            mock.return_value = valid_references()
            result = await ChoiceRender.render_list(
                group_id=999,
                userlist=lst,
                pagination=lst.paginate(page_id, page_size=13),
            )
            result.render().thumbnail(
                max_height=2500, interpolation=Interpolation.LANCZOS).save(
                    out / f"list-page{page_id}.png")

        for k in range(6):
            mock.return_value = valid_references()
            lst = UserList(
                name=f"Test List ({k})",
                group_id=999,
                creator_id=3481996679,
                items=items[:k],
            )
            result = await ChoiceRender.render_list(group_id=999, userlist=lst)
            result.render().save(out / f"list-{k}-items.png")

        mock.return_value = valid_references()
        lst = UserList(
            name="一二三四五六七八九十一二三四五六七八九十",
            group_id=999,
            creator_id=3481996679,
            items=[],
        )
        result = await ChoiceRender.render_list(group_id=999, userlist=lst)
        result.render().save(out / "list-long-name.png")
