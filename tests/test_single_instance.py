import unittest
import uuid

from walldeck.single_instance import SingleInstance


class SingleInstanceTests(unittest.TestCase):
    def test_secondary_instance_notifies_primary(self) -> None:
        application_id = f"WallDeck.Test.{uuid.uuid4()}"
        primary = SingleInstance(application_id)
        secondary = SingleInstance(application_id)
        try:
            self.assertTrue(primary.is_primary)
            self.assertFalse(secondary.is_primary)
            self.assertFalse(primary.activation_requested())

            secondary.notify_primary()

            self.assertTrue(primary.activation_requested())
            self.assertFalse(primary.activation_requested())
        finally:
            secondary.close()
            primary.close()


if __name__ == "__main__":
    unittest.main()
