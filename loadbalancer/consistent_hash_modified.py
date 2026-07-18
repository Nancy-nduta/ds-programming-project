class ConsistentHashMap:
    def __init__(self, num_slots=512, num_virtual=9):
        # num_slots: total positions on the hash ring
        # num_virtual: how many virtual copies of each physical server
        # are placed on the ring, to smooth out load distribution
        self.num_slots = num_slots
        self.num_virtual = num_virtual
        self.slot_to_server = {}   # maps ring slot -> server hostname
        self.server_to_slots = {}  # maps server hostname -> list of its slots
        self.server_to_num = {}    # maps server hostname -> its stable server_num
        self._next_server_num = 0  # monotonically increasing, never reused

    def _request_hash(self, i):
        # Original (Task 2 spec): (i*i + 2*i + 17) % num_slots -- quadratic
        # growth means consecutive request IDs land close together on the
        # ring, clustering traffic instead of spreading it.
        #
        # Modified for A-4: multiplicative hash using a large odd constant
        # (scaled-down Knuth multiplicative hashing constant). Multiplying
        # by a large odd number and truncating mixes the bits of i far
        # more thoroughly, so nearby request IDs no longer map to nearby
        # slots.
        return (i * 2654435761) % self.num_slots

    def _virtual_hash(self, i, j):
        # Original (Task 2 spec): (i*i + j*j + 2*j + 25) % num_slots --
        # same clustering problem, and virtual replicas of the same
        # server (varying j) ended up bunched together too.
        #
        # Modified for A-4: combine i and j into a single integer and run
        # it through the same multiplicative mixer, XORed together so
        # virtual copies of one server don't cluster with each other.
        combined = (i * 40503) ^ (j * 2654435761)
        return combined % self.num_slots

    def _find_free_slot(self, start):
        # If the computed slot is already taken, use quadratic probing
        # to find the next open slot instead of overwriting it
        slot = start % self.num_slots
        step = 1
        while slot in self.slot_to_server:
            slot = (start + step * step) % self.num_slots
            step += 1
        return slot

    def add_server(self, server_id, server_num=None):
        # Registers a new server by placing K virtual copies of it
        # around the ring.
        #
        # server_num is optional: if the caller doesn't supply one (or
        # supplies None), we assign the next number from a counter that
        # only ever increments, so it's never reused after a
        # remove_server call. This keeps virtual-hash slots stable and
        # unique per server across the container's whole lifetime, even
        # if servers are removed and re-added later.
        if server_num is None:
            server_num = self._next_server_num

        self._next_server_num = max(self._next_server_num, server_num + 1)
        self.server_to_num[server_id] = server_num

        slots = []
        for j in range(self.num_virtual):
            h = self._virtual_hash(server_num, j)
            slot = self._find_free_slot(h)
            self.slot_to_server[slot] = server_id
            slots.append(slot)
        self.server_to_slots[server_id] = slots

    def remove_server(self, server_id):
        # Frees up all slots belonging to this server so they can be
        # reused by future servers. Note: server_num is intentionally
        # NOT reclaimed here -- self._next_server_num keeps climbing so
        # a future server never collides with this one's old virtual
        # hash slots.
        for slot in self.server_to_slots.pop(server_id, []):
            del self.slot_to_server[slot]
        self.server_to_num.pop(server_id, None)

    def get_server(self, request_id):
        # Finds which server should handle a given request by hashing
        # its ID and walking clockwise until an occupied slot is found
        if not self.slot_to_server:
            return None
        start = self._request_hash(request_id)
        slot = start
        for _ in range(self.num_slots):
            if slot in self.slot_to_server:
                return self.slot_to_server[slot]
            slot = (slot + 1) % self.num_slots
        return None