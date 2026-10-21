"""
滑块验证码轨迹生成引擎

核心原理：
1. 真人滑动轨迹 = 加速 -> 匀速 -> 减速 -> 微调 四阶段
2. 风控系统检测：速度峰值、加速度突变、y轴抖动频率、停顿次数
3. 贝塞尔曲线 + 物理引擎模拟 -> 生成拟人轨迹
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class TrackPoint:
    x: float
    y: float
    t: float
    vx: float = 0.0
    vy: float = 0.0

    def to_dict(self) -> dict:
        return {"x": round(self.x, 2), "y": round(self.y, 2), "t": round(self.t, 2)}


@dataclass
class TrajectoryConfig:
    distance: int
    start_x: int = 0
    start_y: int = 0
    min_duration: float = 800.0
    max_duration: float = 2500.0
    max_speed: float = 0.0
    acceleration: float = 0.0
    overshoot_range: Tuple[int, int] = (5, 15)
    y_jitter_sigma: float = 1.5
    pause_probability: float = 0.3
    max_pauses: int = 3
    pause_duration: Tuple[float, float] = (50, 200)


class SliderTrajectoryEngine:
    """
    滑块轨迹生成引擎

    四阶段轨迹模型：
    Phase 1: 加速期 (0%-30%)  二次加速曲线
    Phase 2: 高速期 (30%-65%) 接近匀速
    Phase 3: 减速期 (65%-90%) 线性减速
    Phase 4: 微调期 (90%-100%) 含过冲回弹
    """

    def __init__(self, config: Optional[TrajectoryConfig] = None):
        self.config = config or TrajectoryConfig(distance=200)
        self._rng = random.Random()

    def generate(self) -> List[TrackPoint]:
        cfg = self.config
        distance = cfg.distance
        if distance <= 0:
            return []

        overshoot = self._rng.randint(*cfg.overshoot_range)
        total_distance = distance + overshoot

        duration = self._rng.uniform(cfg.min_duration, cfg.max_duration)
        duration *= (1 + total_distance / 500)
        duration = min(duration, cfg.max_duration * 1.5)

        max_speed = cfg.max_speed or (total_distance / duration * 2.5)
        accel = cfg.acceleration or (max_speed / (duration * 0.3))

        points = self._generate_phased_trajectory(
            total_distance=total_distance,
            duration=duration,
            max_speed=max_speed,
            acceleration=accel,
        )

        points = self._add_y_jitter(points, cfg.y_jitter_sigma)
        points = self._add_pauses(points, cfg)
        points = self._add_overshoot_correction(points, distance)

        if points:
            points[0] = TrackPoint(cfg.start_x, cfg.start_y, 0, 0, 0)

        return points

    def _generate_phased_trajectory(
        self,
        total_distance: float,
        duration: float,
        max_speed: float,
        acceleration: float,
    ) -> List[TrackPoint]:
        points: List[TrackPoint] = []
        num_points = max(50, int(duration / 5))
        phase_bounds = [0.0, 0.30, 0.65, 0.90, 1.0]
        prev_x = 0.0
        prev_t = 0.0

        for i in range(num_points + 1):
            progress = i / num_points
            t = progress * duration
            x = self._phase_displacement(progress, total_distance, phase_bounds)
            dt = t - prev_t if i > 0 else 1
            vx = (x - prev_x) / dt if dt > 0 else 0
            points.append(TrackPoint(x=x, y=0, t=t, vx=vx, vy=0))
            prev_x = x
            prev_t = t

        return points

    def _phase_displacement(
        self, progress: float, total_distance: float, bounds: List[float],
    ) -> float:
        if progress <= bounds[1]:
            t_norm = progress / bounds[1]
            return total_distance * 0.15 * (t_norm ** 2)
        elif progress <= bounds[2]:
            t_norm = (progress - bounds[1]) / (bounds[2] - bounds[1])
            return total_distance * (0.15 + 0.55 * t_norm)
        elif progress <= bounds[3]:
            t_norm = (progress - bounds[2]) / (bounds[3] - bounds[2])
            return total_distance * (0.70 + 0.25 * math.sin(math.pi / 2 * t_norm))
        else:
            t_norm = (progress - bounds[3]) / (bounds[4] - bounds[3])
            overshoot_factor = 1.0 + 0.08 * math.sin(math.pi * t_norm - math.pi / 2)
            return total_distance * (0.95 + 0.05 * t_norm) * overshoot_factor

    def _add_y_jitter(self, points: List[TrackPoint], sigma: float) -> List[TrackPoint]:
        result = []
        for p in points:
            jitter = self._rng.gauss(0, sigma) if p.t > 0 else 0
            vy = jitter / 5.0 if p.t > 0 else 0
            result.append(TrackPoint(x=p.x, y=p.y + jitter, t=p.t, vx=p.vx, vy=vy))
        return result

    def _add_pauses(self, points: List[TrackPoint], cfg: TrajectoryConfig) -> List[TrackPoint]:
        if not points or len(points) < 10:
            return points
        num_pauses = 0
        result = [points[0]]
        for i in range(1, len(points)):
            p = points[i]
            progress = p.t / points[-1].t
            if (0.2 < progress < 0.8
                    and num_pauses < cfg.max_pauses
                    and self._rng.random() < cfg.pause_probability * 0.05):
                pause_dur = self._rng.uniform(*cfg.pause_duration)
                result.append(TrackPoint(x=p.x, y=p.y, t=p.t, vx=0, vy=0))
                result.append(TrackPoint(x=p.x, y=p.y, t=p.t + pause_dur, vx=0, vy=0))
                num_pauses += 1
            else:
                result.append(p)
        return result

    def _add_overshoot_correction(self, points: List[TrackPoint], target: int) -> List[TrackPoint]:
        if not points:
            return points
        last = points[-1]
        for i in range(1, 6):
            progress = i / 5
            x = last.x + (target - last.x) * progress
            t = last.t + i * 10
            points.append(TrackPoint(x=x, y=last.y, t=t))
        return points

    def to_mouse_events(self, points: List[TrackPoint]) -> List[dict]:
        events = []
        for i, p in enumerate(points):
            delay = 0
            if i > 0:
                delay = p.t - points[i - 1].t
            events.append({"type": "mousemove", "x": p.x, "y": p.y, "delay": max(0, delay)})
        events.append({"type": "mouseup", "x": points[-1].x, "y": points[-1].y, "delay": 0})
        return events


class BezierTrajectoryGenerator:
    """贝塞尔曲线轨迹生成器"""

    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed)

    def generate(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        num_points: int = 100,
        curvature: float = 0.3,
    ) -> List[Tuple[float, float]]:
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        dist = math.hypot(dx, dy)
        offset = dist * curvature
        cp1 = (
            start[0] + dx * 0.25 + self._rng.gauss(0, offset * 0.3),
            start[1] + dy * 0.25 + self._rng.gauss(0, offset),
        )
        cp2 = (
            start[0] + dx * 0.75 + self._rng.gauss(0, offset * 0.3),
            start[1] + dy * 0.75 + self._rng.gauss(0, offset * 0.5),
        )
        points = []
        for i in range(num_points + 1):
            t = i / num_points
            x, y = self._cubic_bezier(t, start, cp1, cp2, end)
            points.append((x, y))
        return points

    @staticmethod
    def _cubic_bezier(
        t: float,
        p0: Tuple[float, float],
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        p3: Tuple[float, float],
    ) -> Tuple[float, float]:
        u = 1 - t
        tt = t * t
        uu = u * u
        uuu = uu * u
        ttt = tt * t
        x = uuu * p0[0] + 3 * uu * t * p1[0] + 3 * u * tt * p2[0] + ttt * p3[0]
        y = uuu * p0[1] + 3 * uu * t * p1[1] + 3 * u * tt * p2[1] + ttt * p3[1]
        return (x, y)
