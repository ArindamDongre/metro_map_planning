#!/usr/bin/env python3

"""
Optimized SAT Encoder - Balances speed and correctness
Only expands bounding boxes for lines closest to popular cells
"""

import sys
import pickle
from parser import MetroProblem

class GeneralSATEncoder:
    def __init__(self, problem):
        self.problem = problem
        self.var_counter = 1
        self.clauses = []
        self.var_map = {}
        self.turn_vars_by_line = {k: [] for k in range(problem.K)}

        self.N, self.M, self.K = problem.N, problem.M, problem.K

    def new_var(self, description):
        if description not in self.var_map:
            self.var_map[description] = self.var_counter
            self.var_counter += 1
        return self.var_map[description]

    def add_clause(self, literals):
        if literals:
            self.clauses.append(literals)

    def at_most_one(self, variables):
        """O(n^2) AMO encoding"""
        n = len(variables)
        for i in range(n):
            for j in range(i + 1, n):
                self.add_clause([-variables[i], -variables[j]])

    def at_most_k_efficient(self, variables, k, line_index):
        """Sequential Counter Encoding"""
        n = len(variables)

        if k < 0:
            if n > 0:
                for v in variables:
                    self.add_clause([-v])
            return

        if k == 0:
            for v in variables:
                self.add_clause([-v])
            return

        if k >= n:
            return

        for i in range(1, n + 1):
            v_i = variables[i-1]
            for j in range(1, min(k + 1, i + 1)):
                s_i_j = self.new_var(('seq_count', line_index, i, j))

                if i > 1:
                    s_prev_i_j = self.var_map.get(('seq_count', line_index, i - 1, j))
                    if s_prev_i_j:
                        self.add_clause([-s_prev_i_j, s_i_j])

                if j == 1:
                    self.add_clause([-v_i, s_i_j])
                elif i > 1:
                    s_prev_i_j_minus_1 = self.var_map.get(('seq_count', line_index, i - 1, j - 1))
                    if s_prev_i_j_minus_1:
                        self.add_clause([-s_prev_i_j_minus_1, -v_i, s_i_j])

        if k + 1 <= n:
            s_i_k_plus_1 = None
            for i in range(1, n + 1):
                if k + 1 <= i:
                    s_i_k_plus_1 = self.new_var(('seq_count', line_index, i, k + 1))
                    v_i = variables[i-1]

                    if i > 1:
                        s_prev = self.var_map.get(('seq_count', line_index, i - 1, k + 1))
                        if s_prev:
                            self.add_clause([-s_prev, s_i_k_plus_1])

                    if i > 1:
                        s_prev_k = self.var_map.get(('seq_count', line_index, i - 1, k))
                        if s_prev_k:
                            self.add_clause([-s_prev_k, -v_i, s_i_k_plus_1])

            if s_i_k_plus_1 is not None:
                self.add_clause([-s_i_k_plus_1])

    def identify_lines_for_popular_cells(self):
        """
        SMART: Only expand buffers for lines closest to each popular cell
        This maintains correctness while keeping performance
        """
        if self.problem.scenario != 2 or self.problem.P == 0:
            return set()

        lines_to_expand = set()

        for px, py in self.problem.popular_cells:
            # Find the closest 3-5 lines to this popular cell
            distances = []
            for k in range(self.K):
                sx, sy = self.problem.lines[k][0]
                ex, ey = self.problem.lines[k][1]

                # Distance from popular cell to line's bounding box
                min_dist_start = abs(px - sx) + abs(py - sy)
                min_dist_end = abs(px - ex) + abs(py - ey)
                min_dist = min(min_dist_start, min_dist_end)

                distances.append((min_dist, k))

            # Sort by distance and take closest lines
            distances.sort()
            # Expand at least 3 closest lines, or more if they're close
            num_to_expand = 3
            for i in range(num_to_expand):
                if i < len(distances):
                    lines_to_expand.add(distances[i][1])

        return lines_to_expand

    def calculate_buffer(self, k, sx, sy, ex, ey, J, expand_for_popular):
        """
        Calculate buffer - only expand for lines designated to reach popular cells
        """
        manhattan = abs(ex - sx) + abs(ey - sy)

        # Base buffer
        base_buffer = J * 2 + 5

        # Additional buffer for long lines
        grid_diagonal = (self.N + self.M) / 2
        length_ratio = manhattan / grid_diagonal

        if length_ratio > 0.8:
            extra_buffer = int(manhattan * 0.15)
        elif length_ratio > 0.5:
            extra_buffer = int(manhattan * 0.10)
        else:
            extra_buffer = 0

        total_buffer = base_buffer + extra_buffer
        max_buffer = min(50, max(self.N // 3, self.M // 3, 5))
        buffer = min(total_buffer, max_buffer)

        # SMART: Only expand if this line is designated for popular cells
        if expand_for_popular and self.problem.scenario == 2 and self.problem.P > 0:
            for px, py in self.problem.popular_cells:
                min_buffer_x = max(abs(px - sx), abs(px - ex))
                min_buffer_y = max(abs(py - sy), abs(py - ey))
                needed_buffer = max(min_buffer_x, min_buffer_y)

                if needed_buffer > buffer:
                    buffer = min(needed_buffer, max(self.N, self.M))

        return buffer

    def create_variables(self):
        """
        Create variables with smart buffer expansion
        """
        print(f"Creating variables for {self.N}x{self.M} grid, {self.K} lines...")

        # Identify which lines should be expanded for popular cells
        lines_to_expand = self.identify_lines_for_popular_cells()

        if lines_to_expand:
            print(f"  Popular cells: {self.problem.popular_cells}")
            print(f"  Expanding buffers for {len(lines_to_expand)} lines closest to popular cells")

        self.line_bounds = {}
        total_cells = 0

        for k in range(self.K):
            sx, sy = self.problem.lines[k][0]
            ex, ey = self.problem.lines[k][1]

            # Calculate buffer - only expand if this line is in lines_to_expand
            expand = k in lines_to_expand
            buffer = self.calculate_buffer(k, sx, sy, ex, ey, self.problem.J, expand)

            min_x = max(0, min(sx, ex) - buffer)
            max_x = min(self.N - 1, max(sx, ex) + buffer)
            min_y = max(0, min(sy, ey) - buffer)
            max_y = min(self.M - 1, max(sy, ey) + buffer)

            self.line_bounds[k] = (min_x, max_x, min_y, max_y)

            cells_in_bbox = (max_x - min_x + 1) * (max_y - min_y + 1)
            total_cells += cells_in_bbox

            # Create variables within bounding box
            for x in range(min_x, max_x + 1):
                for y in range(min_y, max_y + 1):
                    self.new_var(('cell', k, x, y))
                    for d in range(4):
                        self.new_var(('dir', k, x, y, d))
                    self.new_var(('turn', k, x, y))

        print(f"Created {self.var_counter - 1} variables")
        print(f"Average cells per line: {total_cells // self.K}")

    def in_bounds(self, k, x, y):
        """Check if cell (x,y) is in the bounding box for line k"""
        min_x, max_x, min_y, max_y = self.line_bounds[k]
        return min_x <= x <= max_x and min_y <= y <= max_y

    def encode_constraints(self):
        print(f"Encoding constraints for {self.K} lines...")

        for k in range(self.K):
            sx, sy = self.problem.lines[k][0]
            ex, ey = self.problem.lines[k][1]
            J = self.problem.J

            if k % 10 == 0 or self.K <= 5:
                print(f"  Processing line {k}/{self.K}...")

            self.encode_start_end(k, sx, sy, ex, ey)
            self.encode_path_connectivity(k, sx, sy, ex, ey)
            self.encode_turn_constraints(k, sx, sy, ex, ey, J)
            self.encode_anti_parallel_directions(k)

        self.encode_no_overlap()

        if self.problem.scenario == 2 and self.problem.P > 0:
            self.encode_popular_cells()

    def encode_start_end(self, k, sx, sy, ex, ey):
        start_var = self.var_map.get(('cell', k, sx, sy))
        end_var = self.var_map.get(('cell', k, ex, ey))
        if start_var:
            self.add_clause([start_var])
        if end_var:
            self.add_clause([end_var])

    def encode_path_connectivity(self, k, sx, sy, ex, ey):
        """Only process cells within bounding box"""
        min_x, max_x, min_y, max_y = self.line_bounds[k]

        for x in range(min_x, max_x + 1):
            for y in range(min_y, max_y + 1):
                cell_var = self.var_map.get(('cell', k, x, y))
                if not cell_var:
                    continue

                outgoing, incoming = [], []

                # Outgoing directions
                if x + 1 < self.N and self.in_bounds(k, x + 1, y):
                    dir_var = self.var_map.get(('dir', k, x, y, 0))
                    if dir_var:
                        outgoing.append(dir_var)

                if x - 1 >= 0 and self.in_bounds(k, x - 1, y):
                    dir_var = self.var_map.get(('dir', k, x, y, 1))
                    if dir_var:
                        outgoing.append(dir_var)

                if y + 1 < self.M and self.in_bounds(k, x, y + 1):
                    dir_var = self.var_map.get(('dir', k, x, y, 2))
                    if dir_var:
                        outgoing.append(dir_var)

                if y - 1 >= 0 and self.in_bounds(k, x, y - 1):
                    dir_var = self.var_map.get(('dir', k, x, y, 3))
                    if dir_var:
                        outgoing.append(dir_var)

                # Incoming directions
                if x - 1 >= 0 and self.in_bounds(k, x - 1, y):
                    dir_var = self.var_map.get(('dir', k, x - 1, y, 0))
                    if dir_var:
                        incoming.append(dir_var)

                if x + 1 < self.N and self.in_bounds(k, x + 1, y):
                    dir_var = self.var_map.get(('dir', k, x + 1, y, 1))
                    if dir_var:
                        incoming.append(dir_var)

                if y - 1 >= 0 and self.in_bounds(k, x, y - 1):
                    dir_var = self.var_map.get(('dir', k, x, y - 1, 2))
                    if dir_var:
                        incoming.append(dir_var)

                if y + 1 < self.M and self.in_bounds(k, x, y + 1):
                    dir_var = self.var_map.get(('dir', k, x, y + 1, 3))
                    if dir_var:
                        incoming.append(dir_var)

                # Flow constraints
                if (x, y) == (sx, sy):
                    if outgoing:
                        self.add_clause([-cell_var] + outgoing)
                        self.at_most_one(outgoing)
                    for in_dir_var in incoming:
                        self.add_clause([-in_dir_var])

                elif (x, y) == (ex, ey):
                    if incoming:
                        self.add_clause([-cell_var] + incoming)
                        self.at_most_one(incoming)
                    for out_dir_var in outgoing:
                        self.add_clause([-out_dir_var])

                else:
                    if incoming:
                        self.add_clause([-cell_var] + incoming)
                    if outgoing:
                        self.add_clause([-cell_var] + outgoing)
                    if incoming:
                        self.at_most_one(incoming)
                    if outgoing:
                        self.at_most_one(outgoing)

                # Link directions to cells
                for d_var in outgoing + incoming:
                    self.add_clause([cell_var, -d_var])

                self.encode_direction_implications(k, x, y)

    def encode_direction_implications(self, k, x, y):
        # Right
        if x + 1 < self.N and self.in_bounds(k, x + 1, y):
            dir_var = self.var_map.get(('dir', k, x, y, 0))
            next_cell = self.var_map.get(('cell', k, x + 1, y))
            if dir_var and next_cell:
                self.add_clause([-dir_var, next_cell])

        # Left
        if x - 1 >= 0 and self.in_bounds(k, x - 1, y):
            dir_var = self.var_map.get(('dir', k, x, y, 1))
            next_cell = self.var_map.get(('cell', k, x - 1, y))
            if dir_var and next_cell:
                self.add_clause([-dir_var, next_cell])

        # Down
        if y + 1 < self.M and self.in_bounds(k, x, y + 1):
            dir_var = self.var_map.get(('dir', k, x, y, 2))
            next_cell = self.var_map.get(('cell', k, x, y + 1))
            if dir_var and next_cell:
                self.add_clause([-dir_var, next_cell])

        # Up
        if y - 1 >= 0 and self.in_bounds(k, x, y - 1):
            dir_var = self.var_map.get(('dir', k, x, y, 3))
            next_cell = self.var_map.get(('cell', k, x, y - 1))
            if dir_var and next_cell:
                self.add_clause([-dir_var, next_cell])

    def encode_turn_constraints(self, k, sx, sy, ex, ey, J):
        """Only process cells within bounding box"""
        min_x, max_x, min_y, max_y = self.line_bounds[k]

        for x in range(min_x, max_x + 1):
            for y in range(min_y, max_y + 1):
                turn_var = self.var_map.get(('turn', k, x, y))
                if not turn_var:
                    continue

                cell_var = self.var_map.get(('cell', k, x, y))

                if (x, y) == (sx, sy) or (x, y) == (ex, ey):
                    self.add_clause([-turn_var])
                    continue

                if cell_var:
                    self.add_clause([-turn_var, cell_var])

                # Get incoming and outgoing directions
                in_dirs, out_dirs = [], []

                if x - 1 >= 0 and self.in_bounds(k, x - 1, y):
                    v = self.var_map.get(('dir', k, x - 1, y, 0))
                    if v: in_dirs.append((0, v))

                if x + 1 < self.N and self.in_bounds(k, x + 1, y):
                    v = self.var_map.get(('dir', k, x + 1, y, 1))
                    if v: in_dirs.append((1, v))

                if y - 1 >= 0 and self.in_bounds(k, x, y - 1):
                    v = self.var_map.get(('dir', k, x, y - 1, 2))
                    if v: in_dirs.append((2, v))

                if y + 1 < self.M and self.in_bounds(k, x, y + 1):
                    v = self.var_map.get(('dir', k, x, y + 1, 3))
                    if v: in_dirs.append((3, v))

                if x + 1 < self.N and self.in_bounds(k, x + 1, y):
                    v = self.var_map.get(('dir', k, x, y, 0))
                    if v: out_dirs.append((0, v))

                if x - 1 >= 0 and self.in_bounds(k, x - 1, y):
                    v = self.var_map.get(('dir', k, x, y, 1))
                    if v: out_dirs.append((1, v))

                if y + 1 < self.M and self.in_bounds(k, x, y + 1):
                    v = self.var_map.get(('dir', k, x, y, 2))
                    if v: out_dirs.append((2, v))

                if y - 1 >= 0 and self.in_bounds(k, x, y - 1):
                    v = self.var_map.get(('dir', k, x, y, 3))
                    if v: out_dirs.append((3, v))

                # Turn definitions
                for (din, idir_var) in in_dirs:
                    for (dout, odir_var) in out_dirs:
                        if din != dout:
                            self.add_clause([-idir_var, -odir_var, turn_var])
                        else:
                            self.add_clause([-idir_var, -odir_var, -turn_var])

                self.turn_vars_by_line[k].append(turn_var)

        # Turn limit
        turn_vars_for_line = self.turn_vars_by_line[k]
        self.at_most_k_efficient(turn_vars_for_line, J, k)

    def encode_anti_parallel_directions(self, k):
        """Only process cells within bounding box"""
        min_x, max_x, min_y, max_y = self.line_bounds[k]

        for x in range(min_x, max_x + 1):
            for y in range(min_y, max_y + 1):
                if x + 1 < self.N and self.in_bounds(k, x + 1, y):
                    dir_out = self.var_map.get(('dir', k, x, y, 0))
                    dir_in = self.var_map.get(('dir', k, x + 1, y, 1))
                    if dir_out and dir_in:
                        self.add_clause([-dir_out, -dir_in])

                if x - 1 >= 0 and self.in_bounds(k, x - 1, y):
                    dir_out = self.var_map.get(('dir', k, x, y, 1))
                    dir_in = self.var_map.get(('dir', k, x - 1, y, 0))
                    if dir_out and dir_in:
                        self.add_clause([-dir_out, -dir_in])

                if y + 1 < self.M and self.in_bounds(k, x, y + 1):
                    dir_out = self.var_map.get(('dir', k, x, y, 2))
                    dir_in = self.var_map.get(('dir', k, x, y + 1, 3))
                    if dir_out and dir_in:
                        self.add_clause([-dir_out, -dir_in])

                if y - 1 >= 0 and self.in_bounds(k, x, y - 1):
                    dir_out = self.var_map.get(('dir', k, x, y, 3))
                    dir_in = self.var_map.get(('dir', k, x, y - 1, 2))
                    if dir_out and dir_in:
                        self.add_clause([-dir_out, -dir_in])

    def encode_no_overlap(self):
        """Only check overlaps where bounding boxes intersect"""
        print("Encoding non-collision constraints...")

        # Build set of cells in any line's bounding box
        cells_to_check = set()
        for k in range(self.K):
            min_x, max_x, min_y, max_y = self.line_bounds[k]
            for x in range(min_x, max_x + 1):
                for y in range(min_y, max_y + 1):
                    cells_to_check.add((x, y))

        for x, y in cells_to_check:
            vars_in_cell = []
            for k in range(self.K):
                v = self.var_map.get(('cell', k, x, y))
                if v:
                    vars_in_cell.append(v)

            if len(vars_in_cell) > 1:
                self.at_most_one(vars_in_cell)

        print("  Added cell non-overlap constraints")

    def encode_popular_cells(self):
        """
        CORRECT: Ensures at least one line passes through each popular cell
        """
        print(f"Encoding popular cell constraints for {self.problem.P} cells...")

        for x, y in self.problem.popular_cells:
            vars_in_cell = []
            for k in range(self.K):
                v = self.var_map.get(('cell', k, x, y))
                if v:
                    vars_in_cell.append(v)

            if vars_in_cell:
                self.add_clause(vars_in_cell)
                print(f"  Cell ({x},{y}): {len(vars_in_cell)} lines can reach it")
            else:
                # Popular cell unreachable - make UNSAT
                print(f"  WARNING: Cell ({x},{y}) is unreachable by all lines!")
                print(f"  Adding FALSE clause to make problem UNSAT")
                self.add_clause([])

        print("  Added popular cell constraints")

    def write_dimacs(self, filename):
        with open(filename, 'w') as f:
            num_vars = self.var_counter - 1
            num_clauses = len(self.clauses)
            f.write(f"p cnf {num_vars} {num_clauses}\n")
            for clause in self.clauses:
                f.write(' '.join(map(str, clause)) + ' 0\n')

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: encoder.py <base>", file=sys.stderr)
        sys.exit(1)

    base = sys.argv[1]
    input_file = base + ".city"
    output_file = base + ".satinput"
    varmap_file = base + ".varmap"

    try:
        problem = MetroProblem(input_file)
        print(f"Loaded: {problem}")

        encoder = GeneralSATEncoder(problem)
        encoder.create_variables()
        encoder.encode_constraints()
        encoder.write_dimacs(output_file)

        with open(varmap_file, 'wb') as f:
            pickle.dump(encoder.var_map, f)

        print(f"\nSuccess! Created {output_file}")
        print(f"Variables: {encoder.var_counter-1}, Clauses: {len(encoder.clauses)}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
