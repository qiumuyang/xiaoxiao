from dataclasses import dataclass, field
from datetime import datetime, timedelta

from src.utils.persistence import Collection, Mongo

MAX_GUESS = 6
GLOBAL_HISTORY = 100  # should not repeat in the last 100
UPDATE_INTERVAL = timedelta(minutes=10)
UPDATE_INTERVAL_STR = "10分钟"


@dataclass
class Guess:
    time: datetime
    word: str
    attempt: int  # failure if equals -1


@dataclass
class Attempt:
    user_id: int
    syllables: list[str]


@dataclass
class CurrentGuess:
    time: datetime
    word: str
    # each is a list of syllables
    attempts: list[Attempt]


@dataclass
class GroupData:
    group_id: int
    current: CurrentGuess | None = None
    history: list[Guess] = field(default_factory=list)

    @property
    def score(self) -> int:
        return sum(1 for guess in self.history if guess.attempt > 0)

    @property
    def last_guess(self) -> Guess | None:
        return self.history[-1] if self.history else None

    def new_guess(self, time: datetime, word: str):
        if self.current:
            self.history.append(
                Guess(
                    time=self.current.time,
                    word=self.current.word,
                    attempt=len(self.current.attempts),
                ))
            if self.group_id == GuessIdiomData.GLOBAL_ID:
                self.history = self.history[-GLOBAL_HISTORY:]
        self.current = CurrentGuess(
            time=time,
            word=word,
            attempts=[],
        )
        return self

    def attempt_guess(self, user_id: int, syllables: list[str]):
        if not self.current:
            raise ValueError("No current guess")
        self.current.attempts.append(
            Attempt(user_id=user_id, syllables=syllables))
        return self

    def succeed(self) -> CurrentGuess:
        if not self.current:
            raise ValueError("No current guess")
        self.history.append(
            Guess(
                time=self.current.time,
                word=self.current.word,
                attempt=len(self.current.attempts),
            ))
        if self.group_id == GuessIdiomData.GLOBAL_ID:
            self.history = self.history[-GLOBAL_HISTORY:]
        ret, self.current = self.current, None
        return ret

    def fail(self) -> CurrentGuess:
        if not self.current:
            raise ValueError("No current guess")
        self.history.append(
            Guess(
                time=self.current.time,
                word=self.current.word,
                attempt=-1,
            ))
        if self.group_id == GuessIdiomData.GLOBAL_ID:
            self.history = self.history[-GLOBAL_HISTORY:]
        ret, self.current = self.current, None
        return ret


class GuessIdiomData:

    data: Collection[dict, GroupData] = Mongo.collection("guess_idiom")

    GLOBAL_ID = 0

    @classmethod
    async def get(cls, group_id: int) -> GroupData:
        return (await cls.data.find_one({"group_id": group_id})
                or GroupData(group_id=group_id))

    @classmethod
    async def set(cls, group_id: int, data: GroupData):
        await cls.data.find_one_and_update(
            {"group_id": group_id},
            data,
            upsert=True,
        )

    @classmethod
    async def get_ranking(cls) -> list[GroupData]:
        groups = [item async for item in cls.data.find_all({})]
        return sorted(groups, key=lambda group: group.score, reverse=True)

    @classmethod
    async def get_global(cls) -> GroupData:
        return await cls.get(cls.GLOBAL_ID)

    @classmethod
    async def set_global(cls, data: GroupData):
        await cls.set(cls.GLOBAL_ID, data)


@GuessIdiomData.data.serialize()
def serialize(data: GroupData) -> dict:
    return {
        "group_id":
        data.group_id,
        "current": {
            "time":
            data.current.time,
            "word":
            data.current.word,
            "attempts": [{
                "syllables": attempt.syllables,
                "user_id": attempt.user_id,
            } for attempt in data.current.attempts],
        } if data.current else None,
        "history": [{
            "time": guess.time,
            "word": guess.word,
            "attempt": guess.attempt,
        } for guess in data.history],
    }


@GuessIdiomData.data.deserialize()
def deserialize(data: dict) -> GroupData:
    return GroupData(
        group_id=data["group_id"],
        current=CurrentGuess(
            time=data["current"]["time"],
            word=data["current"]["word"],
            attempts=[
                Attempt(**attempt) for attempt in data["current"]["attempts"]
            ],
        ) if data["current"] else None,
        history=[Guess(**guess) for guess in data["history"]],
    )
