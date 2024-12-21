from collections import defaultdict
from datetime import date, timedelta

from pydantic import BaseModel

from src.utils.message.receive import MessageData


class GroupStatistics(BaseModel):
    num_messages: int
    message_each_month: list[int]
    message_each_day: list[int]
    # active: at least 1 message
    active_days: int
    active_users: int
    # user ranking
    user_messages: dict[int, int]  # user_id: num_messages
    user_talkative_days: dict[int, int]  # user_id: num_talkative_days
    # special day
    most_user: tuple[date, int] | None  # date, num_users
    most_message: tuple[date, int] | None  # date, num_messages
    popular_sentences: list[tuple[str, int, int]]  # sentence, times, num_users


class UserStatistics(BaseModel):
    num_messages: int
    message_each_month: list[int]
    message_each_day: list[int]
    active_days: int
    message_rank: int
    # talkative: most messages in a day
    talkative_days: int
    talkative_rank: int
    most_message: tuple[date, int] | None  # date, num_messages
    popular_sentence: tuple[str, int] | None  # sentence, times


def collect_statistics(
    messages: list[MessageData],
    year: int,
) -> tuple[GroupStatistics, dict[int, UserStatistics]]:
    text_max_length = 20
    text_min_times = 10
    text_min_times_group = 50
    max_num_popular_sentences = 30
    # first aggregate by date and user
    date_to_stat: dict[date, dict[int, int]] = {}
    active_users = set()
    user_language: dict[int, dict[str, int]] = {}
    group_pseudo = -1
    for message in messages:
        day = message.time.date()
        date_to_stat.setdefault(day, {})
        date_to_stat[day].setdefault(message.user_id, 0)
        date_to_stat[day][message.user_id] += 1
        active_users.add(message.user_id)
        if text := message.content.extract_plain_text().strip():
            if "暂不支持该消息类型" in text:
                continue
            if len(text) <= text_max_length:
                for uid in (message.user_id, group_pseudo):
                    user_language.setdefault(uid, {})
                    user_language[uid].setdefault(text, 0)
                    user_language[uid][text] += 1
    # then collect basic user statistics
    users: dict[int, UserStatistics] = {}
    for user_id in active_users:
        months = [0] * 12
        days = [0] * (date(year + 1, 1, 1) - date(year, 1, 1)).days
        for day, user_to_num in date_to_stat.items():
            if user_id in user_to_num:
                months[day.month - 1] += user_to_num[user_id]
                days[(day - date(year, 1, 1)).days] += user_to_num[user_id]
        num_messages = sum(months)
        if num_messages:
            most_message_day = max(days)
            most_message = (date(year, 1, 1) +
                            timedelta(days.index(most_message_day)),
                            most_message_day)
        else:
            most_message = None
        sentence, times = max(user_language.get(user_id, {}).items(),
                              key=lambda x: x[1],
                              default=("", 0))
        users[user_id] = UserStatistics(
            num_messages=num_messages,
            message_each_month=months,
            message_each_day=days,
            active_days=sum(1 for day in days if day > 0),
            most_message=most_message,
            # the following fields are filled later (group-level)
            message_rank=0,
            talkative_days=0,
            talkative_rank=0,
            popular_sentence=None if times < text_min_times else
            (sentence, times),
        )
    # finally collect group statistics
    group_months = [0] * 12
    group_days = [0] * (date(year + 1, 1, 1) - date(year, 1, 1)).days
    group_num_users = [0] * (date(year + 1, 1, 1) - date(year, 1, 1)).days
    talkative_user_days = defaultdict(int)
    for day, user_to_num in date_to_stat.items():
        group_months[day.month - 1] += sum(user_to_num.values())
        group_days[(day - date(year, 1, 1)).days] += sum(user_to_num.values())
        group_num_users[(day - date(year, 1, 1)).days] += len(user_to_num)
        user_id, _ = max(user_to_num.items(), key=lambda x: x[1])
        talkative_user_days[user_id] += 1
    num_messages = sum(group_months)
    if num_messages:
        most_message_day = max(group_days)
        most_message = (date(year, 1, 1) +
                        timedelta(group_days.index(most_message_day)),
                        most_message_day)
        most_user_day = max(group_num_users)
        most_user = (date(year, 1, 1) +
                     timedelta(group_num_users.index(most_user_day)),
                     most_user_day)
    else:
        most_message = None
        most_user = None
    # group-level user ranking
    user_messages = {user_id: s.num_messages for user_id, s in users.items()}
    for rank, (user_id, _) in enumerate(
            sorted(user_messages.items(), key=lambda x: -x[1])):
        users[user_id].message_rank = rank + 1
    for rank, (user_id, days) in enumerate(
            sorted(talkative_user_days.items(), key=lambda x: -x[1])):
        users[user_id].talkative_rank = rank + 1
        users[user_id].talkative_days = days
    # group popular sentences
    popular_sentences = sorted(
        ((sentence, times,
          sum(1 for user_id in active_users
              if sentence in user_language.get(user_id, {})))
         for sentence, times in user_language.get(group_pseudo, {}).items()
         if times >= text_min_times_group),
        key=lambda x: -x[1],
    )[:max_num_popular_sentences]
    group_stat = GroupStatistics(num_messages=num_messages,
                                 message_each_month=group_months,
                                 message_each_day=group_days,
                                 active_days=sum(1 for day in group_days
                                                 if day > 0),
                                 active_users=len(active_users),
                                 user_messages=user_messages,
                                 user_talkative_days=talkative_user_days,
                                 most_user=most_user,
                                 most_message=most_message,
                                 popular_sentences=popular_sentences)
    return group_stat, users
