"""규칙 기반 템플릿으로 결과 해석 문장을 만든다."""

from collections.abc import Callable

import numpy as np

from .core import DematelResult


def generate(
    factors: list[str],
    res: DematelResult,
    rels: list[tuple[int, int, float]],
    theta: float,
    t: Callable[..., str],
    decimals: int = 3,
    top_n: int = 3,
    top_relations: int = 5,
) -> list[str]:
    sep = t("list_sep")

    def num(v: float) -> str:
        return f"{v:,.{decimals}f}"

    def items(indices, values) -> str:
        return sep.join(f"**{factors[i]}** ({num(values[i])})" for i in indices)

    lines = []

    by_prominence = np.argsort(-res.prominence, kind="stable")
    lines.append(t("interp.top_prominence", items=items(by_prominence[:top_n], res.prominence)))

    by_relation = np.argsort(-res.relation, kind="stable")
    cause = [i for i in by_relation if res.group[i] == "cause"]
    effect = [i for i in by_relation[::-1] if res.group[i] == "effect"]
    lines.append(t("interp.cause", items=items(cause, res.relation)) if cause else t("interp.no_cause"))
    lines.append(t("interp.effect", items=items(effect, res.relation)) if effect else t("interp.no_effect"))
    if cause and effect:
        lines.append(t(
            "interp.strongest",
            cause=factors[cause[0]], cause_value=num(res.relation[cause[0]]),
            effect=factors[effect[0]], effect_value=num(res.relation[effect[0]]),
        ))

    for q in (1, 2, 3, 4):
        members = [i for i in by_prominence if res.quadrant[i] == q]
        if members:
            lines.append(t(
                "interp.quadrant",
                quadrant=t(f"quad.roman{q}"), meaning=t(f"quad.meaning{q}"),
                items=sep.join(f"**{factors[i]}**" for i in members),
            ))

    if rels:
        top = sep.join(f"{factors[i]} → {factors[j]} ({num(v)})" for i, j, v in rels[:top_relations])
        lines.append(t("interp.relations", count=len(rels), theta=num(theta), items=top))
    else:
        lines.append(t("interp.no_relations", theta=num(theta)))

    return lines
