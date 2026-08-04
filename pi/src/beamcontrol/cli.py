"""beamctl: operator and diagnostic CLI for the BeamControl CAN controller."""

from __future__ import annotations

import argparse
import sys

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
    p.add_argument("--iface", default="can0", help="CAN interface (default can0)")
    p.add_argument("--source", type=int, default=0, help="controller node id (default 0)")
    p.add_argument("--timeout", type=float, default=0.02, help="response timeout (s)")
    p.add_argument("--retries", type=int, default=2, help="retries per command")


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

    p = sub.add_parser("set-phase", help="set one or all phase states")
    p.add_argument("node", type=int, help="receiver-board CAN node 1-30")
    phase = p.add_mutually_exclusive_group(required=True)
    phase.add_argument("--state", type=int, help="one phase-state index 0-255")
    phase.add_argument(
        "--states",
        nargs=4,
        type=int,
        metavar=("PS1", "PS2", "PS3", "PS4"),
        help="four phase-state indexes 0-255",
    )
    p.add_argument("--channel", type=int, help="RF channel 0-3 for --state")
    _add_common_args(p)

    p = sub.add_parser("set-vga", help="set one or all VGA attenuations")
    p.add_argument("node", type=int, help="receiver-board CAN node 1-30")
    vga = p.add_mutually_exclusive_group(required=True)
    vga.add_argument("--attenuation", type=int, help="one attenuation value 0-23 dB")
    vga.add_argument(
        "--attenuations",
        nargs=4,
        type=int,
        metavar=("VGA1", "VGA2", "VGA3", "VGA4"),
        help="four attenuation values, each 0-23 dB",
    )
    p.add_argument("--channel", type=int, help="RF channel 0-3 for --attenuation")
    _add_common_args(p)

    p = sub.add_parser("set-combined", help="set phase and VGA for one or all channels")
    p.add_argument("node", type=int, help="receiver-board CAN node 1-30")
    phase = p.add_mutually_exclusive_group(required=True)
    phase.add_argument("--state", type=int, help="one phase-state index 0-255")
    phase.add_argument(
        "--states",
        nargs=4,
        type=int,
        metavar=("PS1", "PS2", "PS3", "PS4"),
        help="four phase-state indexes 0-255",
    )
    vga = p.add_mutually_exclusive_group(required=True)
    vga.add_argument("--attenuation", type=int, help="one attenuation value 0-23 dB")
    vga.add_argument(
        "--attenuations",
        nargs=4,
        type=int,
        metavar=("VGA1", "VGA2", "VGA3", "VGA4"),
        help="four attenuation values, each 0-23 dB",
    )
    p.add_argument("--channel", type=int, help="RF channel 0-3 for individual mode")
    _add_common_args(p)

    p = sub.add_parser("enter-safe", help="enter safe state on one RF channel")
    p.add_argument("node", type=int, help="receiver-board CAN node 1-30")
    p.add_argument("--channel", type=int, required=True, help="RF channel 0-3")
    _add_common_args(p)

    return parser


def _validate_command_arguments(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.command == "set-phase":
        if args.states is not None and args.channel is not None:
            parser.error("--channel is valid only with --state")
        if args.state is not None and args.channel is None:
            parser.error("--state requires --channel")
    elif args.command == "set-vga":
        if args.attenuations is not None and args.channel is not None:
            parser.error("--channel is valid only with --attenuation")
        if args.attenuation is not None and args.channel is None:
            parser.error("--attenuation requires --channel")
    elif args.command == "set-combined":
        bulk = args.states is not None and args.attenuations is not None
        individual = args.state is not None and args.attenuation is not None
        if not (bulk or individual):
            parser.error("use --state with --attenuation, or --states with --attenuations")
        if bulk and args.channel is not None:
            parser.error("--channel is valid only for individual mode")
        if individual and args.channel is None:
            parser.error("individual mode requires --channel")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _validate_command_arguments(parser, args)
    c = _client(args)
    try:
        if args.command == "discover":
            for node in range(1, 31):
                try:
                    status = c.discover(node)
                    print(
                        f"node {node:2d}: v{status.major}.{status.minor}.{status.patch} "
                        f"health=0x{status.health_flags:02x} "
                        f"rx_drop={status.rx_dropped} tx_drop={status.tx_dropped} "
                        f"invalid={status.invalid_commands}"
                    )
                except BeamControlError:
                    pass
        elif args.command == "ping":
            print("STATUS:", c.discover(args.node))
        elif args.command == "set-phase":
            if args.states is not None:
                reply = c.set_phase(args.node, args.states)
            else:
                reply = c.set_phase_channel(args.node, args.channel, args.state)
            print("ACK", reply.hex())
        elif args.command == "set-vga":
            if args.attenuations is not None:
                reply = c.set_vga(args.node, args.attenuations)
            else:
                reply = c.set_vga_channel(args.node, args.channel, args.attenuation)
            print("ACK", reply.hex())
        elif args.command == "set-combined":
            if args.states is not None:
                reply = c.set_combined(args.node, args.states, args.attenuations)
            else:
                reply = c.set_combined_channel(
                    args.node,
                    args.channel,
                    args.state,
                    args.attenuation,
                )
            print("ACK", reply.hex())
        elif args.command == "enter-safe":
            print("ACK", c.enter_safe(args.node, args.channel).hex())
        return 0
    except (BeamControlError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
