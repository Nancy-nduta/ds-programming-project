class ConsistentHashMap:
    def __init__(self, num_slots=512, num_virtual=9):
        self.num_slots = num_slots
        self.num_virtual = num_virtual
        self.slot_to_server = {}   # slot -> server_id (hostname)
        self.server_to_slots = {}  # server_id -> [slots]

    def _request_hash(self, i):
        return (i*i + 2*i + 17) % self.num_slots

    def _virtual_hash(self, i, j):
        return (i*i + j*j + 2*j + 25) % self.num_slots

    def _find_free_slot(self, start):
        slot = start % self.num_slots
        step = 1
        while slot in self.slot_to_server:
            slot = (start + step*step) % self.num_slots  # quadratic probing
            step += 1
        return slot

    def add_server(self, server_id, server_num):
        slots = []
        for j in range(self.num_virtual):
            h = self._virtual_hash(server_num, j)
            slot = self._find_free_slot(h)
            self.slot_to_server[slot] = server_id
            slots.append(slot)
        self.server_to_slots[server_id] = slots

    def remove_server(self, server_id):
        for slot in self.server_to_slots.pop(server_id, []):
            del self.slot_to_server[slot]

    def get_server(self, request_id):
        if not self.slot_to_server:
            return None
        start = self._request_hash(request_id)
        slot = start
        for _ in range(self.num_slots):
            if slot in self.slot_to_server:
                return self.slot_to_server[slot]
            slot = (slot + 1) % self.num_slots  # clockwise search
        return None