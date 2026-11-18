"""Mathematical model fitting and curve sampling for chart series trendlines.

Provides analytical and least-squares regression fits for:
- Linear ($y = m \\cdot x + b$, optional explicit intercept $b = c$)
- Exponential ($y = b \\cdot e^{m \\cdot x}$, optional explicit intercept $c > 0$)
- Logarithmic ($y = m \\cdot \\ln(x) + b$, $x > 0$)
- Power ($y = b \\cdot x^m$, $x > 0, y > 0$)
- Polynomial orders 2 to 6 ($y = \\sum a_j x^j$, optional explicit intercept $a_0 = c$)
- Moving Average (periods 2 to 255)

All fits operate on normalized category coordinates $x = 1.0, 2.0, \\dots, N$
matching ISO/IEC 29500 DrawingML Chart series data caches.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

SUPPORTED_TRENDLINE_TYPES = frozenset(
    {"linear", "exp", "log", "power", "poly", "movingAvg"}
)


class TrendlineFitRefusal(ValueError):
    """Raised when a trendline cannot be fitted due to domain exclusions or degenerate data."""


@dataclass(frozen=True)
class TrendlineFitResult:
    """The result of fitting a trendline model to series values."""

    type: str
    predict: Callable[[float], float]
    points: tuple[tuple[float, float], ...]  # sampled (x, y) in category/value space
    coefficients: tuple[float, ...] = ()
    r_squared: float = 0.0


def _clean_data_points(
    values: Sequence[float | None],
) -> list[tuple[float, float]]:
    """Extract valid (x, y) pairs where x is 1-based category index."""
    points: list[tuple[float, float]] = []
    for idx, val in enumerate(values):
        if val is None:
            continue
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            continue
        f_val = float(val)
        if math.isfinite(f_val):
            points.append((float(idx + 1), f_val))
    return points


def _qr_solve(
    matrix: list[list[float]],
    vector: list[float],
) -> list[float]:
    """Solve min ||A x - b||_2 via Modified Gram-Schmidt QR decomposition.

    matrix is m x n where m >= n.
    vector is of length m.
    """
    m = len(matrix)
    if m == 0:
        raise TrendlineFitRefusal("matrix has no rows")
    n = len(matrix[0])
    if m < n:
        raise TrendlineFitRefusal("matrix has fewer rows than columns")

    # Guard against non-finite values
    for row in matrix:
        for val in row:
            if not math.isfinite(val):
                raise TrendlineFitRefusal("matrix contains non-finite values")
    for val in vector:
        if not math.isfinite(val):
            raise TrendlineFitRefusal("vector contains non-finite values")

    # Extract columns
    q_cols = [[matrix[i][j] for i in range(m)] for j in range(n)]
    r_mat = [[0.0] * n for _ in range(n)]

    for j in range(n):
        norm_sq = sum(q_cols[j][i] ** 2 for i in range(m))
        norm = math.sqrt(norm_sq)
        if norm < 1e-10 or not math.isfinite(norm):
            raise TrendlineFitRefusal("matrix is rank-deficient or degenerate")
        r_mat[j][j] = norm
        inv_norm = 1.0 / norm
        for i in range(m):
            q_cols[j][i] *= inv_norm

        for k in range(j + 1, n):
            dot = sum(q_cols[j][i] * q_cols[k][i] for i in range(m))
            r_mat[j][k] = dot
            for i in range(m):
                q_cols[k][i] -= dot * q_cols[j][i]

    # Guard condition of R matrix
    diags = [abs(r_mat[i][i]) for i in range(n)]
    min_diag = min(diags)
    max_diag = max(diags)
    if min_diag < 1e-10 or (max_diag / min_diag) > 1e14:
        raise TrendlineFitRefusal("matrix is singular or ill-conditioned")

    # d = Q^T b
    d_vec = [sum(q_cols[j][i] * vector[i] for i in range(m)) for j in range(n)]

    # Back substitution: R x = d
    x = [0.0] * n
    for j in range(n - 1, -1, -1):
        s = sum(r_mat[j][k] * x[k] for k in range(j + 1, n))
        x[j] = (d_vec[j] - s) / r_mat[j][j]
        if not math.isfinite(x[j]):
            raise TrendlineFitRefusal(
                "polynomial solve produced non-finite coefficients"
            )

    return x


def clip_line_to_rect(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Clip a 2D line segment to an axis-aligned bounding box using Liang-Barsky."""
    dx = x1 - x0
    dy = y1 - y0
    p = [-dx, dx, -dy, dy]
    q = [x0 - xmin, xmax - x0, y0 - ymin, ymax - y0]
    u1 = 0.0
    u2 = 1.0

    for pi, qi in zip(p, q):
        if pi == 0:
            if qi < 0:
                return None
        elif pi < 0:
            u1 = max(u1, qi / pi)
        else:
            u2 = min(u2, qi / pi)
        if u1 > u2:
            return None

    return (
        (x0 + u1 * dx, y0 + u1 * dy),
        (x0 + u2 * dx, y0 + u2 * dy),
    )


