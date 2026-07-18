from unittest.mock import patch

import pytest

from src.plugins.choice.parse import Op, parse_action


class TestParseNonDuplicateAdd:
    def test_force_add_single_item(self):
        """++item 解析为 FORCE_ADD"""
        action = parse_action("+test ++item")
        assert action is not None
        assert action.op == Op.ADD
        assert action.name == "test"
        assert len(action.items) == 1
        assert action.items[0].op == Op.FORCE_ADD
        assert action.items[0].content == "item"

    def test_force_add_not_change_add(self):
        """+item 仍解析为 ADD"""
        action = parse_action("test +item")
        assert action is not None
        assert action.items[0].op == Op.ADD
        assert action.items[0].content == "item"

    def test_mixed_ops(self):
        """混合 ++ / + / - 正确解析"""
        action = parse_action("list ++a +b -c")
        assert action is not None
        assert action.op == Op.NONE
        assert len(action.items) == 3
        assert action.items[0].op == Op.FORCE_ADD
        assert action.items[0].content == "a"
        assert action.items[1].op == Op.ADD
        assert action.items[1].content == "b"
        assert action.items[2].op == Op.REMOVE
        assert action.items[2].content == "c"

    def test_force_add_reference(self):
        """++[ref] 解析为 FORCE_ADD + reference 类型"""
        action = parse_action("test ++[other_list]")
        assert action is not None
        assert action.items[0].op == Op.FORCE_ADD
        assert action.items[0].content == "other_list"
        assert action.items[0].type == "reference"

    def test_add_reference_still_add(self):
        """+[ref] 仍解析为 ADD + reference 类型"""
        action = parse_action("test +[other_list]")
        assert action is not None
        assert action.items[0].op == Op.ADD
        assert action.items[0].content == "other_list"
        assert action.items[0].type == "reference"

    def test_create_list_unchanged(self):
        """+listname 创建列表行为不变"""
        action = parse_action("+newlist")
        assert action is not None
        assert action.op == Op.ADD
        assert action.name == "newlist"
        assert len(action.items) == 0

    def test_force_add_first_token_is_list_level(self):
        """++listname 作为第一个 token → 列表级操作，不是 item 操作"""
        action = parse_action("++listname")
        assert action is not None
        assert action.op == Op.FORCE_ADD
        assert action.name == "listname"
        assert len(action.items) == 0

    def test_parsing_null_or_empty(self):
        """空输入或纯空白"""
        assert parse_action("") is None
        assert parse_action(" ") is None

    def test_default_op_is_none(self):
        """无前缀 token 作为首项 → Op.NONE"""
        action = parse_action("listname")
        assert action is not None
        assert action.op == Op.NONE
        assert action.name == "listname"


