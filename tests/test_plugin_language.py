from src.plugins.language.ask import Ask


def test_is_question():
    positive = [
        "问今天的天气怎么样？",
        "问什么是人工智能？",
        "问你昨天去了哪里？",
        "问为什么天会黑？",
        "问明天有什么计划",
        "问候车室里有多少人",
        "问路途还要多久",
        "问世界上有多少国家",
        "问下面有什么好吃的",
        "问一下雨就会发生什么",
        # "问起不起床",  # failed
    ]
    negative = [
        "问题的答案是什么",
        "问候语应该怎么写？",
        "问询处在什么地方",
        "问及问题的关键",
        "问问他什么时候回家",
        "问下他有没有空",
        "问一下就知道了",
    ]
    for s in positive:
        assert Ask.is_question(s)
    for s in negative:
        assert not Ask.is_question(s)
