"""Runtime configuration for the BeamControl controller (beamd)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BeamControlConfig:
    channel: str = "can0"
    source_node: int = 0
    poll_interval_s: float = 1.0
    can_timeout_s: float = 0.020
    can_retries: int = 2
    nodes: list[int] = field(default_factory=list)
    web_host: str = "0.0.0.0"
    web_port: int = 8080

    def __post_init__(self) -> None:
        from . import protocol as P  # local import to avoid a cycle at module load

        if not self.channel.strip():
            raise ValueError("channel must be non-empty")
        if self.source_node != P.CONTROLLER_NODE:
            raise ValueError(
                f"source_node must be {P.CONTROLLER_NODE} (controller), got {self.source_node}"
            )
        if self.poll_interval_s <= 0:
            raise ValueError(f"poll_interval_s must be > 0, got {self.poll_interval_s}")
        if self.can_timeout_s <= 0:
            raise ValueError(f"can_timeout_s must be > 0, got {self.can_timeout_s}")
        if self.can_retries < 0:
            raise ValueError(f"can_retries must be >= 0, got {self.can_retries}")
        if not self.web_host.strip():
            raise ValueError("web_host must be non-empty")
        if not 1 <= self.web_port <= 65535:
            raise ValueError(f"web_port must be in the range 1..65535, got {self.web_port}")
        for n in self.nodes:
            if n < P.CONTROLLER_NODE + 1 or n >= P.BROADCAST_NODE:
                raise ValueError(f"receiver node {n} out of range 1..{P.BROADCAST_NODE - 1}")
        if len(set(self.nodes)) != len(self.nodes):
            raise ValueError(f"receiver nodes must be unique: {self.nodes}")

    @classmethod
    def from_file(cls, path: str | Path) -> BeamControlConfig:
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
        root = data.get("beamcontrol", {})
        return cls(
            channel=str(root.get("channel", "can0")),
            source_node=int(root.get("source_node", 0)),
            poll_interval_s=float(root.get("poll_interval_s", 1.0)),
            can_timeout_s=float(root.get("can_timeout_s", 0.020)),
            can_retries=int(root.get("can_retries", 2)),
            nodes=[int(n) for n in root.get("nodes", [])],
            web_host=str(root.get("web_host", "0.0.0.0")),
            web_port=int(root.get("web_port", 8080)),
        )
