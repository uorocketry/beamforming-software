"""Host-runnable regression tests for the BeamControl v2.0 protocol module.

Run:  pytest pi/tests/unit/test_protocol.py -v
"""

from __future__ import annotations

import unittest

from beamcontrol import protocol as P


class TestIdEncodeDecode(unittest.TestCase):
    def test_round_trip(self):
        can_id = P.build_id(P.SET_PHASE, 5, 0, 42)
        f = P.parse_id(can_id)
        self.assertEqual(f["type"], P.SET_PHASE)
        self.assertEqual(f["dest"], 5)
        self.assertEqual(f["source"], 0)
        self.assertEqual(f["sequence"], 42)
        self.assertEqual(can_id, 0x08A0002A)

    def test_bit_layout(self):
        # type bits 28:26, dest 25:21, source 20:16, seq 15:0
        self.assertEqual(P.build_id(0, 0, 0, 0), 0)
        self.assertEqual(P.build_id(1, 0, 0, 0), 1 << 26)
        self.assertEqual(P.build_id(0, 1, 0, 0), 1 << 21)
        self.assertEqual(P.build_id(0, 0, 1, 0), 1 << 16)

    def test_max_id(self):
        can_id = P.build_id(7, 31, 31, P.SEQ_MASK)
        self.assertLessEqual(can_id, P.CAN_EXT_ID_MAX)
        f = P.parse_id(can_id)
        self.assertEqual(f["type"], 7)
        self.assertEqual(f["dest"], 31)
        self.assertEqual(f["source"], 31)
        self.assertEqual(f["sequence"], P.SEQ_MASK)

    def test_invalid_fields(self):
        for bad in [
            lambda: P.build_id(8, 0, 0, 0),
            lambda: P.build_id(0, 32, 0, 0),
            lambda: P.build_id(0, 0, 32, 0),
            lambda: P.build_id(0, 0, 0, P.SEQ_MASK + 1),
        ]:
            with self.assertRaises(ValueError):
                bad()


class TestValidation(unittest.TestCase):
    def test_strict_channels_0_3(self):
        for channel in (0, 1, 2, 3):
            P.validate_channel(channel)
        for channel in (4, 5, 15, 255):
            with self.assertRaises(ValueError):
                P.validate_channel(channel)

    def test_bulk_attenuation_uses_every_1_db_step(self):
        for attenuation in range(P.ATTEN_DB_MAX + 1):
            self.assertEqual(
                P.validate_attenuations([attenuation] * P.RF_CHANNEL_COUNT),
                bytes([attenuation] * P.RF_CHANNEL_COUNT),
            )
        with self.assertRaises(ValueError):
            P.validate_attenuations([0, 1, 2, 24])
        with self.assertRaises(ValueError):
            P.validate_attenuations([0, 1, 2])

    def test_bulk_phase_states_0_255(self):
        self.assertEqual(
            P.validate_phase_states([0, 1, 254, 255]),
            bytes([0, 1, 254, 255]),
        )
        with self.assertRaises(ValueError):
            P.validate_phase_states([0, 1, 2, 256])
        with self.assertRaises(ValueError):
            P.validate_phase_states([0, 1, 2])


class TestConstants(unittest.TestCase):
    def test_type_numbers(self):
        self.assertEqual(P.ENTER_SAFE, 0)
        self.assertEqual(P.SET_COMBINED, 1)
        self.assertEqual(P.SET_PHASE, 2)
        self.assertEqual(P.SET_VGA, 3)
        self.assertEqual(P.PING, 4)
        self.assertEqual(P.STATUS, 5)
        self.assertEqual(P.ACK, 6)
        self.assertEqual(P.ERROR, 7)

    def test_nodes(self):
        self.assertEqual(P.CONTROLLER_NODE, 0)
        self.assertEqual(P.BROADCAST_NODE, 31)

    def test_discovery_sequence_reserved(self):
        self.assertEqual(P.SEQ_CAPABILITIES, 0xFFFF)

    def test_protocol_version_and_bulk_feature(self):
        self.assertEqual((P.PROTOCOL_MAJOR, P.PROTOCOL_MINOR, P.PROTOCOL_PATCH), (2, 0, 0))
        self.assertEqual(P.RF_CHANNEL_COUNT, 4)
        self.assertTrue(P.FEATURE_FLAGS & P.FEATURE_BULK_RF_UPDATE)


if __name__ == "__main__":
    unittest.main()
