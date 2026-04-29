class ReservationTable:
    ''''
The ReservationTable is a space-time occupancy index.

It answers four questions:

Is cell (x, y) free at time t?

Is edge (x1, y1) -> (x2, y2) free at time t?

Can I reserve a whole path?

Can I reserve a goal forever?
    '''

    def __init__(self):
        self.vertex_reservations = set()
        self.edge_reservations = set()
        self.static_cells = set()

    # -------- queries --------

    def is_cell_free(self, x, y, t):
        return (x, y) not in self.static_cells and (x, y, t) not in self.vertex_reservations

    def is_edge_free(self, x1, y1, x2, y2, t):
        # forbid both same-direction and opposite-direction conflicts
        return (
            (x1, y1, x2, y2, t) not in self.edge_reservations
            and (x2, y2, x1, y1, t) not in self.edge_reservations
        )

    # -------- reservations --------

    def reserve_path(self, path):
        """
        path: list of (x, y, t)
        """
        for i, (x, y, t) in enumerate(path):
            self.vertex_reservations.add((x, y, t))

            if i > 0:
                px, py, pt = path[i - 1]
                # edge from previous cell at time t-1
                self.edge_reservations.add((px, py, x, y, pt))

    def unreserve_path(self, path):
        """
        Remove reservations for a path.
        """
        for i, (x, y, t) in enumerate(path):
            self.vertex_reservations.discard((x, y, t))

            if i > 0:
                px, py, pt = path[i - 1]
                self.edge_reservations.discard((px, py, x, y, pt))

    def reserve_goal(self, x, y, start_time, horizon=1000):
        """
        Reserve goal cell forever (or up to a large horizon)
        """
        self.static_cells.add((x, y))

    def unreserve_goal(self, x, y, start_time, horizon=1000):
        """Remove a goal reservation (or up to a large horizon)."""
        self.static_cells.discard((x, y))