import unittest
import uuid

from walldeck.virtual_desktops import _parse_guid_array


class VirtualDesktopParsingTests(unittest.TestCase):
    def test_parses_windows_little_endian_guid_array(self) -> None:
        expected = (
            uuid.UUID("db123877-9fd7-4870-8fe9-0d717cc9070d"),
            uuid.UUID("adb79f09-439b-4751-8b0e-5a35175de39b"),
        )

        actual = _parse_guid_array(b"".join(value.bytes_le for value in expected))

        self.assertEqual(expected, actual)

    def test_rejects_partial_guid(self) -> None:
        with self.assertRaises(ValueError):
            _parse_guid_array(b"invalid")


if __name__ == "__main__":
    unittest.main()