class TestHandlerNonDuplicateAdd:
    """测试 ChoiceHandler.handle_list_items 中的幂等添加逻辑。

    使用 mock 隔离 UserListService 和 ImagePHashComparator，
    验证各 op 分支的 diff 跟踪结果。
    """

    @pytest.fixture
    def mock_services(self):
        """构造 handler 需要的最小 mock 环境"""
        from unittest.mock import AsyncMock, MagicMock, patch

        from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent

        bot = MagicMock(spec=Bot)
        event = MagicMock(spec=GroupMessageEvent)
        event.group_id = 999
        matcher = MagicMock()

        # mock UserListService
        svc_patch = patch("src.plugins.choice.choice.UserListService", autospec=True)
        mock_svc_cls = svc_patch.start()

        # mock ImagePHashComparator
        comp_patch = patch(
            "src.plugins.choice.choice.ImagePHashComparator", autospec=True
        )
        mock_comp_cls = comp_patch.start()

        # mock ChoiceRender.render_diff → returns a mock with render() chain
        render_patch = patch("src.plugins.choice.choice.ChoiceRender", autospec=True)
        mock_render_cls = render_patch.start()

        mock_img = MagicMock()
        mock_render_cls.render_diff = AsyncMock(return_value=mock_img)

        yield bot, event, matcher, mock_svc_cls, mock_comp_cls, mock_render_cls

        svc_patch.stop()
        comp_patch.stop()
        render_patch.stop()

    @pytest.mark.asyncio
    async def test_add_skips_duplicate_item(self, mock_services):
        """+item 幂等：列表已有同内容条目 → 跳过"""
        from unittest.mock import AsyncMock

        from nonebot.adapters.onebot.v11 import Message

        from src.plugins.choice.choice import ChoiceHandler
        from src.plugins.choice.parse import Action, ItemAction, Op
        from src.utils.userlist import MessageItem, UserList

        bot, event, matcher, mock_svc, _mock_comp, mock_render = mock_services

        handler = ChoiceHandler(bot, event, matcher)
        comparator = AsyncMock()
        # 返回 True → 与某现有条目匹配（已存在）
        comparator.return_value = True
        handler.comparator = comparator

        lst = UserList(
            name="testlist",
            group_id=999,
            creator_id=111,
            items=[MessageItem(content=Message("饺子"), creator_id=111)],
        )
        mock_svc.find_list = AsyncMock(return_value=lst)

        action = Action(
            op=Op.NONE,
            name="testlist",
            items=[ItemAction(op=Op.ADD, content="饺子", type="message")],
        )

        with patch.object(matcher, "finish", new_callable=AsyncMock) as _mock_finish:
            await handler.handle_list_items(111, "testlist", action, {}, False)

        mock_svc.append_message.assert_not_called()
        mock_svc.append_reference.assert_not_called()
        mock_render.render_diff.assert_called_once()
        diff_items = mock_render.render_diff.call_args[1]["diff_items"]
        assert len(diff_items) == 1
        assert diff_items[0].status == "skipped"

    @pytest.mark.asyncio
    async def test_add_appends_new_item(self, mock_services):
        """+item 幂等：无匹配 → 新增"""
        from unittest.mock import AsyncMock

        from nonebot.adapters.onebot.v11 import Message

        from src.plugins.choice.choice import ChoiceHandler
        from src.plugins.choice.parse import Action, ItemAction, Op
        from src.utils.userlist import MessageItem, UserList

        bot, event, matcher, mock_svc, _mock_comp, mock_render = mock_services

        handler = ChoiceHandler(bot, event, matcher)
        comparator = AsyncMock()
        # 返回 False → 无匹配
        comparator.return_value = False
        handler.comparator = comparator

        lst = UserList(
            name="testlist",
            group_id=999,
            creator_id=111,
            items=[MessageItem(content=Message("米饭"), creator_id=111)],
        )
        mock_svc.find_list = AsyncMock(return_value=lst)
        mock_svc.append_message = AsyncMock()

        action = Action(
            op=Op.NONE,
            name="testlist",
            items=[ItemAction(op=Op.ADD, content="饺子", type="message")],
        )

        with patch.object(matcher, "finish", new_callable=AsyncMock) as _mock_finish:
            await handler.handle_list_items(111, "testlist", action, {}, False)

        mock_svc.append_message.assert_called_once()
        mock_render.render_diff.assert_called_once()
        diff_items = mock_render.render_diff.call_args[1]["diff_items"]
        assert len(diff_items) == 1
        assert diff_items[0].status == "added"

    @pytest.mark.asyncio
    async def test_force_add_always_appends(self, mock_services):
        """++item 强制添加：无论是否已存在，都追加"""
        from unittest.mock import AsyncMock

        from nonebot.adapters.onebot.v11 import Message

        from src.plugins.choice.choice import ChoiceHandler
        from src.plugins.choice.parse import Action, ItemAction, Op
        from src.utils.userlist import MessageItem, UserList

        bot, event, matcher, mock_svc, _mock_comp, mock_render = mock_services

        handler = ChoiceHandler(bot, event, matcher)
        comparator = AsyncMock(return_value=True)
        handler.comparator = comparator

        lst = UserList(
            name="testlist",
            group_id=999,
            creator_id=111,
            items=[MessageItem(content=Message("饺子"), creator_id=111)],
        )
        mock_svc.find_list = AsyncMock(return_value=lst)
        mock_svc.append_message = AsyncMock()

        action = Action(
            op=Op.NONE,
            name="testlist",
            items=[ItemAction(op=Op.FORCE_ADD, content="饺子", type="message")],
        )

        with patch.object(matcher, "finish", new_callable=AsyncMock) as _mock_finish:
            await handler.handle_list_items(111, "testlist", action, {}, False)

        # 即使已存在，force_add 也追加
        mock_svc.append_message.assert_called_once()
        diff_items = mock_render.render_diff.call_args[1]["diff_items"]
        assert diff_items[0].status == "forced"

    @pytest.mark.asyncio
    async def test_remove_captures_item_before_deletion(self, mock_services):
        """-2 删除：在调用 remove_by_index 前捕获条目内容"""
        from unittest.mock import AsyncMock

        from nonebot.adapters.onebot.v11 import Message

        from src.plugins.choice.choice import ChoiceHandler
        from src.plugins.choice.parse import Action, ItemAction, Op
        from src.utils.userlist import MessageItem, UserList

        bot, event, matcher, mock_svc, _mock_comp, mock_render = mock_services

        handler = ChoiceHandler(bot, event, matcher)
        handler.comparator = AsyncMock()

        item_to_remove = MessageItem(content=Message("饺子"), creator_id=111)
        lst = UserList(
            name="testlist",
            group_id=999,
            creator_id=111,
            items=[
                item_to_remove,
                MessageItem(content=Message("米饭"), creator_id=111),
            ],
        )
        mock_svc.find_list = AsyncMock(return_value=lst)
        mock_svc.remove_by_index = AsyncMock()

        action = Action(
            op=Op.NONE,
            name="testlist",
            items=[ItemAction(op=Op.REMOVE, content="1", type="message")],
        )

        with patch.object(matcher, "finish", new_callable=AsyncMock) as _mock_finish:
            await handler.handle_list_items(111, "testlist", action, {}, False)

        mock_svc.remove_by_index.assert_called_once()
        diff_items = mock_render.render_diff.call_args[1]["diff_items"]
        assert len(diff_items) == 1
        assert diff_items[0].status == "removed"
        assert diff_items[0].item is not None

    @pytest.mark.asyncio
    async def test_remove_fail_by_text_not_found(self, mock_services):
        """-item 文本不匹配 → remove_failed"""
        from unittest.mock import AsyncMock

        from nonebot.adapters.onebot.v11 import Message

        from src.plugins.choice.choice import ChoiceHandler
        from src.plugins.choice.parse import Action, ItemAction, Op
        from src.utils.userlist import MessageItem, UserList

        bot, event, matcher, mock_svc, _mock_comp, mock_render = mock_services

        handler = ChoiceHandler(bot, event, matcher)
        handler.comparator = AsyncMock()

        lst = UserList(
            name="testlist",
            group_id=999,
            creator_id=111,
            items=[MessageItem(content=Message("米饭"), creator_id=111)],
        )
        mock_svc.find_list = AsyncMock(return_value=lst)
        mock_svc.remove_by_index = AsyncMock()

        action = Action(
            op=Op.NONE,
            name="testlist",
            items=[ItemAction(op=Op.REMOVE, content="饺子", type="message")],
        )

        with patch.object(matcher, "finish", new_callable=AsyncMock) as _mock_finish:
            await handler.handle_list_items(111, "testlist", action, {}, False)

        # 未匹配，不应调用删除
        mock_svc.remove_by_index.assert_not_called()
        diff_items = mock_render.render_diff.call_args[1]["diff_items"]
        assert diff_items[0].status == "remove_failed"


