"""인과 네트워크 지도(INRM) Plotly Figure."""

from collections.abc import Callable

import plotly.graph_objects as go

from .core import DematelResult

GROUP_COLORS = {"cause": "#c0392b", "effect": "#2471a3", "neutral": "#7f8c8d"}
ARROW_COLOR = "rgba(80, 80, 80, 0.55)"
ROMAN = {1: "Ⅰ", 2: "Ⅱ", 3: "Ⅲ", 4: "Ⅳ"}
# 사분면 라벨 위치: (x, y, xanchor, yanchor) — 축 영역 기준 비율
CORNERS = {
    1: (0.99, 0.99, "right", "top"),
    2: (0.01, 0.99, "left", "top"),
    3: (0.01, 0.01, "left", "bottom"),
    4: (0.99, 0.01, "right", "bottom"),
}


def build_figure(
    factors: list[str],
    res: DematelResult,
    rels: list[tuple[int, int, float]],
    theta: float,
    t: Callable[..., str],
    decimals: int = 3,
) -> go.Figure:
    P, Rel = res.prominence, res.relation
    fmt = f",.{decimals}f"
    fig = go.Figure()

    # 영향 관계 화살표: 약한 관계부터 그려 강한 화살표가 위에 오게 한다.
    strength = {(i, j): v for i, j, v in rels}
    v_max = max(strength.values(), default=theta)

    def width(v: float) -> float:
        return 1.0 + 3.0 * (v - theta) / (v_max - theta) if v_max > theta else 2.0

    hover_x, hover_y, hover_text = [], [], []
    drawn = set()
    for (i, j), v in sorted(strength.items(), key=lambda kv: kv[1]):
        if (i, j) in drawn:
            continue
        back = strength.get((j, i))
        drawn.update({(i, j), (j, i)})
        fig.add_annotation(
            x=P[j], y=Rel[j], ax=P[i], ay=Rel[i],
            xref="x", yref="y", axref="x", ayref="y",
            text="", showarrow=True,
            arrowhead=2, startarrowhead=2, arrowsize=1,
            arrowside="end+start" if back is not None else "end",
            arrowwidth=width(max(v, back or v)), arrowcolor=ARROW_COLOR,
            standoff=9, startstandoff=9,
        )
        lines = [f"{factors[i]} → {factors[j]}: {v:{fmt}}"]
        if back is not None:
            lines.append(f"{factors[j]} → {factors[i]}: {back:{fmt}}")
        hover_x.append((P[i] + P[j]) / 2)
        hover_y.append((Rel[i] + Rel[j]) / 2)
        hover_text.append("<br>".join(lines))

    # 화살표에는 hover가 없으므로 중간점에 투명 마커를 둔다.
    if hover_x:
        fig.add_trace(go.Scatter(
            x=hover_x, y=hover_y, mode="markers",
            marker=dict(size=14, color="rgba(0,0,0,0)"),
            hovertext=hover_text, hoverinfo="text", showlegend=False,
        ))

    for g in ("cause", "effect", "neutral"):
        idx = [k for k, grp in enumerate(res.group) if grp == g]
        if not idx:
            continue
        fig.add_trace(go.Scatter(
            x=P[idx], y=Rel[idx], mode="markers+text",
            text=[factors[k] for k in idx], textposition="top center",
            marker=dict(size=13, color=GROUP_COLORS[g], line=dict(width=1, color="white")),
            name=t(f"group.{g}"),
            customdata=[[res.weight[k]] for k in idx],
            hovertemplate=(
                "<b>%{text}</b><br>"
                f"R+C: %{{x:{fmt}}}<br>R−C: %{{y:{fmt}}}<br>"
                f"{t('col.weight')}: %{{customdata[0]:{fmt}}}<extra></extra>"
            ),
        ))

    # 사분면 기준선과 라벨
    fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
    fig.add_vline(x=float(P.mean()), line_dash="dot", line_color="gray", line_width=1)
    for q, (x, y, xa, ya) in CORNERS.items():
        fig.add_annotation(
            xref="x domain", yref="y domain", x=x, y=y, xanchor=xa, yanchor=ya,
            text=f"{ROMAN[q]} {t(f'quad.name{q}')}", showarrow=False,
            font=dict(size=12, color="gray"),
        )

    x_span = float(P.max() - P.min()) or 1.0
    y_lim = float(abs(Rel).max()) or 1.0
    fig.update_layout(
        xaxis=dict(title=t("map.x"), range=[P.min() - 0.15 * x_span, P.max() + 0.15 * x_span], zeroline=False),
        yaxis=dict(title=t("map.y"), range=[-1.3 * y_lim, 1.3 * y_lim], zeroline=False),
        height=620,
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=40, b=40, l=40, r=20),
    )
    return fig
