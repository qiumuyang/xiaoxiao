from pathlib import Path
from typing import Any, Callable, Iterable

import jieba


class Keyword:

    STOPWORDS = set(line for line in Path(
        "data/static/language/stopwords.txt").read_text().split("\n") if line)
    STOPWORDS |= {chr(65039), " ", "　", "\n", "\t"}

    @staticmethod
    def dice(s1: Iterable[Any], s2: Iterable[Any]) -> float:
        s1, s2 = set(s1), set(s2)
        if not s1 and not s2:
            return 1
        if not s1 or not s2:
            return 0
        return 2 * len(s1 & s2) / (len(s1) + len(s2))

    @staticmethod
    def overlap(s1: Iterable[Any], s2: Iterable[Any]) -> float:
        s1, s2 = set(s1), set(s2)
        if not s1 or not s2:
            return 0
        return len(set(s1) & set(s2)) / min(len(s1), len(s2))

    @classmethod
    def extract(cls, text: str) -> list[str]:
        return [
            w for w in jieba.cut(text, use_paddle=True)
            if w not in cls.STOPWORDS
        ]

    @classmethod
    def search(
        cls,
        query: list[str],
        corpus: list[str],
        corpus_keywords: list[Iterable[str]] | None = None,
        top_k: int = 5,
        threshold: float = 0.5,
        metric: Callable[[Iterable[str], Iterable[str]], float] = overlap,
    ) -> list[str]:
        if corpus_keywords is None:
            kw_corpus = [cls.extract(text.lower()) for text in corpus]
        else:
            assert len(corpus) == len(corpus_keywords)
            kw_corpus = corpus_keywords
        kw_query = cls.extract(" ".join(query).lower())
        sim = [(cp, metric(kw_query, ref))
               for cp, ref in zip(corpus, kw_corpus)]
        sim.sort(key=lambda x: x[1], reverse=True)
        return [text for text, score in sim if score > threshold][:top_k]