class TestRenderDiff:
    """视觉验证 render_diff 卡片输出，保存到 render-test/choice/diff/"""

    @pytest.mark.asyncio
    async def test_render_diff_all_statuses(self):
        from pathlib import Path
        from unittest.mock import AsyncMock, patch

        from nonebot.adapters.onebot.v11 import Message
        from PIL import Image as PILImage

        from src.plugins.choice.render import ChoiceRender, DiffEntry
        from src.utils.userlist import MessageItem, ReferenceItem, UserList

        placeholder = PILImage.new("RGBA", (80, 80), color=(150, 150, 150, 255))

        out = Path("render-test/choice/diff")
        out.mkdir(parents=True, exist_ok=True)

        lst = UserList(name="午餐", group_id=999, creator_id=3481996679, items=[])

        msg_jiaozi = MessageItem(content=Message("饺子"), creator_id=111)
        msg_mifan = MessageItem(content=Message("米饭"), creator_id=111)
        ref_kuaican = ReferenceItem(name="快餐", creator_id=111)
        msg_jiandan = MessageItem(content=Message("煎蛋"), creator_id=111)
        msg_hanbao = MessageItem(content=Message("汉堡"), creator_id=111)

        diff = [
            DiffEntry("added", 4, msg_jiaozi, None),
            DiffEntry("forced", 5, msg_jiandan, None),
            DiffEntry("skipped", 2, msg_mifan, None),
            DiffEntry("removed", 0, msg_hanbao, None),
            DiffEntry("remove_failed", None, None, "面条"),
            DiffEntry("added", 6, ref_kuaican, None),
            DiffEntry("skipped", 3, ReferenceItem(name="小吃", creator_id=111), None),
        ]

        with (
            patch(
                "src.utils.persistence.FileStorage.get_instance",
                new_callable=AsyncMock,
            ),
            patch(
                "src.utils.image.avatar.Avatar.user",
                new_callable=AsyncMock,
                return_value=placeholder,
            ),
        ):
            # Scenario 1: all statuses
            obj = await ChoiceRender.render_diff(
                group_id=999, userlist=lst, diff_items=diff
            )
            obj.render().save(out / "all-statuses.png")

            # Scenario 2: only added
            obj = await ChoiceRender.render_diff(
                group_id=999,
                userlist=lst,
                diff_items=[DiffEntry("added", 0, msg_jiaozi, None)],
            )
            obj.render().save(out / "only-added.png")

            # Scenario 3: only skipped
            obj = await ChoiceRender.render_diff(
                group_id=999,
                userlist=lst,
                diff_items=[DiffEntry("skipped", 5, msg_jiaozi, None)],
            )
            obj.render().save(out / "only-skipped.png")

            # Scenario 4: only removed
            obj = await ChoiceRender.render_diff(
                group_id=999,
                userlist=lst,
                diff_items=[DiffEntry("removed", 0, msg_jiaozi, None)],
            )
            obj.render().save(out / "only-removed.png")

            # Scenario 5: only remove_failed
            obj = await ChoiceRender.render_diff(
                group_id=999,
                userlist=lst,
                diff_items=[DiffEntry("remove_failed", None, None, "不存在的东西")],
            )
            obj.render().save(out / "only-remove-failed.png")

            # Scenario 6: empty
            obj = await ChoiceRender.render_diff(
                group_id=999,
                userlist=lst,
                diff_items=[],
            )
            obj.render().save(out / "empty.png")

            # Scenario 7: long list name
            lst_long = UserList(
                name="一二三四五六七八九十一二三四五六七八九十",
                group_id=999,
                creator_id=3481996679,
                items=[],
            )
            obj = await ChoiceRender.render_diff(
                group_id=999,
                userlist=lst_long,
                diff_items=[DiffEntry("added", 0, msg_jiaozi, None)],
            )
            obj.render().save(out / "long-name.png")

        print("All diff render images saved to render-test/choice/diff/")
