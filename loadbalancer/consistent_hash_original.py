class ConsistentHashMap:
    def __init__(self, num_slots=512, num_virtual=9):
        # num_slots: total positions on the hash ring
        # num_virtual: how many virtual copies of each physical server
        # get placed on the ring, spreads load out more evenly than
        # giving each server just one point
        self.num_slots = num_slots
        self.num_virtual = num_virtual
        self.slot_to_server = {}   # slot -> server_id (hostname)
        self.server_to_slots = {}  # server_id -> [slots]

    def _request_hash(self, i):
        # Maps a request ID onto a ring slot
        return (i*i + 2*i + 17) % self.num_slots

    def _virtual_hash(self, i, j):
        # Maps a (server number, virtual index) pair onto a ring slot,
        # j makes sure each virtual copy of the same server lands somewhere different
        return (i*i + j*j + 2*j + 25) % self.num_slots

    def _find_free_slot(self, start):
        # If start is already occupied, keep hopping forward using
        # quadratic probing instead of just overwriting whoever's there
        slot = start % self.num_slots
        step = 1
        while slot in self.slot_to_server:
            slot = (start + step*step) % self.num_slots  # quadratic probing
            step += 1
        return slot

    def add_server(self, server_id, server_num):
        # Places num_virtual copies of this server around the ring
        slots = []
        for j in range(self.num_virtual):
            h = self._virtual_hash(server_num, j)
            slot = self._find_free_slot(h)
            self.slot_to_server[slot] = server_id
            slots.append(slot)
        self.server_to_slots[server_id] = slots

    def remove_server(self, server_id):
        # Frees up every slot this server was holding, so future
        # servers can land there
        for slot in self.server_to_slots.pop(server_id, []):
            del self.slot_to_server[slot]

    def get_server(self, request_id):
        if not self.slot_to_server:
            return None
        # Hash the request, then walk clockwise around the ring until
        # we land on an occupied slot, that server owns the request
        start = self._request_hash(request_id)
        slot = start
        for _ in range(self.num_slots):
            if slot in self.slot_to_server:
                return self.slot_to_server[slot]
            slot = (slot + 1) % self.num_slots  # clockwise search
        return None