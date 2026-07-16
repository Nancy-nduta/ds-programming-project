"""
Unit tests for the ConsistentHashMap implementation.
Run with: pytest tests/test_consistent_hash.py -v
"""
import sys
import os

# Allow importing consistent_hash.py from the loadbalancer/ folder
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loadbalancer"))

from consistent_hash import ConsistentHashMap


def test_add_server_creates_virtual_slots():
    """Adding one server should register exactly K virtual slots."""
    chm = ConsistentHashMap(num_slots=512, num_virtual=9)
    chm.add_server("S1", 1)
    assert len(chm.server_to_slots["S1"]) == 9
    assert len(chm.slot_to_server) == 9


def test_remove_server_clears_its_slots():
    """Removing a server should free all its virtual slots."""
    chm = ConsistentHashMap(num_slots=512, num_virtual=9)
    chm.add_server("S1", 1)
    chm.remove_server("S1")
    # server_to_slots shouldn't even have the key anymore, not just an empty list
    assert chm.server_to_slots.get("S1") is None
    assert len(chm.slot_to_server) == 0


def test_get_server_returns_none_when_empty():
    """With no servers registered, routing should return None."""
    chm = ConsistentHashMap(num_slots=512, num_virtual=9)
    # Arbitrary request id, doesn't matter what it hashes to since
    # there's nothing to route to anyway
    assert chm.get_server(123456) is None


def test_get_server_returns_a_valid_registered_server():
    """A routed request must resolve to one of the currently registered servers."""
    chm = ConsistentHashMap(num_slots=512, num_virtual=9)
    chm.add_server("S1", 1)
    chm.add_server("S2", 2)
    chm.add_server("S3", 3)

    # We're not checking which server it lands on (that depends on the
    # hash function), just that it's one of the three that exist.
    result = chm.get_server(132574)
    assert result in ["S1", "S2", "S3"]


def test_collision_handling_no_overwrites():
    """Adding multiple servers should never let one server's virtual slot
    silently overwrite another's — every slot recorded must map back
    correctly to exactly the server that owns it."""
    chm = ConsistentHashMap(num_slots=512, num_virtual=9)
    chm.add_server("S1", 1)
    chm.add_server("S2", 2)
    chm.add_server("S3", 3)

    # If a collision had silently overwritten a slot, slot_to_server would
    # end up smaller than the sum of what each server thinks it owns.
    total_slots = sum(len(v) for v in chm.server_to_slots.values())
    assert total_slots == len(chm.slot_to_server)


def test_removing_one_server_does_not_affect_others():
    """Removing one server should not disturb the other servers' slot assignments."""
    chm = ConsistentHashMap(num_slots=512, num_virtual=9)
    chm.add_server("S1", 1)
    chm.add_server("S2", 2)
    chm.add_server("S3", 3)

    # Snapshot S2's slots before touching anything else, then compare
    # after removing S1 to make sure S2 wasn't accidentally reshuffled.
    s2_slots_before = set(chm.server_to_slots["S2"])
    chm.remove_server("S1")
    s2_slots_after = set(chm.server_to_slots["S2"])

    assert s2_slots_before == s2_slots_after