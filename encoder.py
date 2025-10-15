#!/usr/bin/env python3

"""
Optimized SAT Encoder for Metro Planning
- Adaptive bounding boxes with intelligent expansion
- Handles both small tricky cases and large test cases
- Better heuristics for difficult instances
"""

import sys
import pickle
from parser import MetroProblem

class OptimizedSATEncoder:
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
        """Sequential Counter Encoding for at-most-k constraint"""
        n = len(variables)
        if k < 0 or (k == 0 and n > 0):
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
            for i in range(k + 1, n + 1):
                s_i_k_plus_1 = self.new_var(('seq_count', line_index, i, k + 1))
                v_i = variables[i-1]
                if i > k + 1:
                    s_prev = self.var_map.get(('seq_count', line_index, i - 1, k + 1))
                    if s_prev:
                        self.add_clause([-s_prev, s_i_k_plus_1])
                s_prev_k = self.var_map.get(('seq_count', line_index, i - 1, k))
                if s_prev_k:
                    self.add_clause([-s_prev_k, -v_i, s_i_k_plus_1])
            
            final_s = self.var_map.get(('seq_count', line_index, n, k + 1))
            if final_s:
                self.add_clause([-final_s])

    def calculate_adaptive_buffer(self, sx, sy, ex, ey, J, popular_cells, line_idx):
        """
        Intelligent buffer calculation:
        1. Ensures minimum path feasibility
        2. Accounts for turn requirements
        3. Includes popular cells when needed
        4. Scales with grid size and problem difficulty
        """
        manhattan = abs(ex - sx) + abs(ey - sy)
        
        # Minimum turns needed for this line
        if sx == ex or sy == ey:
            min_turns_needed = 0
        else:
            min_turns_needed = 1
        
        # Base buffer depends on turns needed vs allowed
        turn_slack = J - min_turns_needed
        base_buffer = min(3 + turn_slack * 2, J * 3)
        
        # For small grids, be generous
        if self.N <= 10 or self.M <= 10:
            grid_factor = max(self.N, self.M) // 3
            base_buffer = max(base_buffer, grid_factor)
        
        # For long lines relative to grid, add proportional buffer
        grid_span = max(self.N, self.M)
        if manhattan > grid_span * 0.6:
            base_buffer = max(base_buffer, int(manhattan * 0.12))
        
        # Cap at reasonable maximum to prevent explosion
        max_buffer = min(60, max(self.N // 3, self.M // 3))
        buffer = min(base_buffer, max_buffer)
        
        # CRITICAL: Ensure popular cells are reachable
        if popular_cells:
            for px, py in popular_cells:
                # Check if this popular cell is far from line's path
                min_x_line = min(sx, ex)
                max_x_line = max(sx, ex)
                min_y_line = min(sy, ey)
                max_y_line = max(sy, ey)
                
                dist_x = max(0, min_x_line - px, px - max_x_line)
                dist_y = max(0, min_y_line - py, py - max_y_line)
                needed = max(dist_x, dist_y)
                
                # Expand buffer if this line needs to reach this popular cell
                # Only expand if it's reasonable for this line to cover it
                if needed > buffer and needed < max(self.N, self.M) // 2:
                    buffer = min(needed + 3, max_buffer)
        
        return buffer

    def create_variables(self):
        """Create variables with adaptive bounding boxes"""
        print(f"Creating variables for {self.N}x{self.M} grid, {self.K} lines...")
        
        popular_cells = None
        if self.problem.scenario == 2 and self.problem.P > 0:
            popular_cells = self.problem.popular_cells
            print(f"  Popular cells: {popular_cells}")
        
        self.line_bounds = {}
        total_cells = 0
        
        for k in range(self.K):
            sx, sy = self.problem.lines[k][0]
            ex, ey = self.problem.lines[k][1]
            
            buffer = self.calculate_adaptive_buffer(sx, sy, ex, ey, 
                                                    self.problem.J, popular_cells, k)
            
            min_x = max(0, min(sx, ex) - buffer)
            max_x = min(self.N - 1, max(sx, ex) + buffer)
            min_y = max(0, min(sy, ey) - buffer)
            max_y = min(self.M - 1, max(sy, ey) + buffer)
            
            self.line_bounds[k] = (min_x, max_x, min_y, max_y)
            cells_in_bbox = (max_x - min_x + 1) * (max_y - min_y + 1)
            total_cells += cells_in_bbox
            
            # Create variables
            for x in range(min_x, max_x + 1):
                for y in range(min_y, max_y + 1):
                    self.new_var(('cell', k, x, y))
                    for d in range(4):
                        self.new_var(('dir', k, x, y, d))
                    self.new_var(('turn', k, x, y))
        
        print(f"Created {self.var_counter - 1} variables")
        print(f"Average cells per line: {total_cells // max(1, self.K)}")

    def in_bounds(self, k, x, y):
        min_x, max_x, min_y, max_y = self.line_bounds[k]
        return min_x <= x <= max_x and min_y <= y <= max_y

    def encode_constraints(self):
        print(f"Encoding constraints...")
        
        for k in range(self.K):
            if self.K > 20 and k % 5 == 0:
                print(f"  Processing line {k}/{self.K}...")
            
            sx, sy = self.problem.lines[k][0]
            ex, ey = self.problem.lines[k][1]
            
            self.encode_start_end(k, sx, sy, ex, ey)
            self.encode_path_connectivity(k, sx, sy, ex, ey)
            self.encode_turn_constraints(k, sx, sy, ex, ey, self.problem.J)
            self.encode_anti_parallel(k)
        
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
        min_x, max_x, min_y, max_y = self.line_bounds[k]
        
        for x in range(min_x, max_x + 1):
            for y in range(min_y, max_y + 1):
                cell_var = self.var_map.get(('cell', k, x, y))
                if not cell_var:
                    continue
                
                # Collect outgoing and incoming directions
                outgoing = []
                if x + 1 < self.N and self.in_bounds(k, x + 1, y):
                    v = self.var_map.get(('dir', k, x, y, 0))
                    if v: outgoing.append(v)
                if x - 1 >= 0 and self.in_bounds(k, x - 1, y):
                    v = self.var_map.get(('dir', k, x, y, 1))
                    if v: outgoing.append(v)
                if y + 1 < self.M and self.in_bounds(k, x, y + 1):
                    v = self.var_map.get(('dir', k, x, y, 2))
                    if v: outgoing.append(v)
                if y - 1 >= 0 and self.in_bounds(k, x, y - 1):
                    v = self.var_map.get(('dir', k, x, y, 3))
                    if v: outgoing.append(v)
                
                incoming = []
                if x - 1 >= 0 and self.in_bounds(k, x - 1, y):
                    v = self.var_map.get(('dir', k, x - 1, y, 0))
                    if v: incoming.append(v)
                if x + 1 < self.N and self.in_bounds(k, x + 1, y):
                    v = self.var_map.get(('dir', k, x + 1, y, 1))
                    if v: incoming.append(v)
                if y - 1 >= 0 and self.in_bounds(k, x, y - 1):
                    v = self.var_map.get(('dir', k, x, y - 1, 2))
                    if v: incoming.append(v)
                if y + 1 < self.M and self.in_bounds(k, x, y + 1):
                    v = self.var_map.get(('dir', k, x, y + 1, 3))
                    if v: incoming.append(v)
                
                # Flow constraints based on position
                if (x, y) == (sx, sy):
                    if outgoing:
                        self.add_clause([-cell_var] + outgoing)
                        self.at_most_one(outgoing)
                    for v in incoming:
                        self.add_clause([-v])
                elif (x, y) == (ex, ey):
                    if incoming:
                        self.add_clause([-cell_var] + incoming)
                        self.at_most_one(incoming)
                    for v in outgoing:
                        self.add_clause([-v])
                else:
                    if incoming:
                        self.add_clause([-cell_var] + incoming)
                    if outgoing:
                        self.add_clause([-cell_var] + outgoing)
                    if incoming:
                        self.at_most_one(incoming)
                    if outgoing:
                        self.at_most_one(outgoing)
                
                # Direction implies next cell
                for d_var in outgoing + incoming:
                    self.add_clause([cell_var, -d_var])
                
                self.encode_direction_implications(k, x, y)

    def encode_direction_implications(self, k, x, y):
        directions = [
            (0, 1, 0),   # Right
            (1, -1, 0),  # Left
            (2, 0, 1),   # Down
            (3, 0, -1)   # Up
        ]
        
        for d, dx, dy in directions:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.N and 0 <= ny < self.M and self.in_bounds(k, nx, ny):
                dir_var = self.var_map.get(('dir', k, x, y, d))
                next_cell = self.var_map.get(('cell', k, nx, ny))
                if dir_var and next_cell:
                    self.add_clause([-dir_var, next_cell])

    def encode_turn_constraints(self, k, sx, sy, ex, ey, J):
        min_x, max_x, min_y, max_y = self.line_bounds[k]
        
        for x in range(min_x, max_x + 1):
            for y in range(min_y, max_y + 1):
                turn_var = self.var_map.get(('turn', k, x, y))
                if not turn_var:
                    continue
                
                if (x, y) == (sx, sy) or (x, y) == (ex, ey):
                    self.add_clause([-turn_var])
                    continue
                
                cell_var = self.var_map.get(('cell', k, x, y))
                if cell_var:
                    self.add_clause([-turn_var, cell_var])
                
                # Define turns: incoming dir != outgoing dir
                in_dirs = []
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
                
                out_dirs = []
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
                
                for (din, ivar) in in_dirs:
                    for (dout, ovar) in out_dirs:
                        if din != dout:
                            self.add_clause([-ivar, -ovar, turn_var])
                        else:
                            self.add_clause([-ivar, -ovar, -turn_var])
                
                self.turn_vars_by_line[k].append(turn_var)
        
        self.at_most_k_efficient(self.turn_vars_by_line[k], J, k)

    def encode_anti_parallel(self, k):
        min_x, max_x, min_y, max_y = self.line_bounds[k]
        
        for x in range(min_x, max_x + 1):
            for y in range(min_y, max_y + 1):
                # Horizontal
                if x + 1 < self.N and self.in_bounds(k, x + 1, y):
                    r = self.var_map.get(('dir', k, x, y, 0))
                    l = self.var_map.get(('dir', k, x + 1, y, 1))
                    if r and l:
                        self.add_clause([-r, -l])
                
                # Vertical
                if y + 1 < self.M and self.in_bounds(k, x, y + 1):
                    d = self.var_map.get(('dir', k, x, y, 2))
                    u = self.var_map.get(('dir', k, x, y + 1, 3))
                    if d and u:
                        self.add_clause([-d, -u])

    def encode_no_overlap(self):
        print("Encoding non-overlap constraints...")
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

    def encode_popular_cells(self):
        print(f"Encoding popular cell constraints...")
        for x, y in self.problem.popular_cells:
            vars_in_cell = []
            for k in range(self.K):
                v = self.var_map.get(('cell', k, x, y))
                if v:
                    vars_in_cell.append(v)
            
            if vars_in_cell:
                self.add_clause(vars_in_cell)
            else:
                print(f"  WARNING: Popular cell ({x},{y}) unreachable - adding UNSAT clause")
                self.add_clause([])

    def write_dimacs(self, filename):
        with open(filename, 'w') as f:
            f.write(f"p cnf {self.var_counter - 1} {len(self.clauses)}\n")
            for clause in self.clauses:
                f.write(' '.join(map(str, clause)) + ' 0\n')

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: encoder.py <base>", file=sys.stderr)
        sys.exit(1)

    base = sys.argv[1]
    problem = MetroProblem(base + ".city")
    print(f"Loaded: {problem}")
    
    encoder = OptimizedSATEncoder(problem)
    encoder.create_variables()
    encoder.encode_constraints()
    encoder.write_dimacs(base + ".satinput")
    
    with open(base + ".varmap", 'wb') as f:
        pickle.dump(encoder.var_map, f)
    
    print(f"\nSuccess! Variables: {encoder.var_counter-1}, Clauses: {len(encoder.clauses)}")