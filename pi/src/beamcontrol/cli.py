"""beamctl: operator and diagnostic CLI for the BeamControl CAN controller."""

from __future__ import annotations

import argparse
import sys

import can

from . import protocol as P
from .client import BeamControlClient, BeamControlError
from .transport import SocketCanTransport


def _client(args: argparse.Namespace) -> BeamControlClient:
    return BeamControlClient(
        SocketCanTransport(args.iface),
        source_node=args.source,
        timeout=args.timeout,
        retries=args.retries,
    )


def _add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--iface", default="beamcan0", help="CAN interface (default beamcan0)")
    p.add_argument("--source", type=int, default=0, help="controller node id (default 0)")
    p.add_argument("--timeout", type=float, default=0.02, help="response timeout (s)")
    p.add_argument("--retries", type=int, default=2, help="retries per command")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and print the command without opening SocketCAN",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="beamctl", description="uORocketry BeamControl CAN controller CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser(
        "discover", help="scan receiver-board nodes 1-30 for presence + protocol info"
    )
    _add_common_args(p)

    p = sub.add_parser("ping", help="query one receiver board")
    p.add_argument("node", type=int, help="receiver-board CAN node 1-30")
    _add_common_args(p)

    p = sub.add_parser("set-phase", help="set the receiver phase state")
    p.add_argument("node", type=int, help="receiver-board CAN node 1-30")
    p.add_argument("--state", type=int, required=True, help="phase-state index 0-255")
    _add_common_args(p)

    p = sub.add_parser("set-vga", help="set the receiver VGA attenuation")
    p.add_argument("node", type=int, help="receiver-board CAN node 1-30")
    p.add_argument("--attenuation", type=int, required=True, help="attenuation 0-23 dB")
    _add_common_args(p)

    p = sub.add_parser("set-combined", help="set receiver phase and VGA")
    p.add_argument("node", type=int, help="receiver-board CAN node 1-30")
    p.add_argument("--state", type=int, required=True, help="phase-state index 0-255")
    p.add_argument("--attenuation", type=int, required=True, help="attenuation 0-23 dB")
    _add_common_args(p)

    p = sub.add_parser("enter-safe", help="enter the receiver safe state")
    p.add_argument("node", type=int, help="receiver-board CAN node 1-30")
    _add_common_args(p)

    return parser


def _dry_run(args: argparse.Namespace) -> None:
    common = (
        f"iface={args.iface} source={args.source} timeout={args.timeout:g}s retries={args.retries}"
    )
    if args.command == "discover":
        detail = "nodes=1-30"
    elif args.command == "ping":
        detail = f"node={args.node}"
    elif args.command == "set-phase":
        detail = f"node={args.node} state={args.state}"
    elif args.command == "set-vga":
        detail = f"node={args.node} attenuation={args.attenuation}"
    elif args.command == "set-combined":
        detail = f"node={args.node} state={args.state} attenuation={args.attenuation}"
    else:
        detail = f"node={args.node}"
    print(f"DRY RUN {args.command}: {detail} {common}")


def _validate_arguments(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.source != P.CONTROLLER_NODE:
        parser.error(f"--source must be controller node {P.CONTROLLER_NODE}")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.retries < 0:
        parser.error("--retries must be non-negative")
    if args.command != "discover" and not 1 <= args.node <= 30:
        parser.error("node must be a receiver node 1..30")
    if args.command in {"set-phase", "set-combined"}:
        P.validate_phase_state(args.state)
    if args.command in {"set-vga", "set-combined"}:
        P.validate_attenuation(args.attenuation)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        _validate_arguments(parser, args)
    except ValueError as error:
        parser.error(str(error))
    if args.dry_run:
        _dry_run(args)
        return 0
    c: BeamControlClient | None = None
    try:
        c = _client(args)
        if args.command == "discover":
            discovered = 0
            for node in range(1, 31):
                try:
                    status = c.discover(node)
                    discovered += 1
                    print(
                        f"node {node:2d}: v{status.major}.{status.minor}.{status.patch} "
                        f"health=0x{status.health_flags:02x} "
                        f"rx_drop={status.rx_dropped} tx_drop={status.tx_dropped} "
                        f"invalid={status.invalid_commands}"
                    )
                except BeamControlError:
                    pass
            if discovered == 0:
                print("error: no receiver boards discovered", file=sys.stderr)
                return 1
        elif args.command == "ping":
            print("STATUS:", c.discover(args.node))
        elif args.command == "set-phase":
            reply = c.set_phase(args.node, args.state)
            print("ACK", reply.hex())
        elif args.command == "set-vga":
            reply = c.set_vga(args.node, args.attenuation)
            print("ACK", reply.hex())
        elif args.command == "set-combined":
            reply = c.set_combined(args.node, args.state, args.attenuation)
            print("ACK", reply.hex())
        elif args.command == "enter-safe":
            print("ACK", c.enter_safe(args.node).hex())
        return 0
    except (BeamControlError, can.CanError, OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        if c is not None:
            c.close()


if __name__ == "__main__":
    sys.exit(main())
