from datetime import datetime

from src.ext import MessageSegment

from ..data import Diff, Idiom
from .data import (MAX_GUESS, UPDATE_INTERVAL, CurrentGuess, GroupData,
                   GuessIdiomData)
from .render import GuessRender, RenderAttemptData, Status


class InvalidInput(Exception):

    def __str__(self):
        raise NotImplementedError


class SyllableParseFailure(InvalidInput):

    def __str__(self):
        return "存在不正确的音节"


class SyllableNumMismatch(InvalidInput):

    def __init__(self, expect: int):
        self.expect = expect

    def __str__(self):
        return f"答案应为 {self.expect} 个音节！"


class SyllableLengthMismatch(InvalidInput):

    def __init__(self, expect: list[int]):
        self.expect = expect

    def __str__(self):
        return f"每个音节的长度应为 {'/'.join(map(str, self.expect))}！"


class GuessIdiom:

    def __init__(self, group_id: int):
        self.group_id = group_id

    @classmethod
    def _new_guess(cls, global_data: GroupData) -> GroupData:
        exclude = {h.word for h in global_data.history}
        new_word = Idiom.random4(excludes=exclude)["word"]
        return global_data.new_guess(datetime.now(), new_word)

    @classmethod
    def _check_answer(
        cls,
        input_: str,
        guess: CurrentGuess,
    ) -> list[str]:
        syllables = Idiom.parse_syllables(input_)
        if not syllables:
            raise SyllableParseFailure
        target = Idiom.get_pinyin(guess.word)
        syllable_count_filtered = [
            s for s in syllables if len(s) == len(target)
        ]
        if not syllable_count_filtered:
            raise SyllableNumMismatch(len(target))
        syllable_length_filtered = [
            s for s in syllable_count_filtered if all(
                len(m) == len(n) for m, n in zip(s, target))
        ]
        if not syllable_length_filtered:
            raise SyllableLengthMismatch([len(t) for t in target])
        return list(syllable_length_filtered[0])

    async def start(self) -> MessageSegment | None:
        group = await GuessIdiomData.get(self.group_id)
        if group.current is not None:
            # already started, render current status
            return await GuessIdiom.render(group.current, stop=False)
        # update global if necessary
        glob = await GuessIdiomData.get_global()
        interval = None
        if glob.current is None or (interval := datetime.now() -
                                    glob.current.time) > UPDATE_INTERVAL:
            glob = self._new_guess(glob)
            await GuessIdiomData.set_global(glob)
        assert glob.current is not None
        # update from the global data
        if not group.last_guess or group.last_guess.word != glob.current.word:
            group = group.new_guess(glob.current.time, glob.current.word)
            await GuessIdiomData.set(self.group_id, group)
            assert group.current is not None
            return await GuessIdiom.render(group.current, stop=False)
        elif interval:
            # have to wait for the next update
            secs = int((UPDATE_INTERVAL - interval).total_seconds())
            return MessageSegment.text(f"距离下一个成语更新还有 {secs} 秒")

    async def guess(
        self,
        user_id: int,
        input_: str,
        explicit: bool = False,
    ) -> MessageSegment | None:
        group = await GuessIdiomData.get(self.group_id)
        if group.current is None:
            return None if not explicit else MessageSegment.text(
                "没有正在进行的猜成语游戏")
        try:
            provided = self._check_answer(input_, group.current)
        except SyllableParseFailure as e:
            return None if not explicit else MessageSegment.text(str(e))
        except InvalidInput as e:
            return MessageSegment.text(str(e))
        target = Idiom.get_pinyin(group.current.word)
        diff = Idiom.diff("".join(target), "".join(provided))
        group.attempt_guess(user_id, provided)

        echo: MessageSegment | None = None
        if all(d == Diff.EXACT for d in diff):
            guess = group.succeed()
            echo = await GuessIdiom.render(guess, stop=True)
        elif len(group.current.attempts) >= MAX_GUESS:
            guess = group.fail()
            echo = await GuessIdiom.render(guess, stop=True)
        else:
            echo = await GuessIdiom.render(group.current, stop=False)
        # Note: what if another coroutine gets the same group data
        # before the current one finishes updating?
        # Prevent this by setting minimum interval between updates
        await GuessIdiomData.set(self.group_id, group)
        return echo

    @classmethod
    async def render(
        cls,
        current: CurrentGuess,
        stop: bool,
    ) -> MessageSegment:
        target_syl = Idiom.get_pinyin(current.word)
        target_syl_len = [len(s) for s in target_syl]

        attempts: list[RenderAttemptData] = []
        keyboards = {}
        priority = [Status.EXACT, Status.EXIST, Status.MISS]
        for attempt in current.attempts:
            attempt_s = "".join(attempt.syllables)
            target_s = "".join(target_syl)
            diff = Idiom.diff(target_s, attempt_s)
            if not stop:
                for syl, d in zip(attempt_s, diff):
                    status = Status.from_diff(d)
                    p_now = priority.index(keyboards.get(syl, status))
                    p_new = priority.index(status)
                    p = min(p_now, p_new)
                    keyboards[syl] = priority[p]
            attempts.append({
                "user_id": attempt.user_id,
                "syllables": attempt.syllables,
                "diffs": diff,
            })
        obj = await GuessRender.render(
            attempts=attempts,
            syllables=target_syl_len,
            key_state=None if stop else keyboards,
            answer=Idiom.idiom_table[current.word] if stop else None,
        )
        return MessageSegment.image(obj.render().to_pil())