def fit_trendline(
    trendline_type: str,
    values: Sequence[float | None],
    *,
    order: int | None = None,
    period: int | None = None,
    forward: float | None = None,
    backward: float | None = None,
    intercept: float | None = None,
    num_samples: int = 100,
) -> TrendlineFitResult:
    """Fit a regression trendline to series values and sample curve coordinates."""
    if trendline_type not in SUPPORTED_TRENDLINE_TYPES:
        raise TrendlineFitRefusal(f"unsupported trendline type {trendline_type!r}")

    category_count = len(values)
    if category_count == 0:
        raise TrendlineFitRefusal("series has no data points")

    valid_points = _clean_data_points(values)
    n_pts = len(valid_points)
    if n_pts == 0:
        raise TrendlineFitRefusal("series has no valid numeric data points")

    fwd = float(forward) if forward is not None else 0.0
    bwd = float(backward) if backward is not None else 0.0
    if fwd < 0.0:
        raise TrendlineFitRefusal("forward forecast must be non-negative")
    if bwd < 0.0:
        raise TrendlineFitRefusal("backward forecast must be non-negative")

    x_min = 1.0 - bwd
    x_max = float(category_count) + fwd

    # 1. LINEAR
    if trendline_type == "linear":
        if intercept is not None:
            c = float(intercept)
            if n_pts < 1:
                raise TrendlineFitRefusal(
                    "linear trendline requires at least 1 valid data point"
                )
            sum_x2 = sum(x * x for x, _ in valid_points)
            sum_xy = sum(x * (y - c) for x, y in valid_points)
            if abs(sum_x2) < 1e-12:
                raise TrendlineFitRefusal(
                    "linear trendline cannot be fitted to degenerate data"
                )
            slope = sum_xy / sum_x2
            coeffs = (c, slope)
            predict_fn = lambda x, s=slope, ic=c: ic + s * x
        else:
            if n_pts < 2:
                raise TrendlineFitRefusal(
                    "linear trendline requires at least 2 valid data points"
                )
            avg_x = sum(x for x, _ in valid_points) / n_pts
            avg_y = sum(y for _, y in valid_points) / n_pts
            s_xx = sum((x - avg_x) ** 2 for x, _ in valid_points)
            s_xy = sum((x - avg_x) * (y - avg_y) for x, y in valid_points)
            if abs(s_xx) < 1e-12:
                raise TrendlineFitRefusal(
                    "linear trendline cannot be fitted to degenerate data"
                )
            slope = s_xy / s_xx
            b_val = avg_y - slope * avg_x
            coeffs = (b_val, slope)
            predict_fn = lambda x, s=slope, b=b_val: b + s * x

        points = ((x_min, predict_fn(x_min)), (x_max, predict_fn(x_max)))
        return TrendlineFitResult(
            type="linear",
            predict=predict_fn,
            points=points,
            coefficients=coeffs,
        )

    # 2. EXPONENTIAL
    if trendline_type == "exp":
        if any(y <= 0.0 for _, y in valid_points):
            raise TrendlineFitRefusal(
                "exponential trendline requires all data values to be positive"
            )

        if intercept is not None:
            c = float(intercept)
            if c <= 0.0:
                raise TrendlineFitRefusal(
                    "exponential trendline intercept must be positive"
                )
            if n_pts < 1:
                raise TrendlineFitRefusal(
                    "exponential trendline requires at least 1 valid data point"
                )
            ln_c = math.log(c)
            sum_x2 = sum(x * x for x, _ in valid_points)
            sum_x_lny = sum(x * (math.log(y) - ln_c) for x, y in valid_points)
            if abs(sum_x2) < 1e-12:
                raise TrendlineFitRefusal(
                    "exponential trendline cannot be fitted to degenerate data"
                )
            slope = sum_x_lny / sum_x2
            coeffs = (c, slope)
            predict_fn = lambda x, s=slope, ic=c: ic * math.exp(s * x)
        else:
            if n_pts < 2:
                raise TrendlineFitRefusal(
                    "exponential trendline requires at least 2 valid data points"
                )
            avg_x = sum(x for x, _ in valid_points) / n_pts
            avg_lny = sum(math.log(y) for _, y in valid_points) / n_pts
            s_xx = sum((x - avg_x) ** 2 for x, _ in valid_points)
            s_x_lny = sum(
                (x - avg_x) * (math.log(y) - avg_lny) for x, y in valid_points
            )
            if abs(s_xx) < 1e-12:
                raise TrendlineFitRefusal(
                    "exponential trendline cannot be fitted to degenerate data"
                )
            slope = s_x_lny / s_xx
            b_val = math.exp(avg_lny - slope * avg_x)
            coeffs = (b_val, slope)
            predict_fn = lambda x, s=slope, b=b_val: b * math.exp(s * x)

        sample_points: list[tuple[float, float]] = []
        for step in range(max(2, num_samples)):
            t = step / (max(2, num_samples) - 1)
            x = x_min + t * (x_max - x_min)
            try:
                y = predict_fn(x)
                if math.isfinite(y):
                    sample_points.append((x, y))
            except (OverflowError, ValueError):
                continue

        if len(sample_points) < 2:
            raise TrendlineFitRefusal(
                "exponential trendline calculation overflowed or produced non-finite values"
            )
        return TrendlineFitResult(
            type="exp",
            predict=predict_fn,
            points=tuple(sample_points),
            coefficients=coeffs,
        )

    # 3. LOGARITHMIC
    if trendline_type == "log":
        if intercept is not None:
            raise TrendlineFitRefusal(
                "logarithmic trendline does not support explicit intercept"
            )
        if x_min <= 0.0:
            raise TrendlineFitRefusal(
                "logarithmic trendline backward forecast extends to non-positive domain"
            )
        if n_pts < 2:
            raise TrendlineFitRefusal(
                "logarithmic trendline requires at least 2 valid data points"
            )

        avg_lnx = sum(math.log(x) for x, _ in valid_points) / n_pts
        avg_y = sum(y for _, y in valid_points) / n_pts
        s_lnx2 = sum((math.log(x) - avg_lnx) ** 2 for x, _ in valid_points)
        s_lnx_y = sum((math.log(x) - avg_lnx) * (y - avg_y) for x, y in valid_points)
        if abs(s_lnx2) < 1e-12:
            raise TrendlineFitRefusal(
                "logarithmic trendline cannot be fitted to degenerate data"
            )
        slope = s_lnx_y / s_lnx2
        b_val = avg_y - slope * avg_lnx
        coeffs = (b_val, slope)
        predict_fn = lambda x, s=slope, b=b_val: b + s * math.log(x)

        sample_points = []
        for step in range(max(2, num_samples)):
            t = step / (max(2, num_samples) - 1)
            x = x_min + t * (x_max - x_min)
            if x <= 0.0:
                continue
            try:
                y = predict_fn(x)
                if math.isfinite(y):
                    sample_points.append((x, y))
            except (OverflowError, ValueError):
                continue

        if len(sample_points) < 2:
            raise TrendlineFitRefusal(
                "logarithmic trendline produced insufficient points"
            )
        return TrendlineFitResult(
            type="log",
            predict=predict_fn,
            points=tuple(sample_points),
            coefficients=coeffs,
        )

    # 4. POWER
    if trendline_type == "power":
        if intercept is not None:
            raise TrendlineFitRefusal(
                "power trendline does not support explicit intercept"
            )
        if any(y <= 0.0 for _, y in valid_points):
            raise TrendlineFitRefusal(
                "power trendline requires all data values to be positive"
            )
        if x_min <= 0.0:
            raise TrendlineFitRefusal(
                "power trendline backward forecast extends to non-positive domain"
            )
        if n_pts < 2:
            raise TrendlineFitRefusal(
                "power trendline requires at least 2 valid data points"
            )

        avg_lnx = sum(math.log(x) for x, _ in valid_points) / n_pts
        avg_lny = sum(math.log(y) for _, y in valid_points) / n_pts
        s_lnx2 = sum((math.log(x) - avg_lnx) ** 2 for x, _ in valid_points)
        s_lnx_lny = sum(
            (math.log(x) - avg_lnx) * (math.log(y) - avg_lny) for x, y in valid_points
        )
        if abs(s_lnx2) < 1e-12:
            raise TrendlineFitRefusal(
                "power trendline cannot be fitted to degenerate data"
            )
        slope = s_lnx_lny / s_lnx2
        b_val = math.exp(avg_lny - slope * avg_lnx)
        coeffs = (b_val, slope)
        predict_fn = lambda x, s=slope, b=b_val: b * (x**s)

        sample_points = []
        for step in range(max(2, num_samples)):
            t = step / (max(2, num_samples) - 1)
            x = x_min + t * (x_max - x_min)
            if x <= 0.0:
                continue
            try:
                y = predict_fn(x)
                if math.isfinite(y):
                    sample_points.append((x, y))
            except (OverflowError, ValueError):
                continue

        if len(sample_points) < 2:
            raise TrendlineFitRefusal("power trendline produced insufficient points")
        return TrendlineFitResult(
            type="power",
            predict=predict_fn,
            points=tuple(sample_points),
            coefficients=coeffs,
        )

    # 5. POLYNOMIAL
    if trendline_type == "poly":
        deg = 2 if order is None else int(order)
        if deg < 2 or deg > 6:
            raise TrendlineFitRefusal(
                f"polynomial trendline order must be in range 2 to 6, got {deg}"
            )

        min_required = deg if intercept is not None else deg + 1
        if n_pts < min_required:
            raise TrendlineFitRefusal(
                f"polynomial trendline of order {deg} requires at least {min_required} valid data points"
            )

        if intercept is not None:
            c = float(intercept)
            mat = [[(x ** (j + 1)) for j in range(deg)] for x, _ in valid_points]
            vec = [y - c for _, y in valid_points]
            solved = _qr_solve(mat, vec)
            coeffs = (c, *solved)
        else:
            mat = [[(x**j) for j in range(deg + 1)] for x, _ in valid_points]
            vec = [y for _, y in valid_points]
            coeffs = tuple(_qr_solve(mat, vec))

        def poly_predict(x: float, c_tuple: tuple[float, ...] = coeffs) -> float:
            return sum(c_val * (x**p_idx) for p_idx, c_val in enumerate(c_tuple))

        sample_points = []
        for step in range(max(2, num_samples)):
            t = step / (max(2, num_samples) - 1)
            x = x_min + t * (x_max - x_min)
            try:
                y = poly_predict(x)
                if math.isfinite(y):
                    sample_points.append((x, y))
            except (OverflowError, ValueError):
                continue

        if len(sample_points) < 2:
            raise TrendlineFitRefusal(
                "polynomial trendline produced insufficient points"
            )
        return TrendlineFitResult(
            type="poly",
            predict=poly_predict,
            points=tuple(sample_points),
            coefficients=coeffs,
        )

    # 6. MOVING AVERAGE
    if trendline_type == "movingAvg":
        if intercept is not None:
            raise TrendlineFitRefusal(
                "moving average trendline does not support explicit intercept"
            )
        p = 2 if period is None else int(period)
        if p < 2 or p > 255:
            raise TrendlineFitRefusal(
                f"moving average period must be in range 2 to 255, got {p}"
            )
        if n_pts < p:
            raise TrendlineFitRefusal(
                f"moving average trendline with period {p} requires at least {p} valid data points"
            )

        m_points: list[tuple[float, float]] = []
        for i in range(p - 1, category_count):
            window = values[i - p + 1 : i + 1]
            if all(
                v is not None and isinstance(v, (int, float)) and math.isfinite(v)
                for v in window
            ):
                avg_y = sum(float(v) for v in window) / p  # type: ignore[arg-type]
                m_points.append((float(i + 1), avg_y))

        if len(m_points) < 2:
            raise TrendlineFitRefusal(
                f"moving average trendline with period {p} has insufficient points to render"
            )

        return TrendlineFitResult(
            type="movingAvg",
            predict=lambda x: m_points[-1][1],
            points=tuple(m_points),
        )

    raise TrendlineFitRefusal(f"unsupported trendline type {trendline_type!r}")
