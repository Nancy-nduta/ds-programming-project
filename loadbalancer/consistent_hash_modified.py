class ConsistentHashMap:
    def __init__(self, num_slots=512, num_virtual=9):
        # num_slots: total positions on the ring
        # num_virtual: virtual copies per physical server, spreads
        # load out more evenly than one point per server would
        self.num_slots = num_slots
        self.num_virtual = num_virtual
        self.slot_to_server = {}   # slot -> server_id (hostname)
        self.server_to_slots = {}  # server_id -> [slots]

    def _request_hash(self, i):
        # Modified hash function for A-4: better bit-mixing than the quadratic default
        return (hash(f"req-{i}") ) % self.num_slots

    def _virtual_hash(self, i, j):
        # Modified hash function for A-4, j keeps each virtual copy of
        # the same server landing on a different slot
        return (hash(f"srv-{i}-{j}")) % self.num_slots

    def _find_free_slot(self, start):
        # If start is taken, hop forward using quadratic probing rather
        # than overwriting whatever server is already sitting there
        slot = start % self.num_slots
        step = 1
        while slot in self.slot_to_server:
            slot = (start + step*step) % self.num_slots
            step += 1
        return slot

    def add_server(self, server_id, server_num):
        # Drops num_virtual copies of this server around the ring
        slots = []
        for j in range(self.num_virtual):
            h = self._virtual_hash(server_num, j)
            slot = self._find_free_slot(h)
            self.slot_to_server[slot] = server_id
            slots.append(slot)
        self.server_to_slots[server_id] = slots

    def remove_server(self, server_id):
        # Clears out every slot this server was occupying
        for slot in self.server_to_slots.pop(server_id, []):
            del self.slot_to_server[slot]

    def get_server(self, request_id):
        if not self.slot_to_server:
            return None
        # Hash the request onto the ring, then walk forward until we
        # hit an occupied slot, that's the server responsible for it
        start = self._request_hash(request_id)
        slot = start
        for _ in range(self.num_slots):
            if slot in self.slot_to_server:
                return self.slot_to_server[slot]
            slot = (slot + 1) % self.num_slots
        return None