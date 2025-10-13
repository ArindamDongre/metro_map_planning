#!/usr/bin/env python3

"""
General SAT Encoder for Metro Planning (Phase 3: Multiple Lines, strict turn counting)
Refined for Scenario II and efficiency
"""

import sys
import pickle
# Assuming parser.py is available for import
from parser import MetroProblem
# import itertools # Not needed as naive at_most_k is removed

class GeneralSATEncoder:
    def __init__(self, problem):
        self.problem = problem
        self.var_counter = 1
        self.clauses = []
        self.var_map = {}
        # Stores (var_id, k) for turn variables to easily look up line k
        self.turn_vars_by_line = {k: [] for k in range(problem.K)} 

    def new_var(self, description):
        if description not in self.var_map:
            self.var_map[description] = self.var_counter
            self.var_counter += 1
        return self.var_map[description]

    def add_clause(self, literals):
        if literals:
            self.clauses.append(literals)

    # Naive At-Most-One (AMO) encoding (O(n^2) clauses) - acceptable for small sets
    def at_most_one(self, variables):
        for i in range(len(variables)):
            for j in range(i + 1, len(variables)):
                self.add_clause([-variables[i], -variables[j]])

    # EFFICIENT At-Most-K (AMK) using Sequential Counter Encoding (O(n*k) clauses)
    def at_most_k_efficient(self, variables, k, line_index):
        n = len(variables)
        if k < 0:
            if n > 0:
                 for v in variables:
                     self.add_clause([-v])
            return

        if k >= n:
            return

        # Pass 1: Define s_i_j for 1 <= j <= k
        for i in range(1, n + 1):
            v_i = variables[i-1] # The i-th turn variable (0-indexed)

            for j in range(1, k + 1):
                s_i_j = self.new_var(('seq_count', line_index, i, j))

                # 1. Carry over: s_{i-1, j} -> s_{i, j} (Need i > 1)
                # (-s_{i-1, j} OR s_{i, j})
                if i > 1:
                    s_prev_i_j = self.var_map[('seq_count', line_index, i - 1, j)]
                    self.add_clause([-s_prev_i_j, s_i_j])

                # 2. Increment: (s_{i-1, j-1} AND v_i) -> s_{i, j}
                # CNF: (-s_{i-1, j-1} OR -v_i OR s_{i, j})
                
                # Case 1: j=1. Rule simplifies to (v_i) -> s_{i, 1}. (s_{i-1, 0} is implicitly True)
                if j == 1:
                    self.add_clause([-v_i, s_i_j])
                
                # Case 2: j>1 and i>1. Normal case. (s_{i-1, j-1} must exist)
                elif i > 1:
                    s_prev_i_j_minus_1 = self.var_map[('seq_count', line_index, i - 1, j - 1)]
                    self.add_clause([-s_prev_i_j_minus_1, -v_i, s_i_j])
                
                # Case 3: j>1 and i=1. (s_{0, j-1} is implicitly False) - Rule is trivially satisfied. Skip encoding.


        # Final Constraint: s_{n, k+1} must be FALSE.
        # Propagate the k+1 column up to s_{n, k+1}.
        if k + 1 <= n:
            s_i_k_plus_1 = None # Initialize to hold the last variable s_{n, k+1}

            for i in range(1, n + 1):
                s_i_k_plus_1 = self.new_var(('seq_count', line_index, i, k + 1))
                v_i = variables[i-1]

                # 1. Carry over: s_{i-1, k+1} -> s_{i, k+1}
                if i > 1:
                    s_prev_i_k_plus_1 = self.var_map[('seq_count', line_index, i - 1, k + 1)]
                    self.add_clause([-s_prev_i_k_plus_1, s_i_k_plus_1])
                
                # 2. Increment: (s_{i-1, k} AND v_i) -> s_{i, k+1}
                # CNF: (-s_{i-1, k} OR -v_i OR s_{i, k+1})
                if i > 1:
                    # s_{i-1, k} was defined in Pass 1 (since k >= 1)
                    s_prev_i_k = self.var_map[('seq_count', line_index, i - 1, k)] 
                    self.add_clause([-s_prev_i_k, -v_i, s_i_k_plus_1])
                
                # Case i=1 is skipped (s_{0, k} is implicitly False)

            # The overall constraint: The last s_{n, k+1} variable must be False
            if s_i_k_plus_1 is not None:
                self.add_clause([-s_i_k_plus_1])


    def create_variables(self):
        N, M, K = self.problem.N, self.problem.M, self.problem.K
        print(f"Creating variables for {N}x{M} grid, {K} lines...")
        for k in range(K):
            for x in range(N):
                for y in range(M):
                    # ('cell', k, x, y): Is cell (x, y) part of line k?
                    self.new_var(('cell', k, x, y)) 
                    # ('dir', k, x, y, d): Does line k exit cell (x, y) in direction d?
                    for d in range(4):  # Directions: Right=0, Left=1, Down=2, Up=3
                        self.new_var(('dir', k, x, y, d))
                    # ('turn', k, x, y): Does line k make a turn at cell (x, y)?
                    self.new_var(('turn', k, x, y)) 
        print(f"Created {self.var_counter - 1} variables")

    def encode_constraints(self):
        N, M, K = self.problem.N, self.problem.M, self.problem.K
        print(f"Encoding constraints for {K} lines...")
        for k in range(K):
            sx, sy = self.problem.lines[k][0]
            ex, ey = self.problem.lines[k][1]
            J = self.problem.J # Max turns
            print(f"Line {k}: ({sx},{sy}) -> ({ex},{ey}), max turns J={J}")
            self.encode_start_end(k, sx, sy, ex, ey)
            self.encode_path_connectivity(k, sx, sy, ex, ey)
            self.encode_turn_constraints(k, sx, sy, ex, ey, J)
            self.encode_anti_parallel_directions(k) # Added anti-parallel constraint
            
        self.encode_no_overlap() # At most 1 line per cell
        
        if self.problem.scenario == 2 and self.problem.P > 0:
            self.encode_popular_cells() # Every popular cell must be covered


    def encode_start_end(self, k, sx, sy, ex, ey):
        # The start and end cells MUST be part of line k
        start_var = self.var_map[('cell', k, sx, sy)]
        self.add_clause([start_var])
        end_var = self.var_map[('cell', k, ex, ey)]
        self.add_clause([end_var])
        print(f" Added start/end constraints for line {k}")

    def encode_path_connectivity(self, k, sx, sy, ex, ey):
        N, M = self.problem.N, self.problem.M
        print(f" Encoding path connectivity for line {k}...")
        for x in range(N):
            for y in range(M):
                cell_var = self.var_map[('cell', k, x, y)]
                outgoing, incoming = [], []
                
                # Outgoing directions from (x, y)
                if x + 1 < N: # Right (0)
                    outgoing.append(self.var_map[('dir', k, x, y, 0)])
                if x - 1 >= 0: # Left (1)
                    outgoing.append(self.var_map[('dir', k, x, y, 1)])
                if y + 1 < M: # Down (2)
                    outgoing.append(self.var_map[('dir', k, x, y, 2)])
                if y - 1 >= 0: # Up (3)
                    outgoing.append(self.var_map[('dir', k, x, y, 3)])

                # Incoming directions to (x, y)
                if x - 1 >= 0: # From Left (Right dir from x-1)
                    incoming.append(self.var_map[('dir', k, x - 1, y, 0)])
                if x + 1 < N: # From Right (Left dir from x+1)
                    incoming.append(self.var_map[('dir', k, x + 1, y, 1)])
                if y - 1 >= 0: # From Up (Down dir from y-1)
                    incoming.append(self.var_map[('dir', k, x, y - 1, 2)])
                if y + 1 < M: # From Down (Up dir from y+1)
                    incoming.append(self.var_map[('dir', k, x, y + 1, 3)])

                # 1. Flow for Start/End/Internal Cells
                if (x, y) == (sx, sy):
                    # Start: Must have exactly one outgoing and zero incoming (if used)
                    if outgoing:
                        self.add_clause([-cell_var] + outgoing) # cell -> at least one outgoing
                        self.at_most_one(outgoing) # at most one outgoing
                    for in_dir_var in incoming:
                        self.add_clause([-in_dir_var])  # start cell no incoming
                elif (x, y) == (ex, ey):
                    # End: Must have exactly one incoming and zero outgoing (if used)
                    if incoming:
                        self.add_clause([-cell_var] + incoming) # cell -> at least one incoming
                        self.at_most_one(incoming) # at most one incoming
                    for out_dir_var in outgoing:
                        self.add_clause([-out_dir_var])  # end cell no outgoing
                else:
                    # Internal: Must have exactly one incoming AND exactly one outgoing (if used)
                    if incoming:
                        self.add_clause([-cell_var] + incoming) # cell -> at least one incoming
                    if outgoing:
                        self.add_clause([-cell_var] + outgoing) # cell -> at least one outgoing
                    self.at_most_one(incoming) # at most one incoming
                    self.at_most_one(outgoing) # at most one outgoing

                # 2. Link cell to direction variables: Direction implies cell
                # If any direction variable is true, the current cell MUST be true
                for d_var in outgoing + incoming:
                    self.add_clause([cell_var, -d_var]) # (-d_var OR cell_var) == (d_var -> cell_var)

                # 3. Direction variables imply next cell is true
                self.encode_direction_implications(k, x, y)

        print(f" Added connectivity for all cells for line {k}")

    def encode_direction_implications(self, k, x, y):
        N, M = self.problem.N, self.problem.M
        # Right (0)
        if x + 1 < N:
            dir_var = self.var_map[('dir', k, x, y, 0)]
            next_cell = self.var_map[('cell', k, x + 1, y)]
            self.add_clause([-dir_var, next_cell])
        # Left (1)
        if x - 1 >= 0:
            dir_var = self.var_map[('dir', k, x, y, 1)]
            next_cell = self.var_map[('cell', k, x - 1, y)]
            self.add_clause([-dir_var, next_cell])
        # Down (2)
        if y + 1 < M:
            dir_var = self.var_map[('dir', k, x, y, 2)]
            next_cell = self.var_map[('cell', k, x, y + 1)]
            self.add_clause([-dir_var, next_cell])
        # Up (3)
        if y - 1 >= 0:
            dir_var = self.var_map[('dir', k, x, y, 3)]
            next_cell = self.var_map[('cell', k, x, y - 1)]
            self.add_clause([-dir_var, next_cell])

    def encode_turn_constraints(self, k, sx, sy, ex, ey, J):
        N, M = self.problem.N, self.problem.M
        # Directions are 0:Right, 1:Left, 2:Down, 3:Up

        for x in range(N):
            for y in range(M):
                turn_var = self.var_map[('turn', k, x, y)]
                cell_var = self.var_map[('cell', k, x, y)]

                # Endpoints cannot be turns
                if (x, y) == (sx, sy) or (x, y) == (ex, ey):
                    self.add_clause([-turn_var])
                    continue

                # turn_var -> cell_var (optional, but good)
                self.add_clause([-turn_var, cell_var])
                
                # --- Define Turn ---
                # turn_var is true IFF incoming direction is NOT the same as outgoing direction
                
                # 1. Get incoming and outgoing direction variables (same as in connectivity)
                in_dirs, out_dirs = [], []
                # In from Left (Dir Right) -> Incoming dir is Right (0)
                if x - 1 >= 0: in_dirs.append((0, self.var_map[('dir', k, x - 1, y, 0)])) 
                # In from Right (Dir Left) -> Incoming dir is Left (1)
                if x + 1 < N: in_dirs.append((1, self.var_map[('dir', k, x + 1, y, 1)])) 
                # In from Up (Dir Down) -> Incoming dir is Down (2)
                if y - 1 >= 0: in_dirs.append((2, self.var_map[('dir', k, x, y - 1, 2)])) 
                # In from Down (Dir Up) -> Incoming dir is Up (3)
                if y + 1 < M: in_dirs.append((3, self.var_map[('dir', k, x, y + 1, 3)])) 
                
                if x + 1 < N: out_dirs.append((0, self.var_map[('dir', k, x, y, 0)])) # Out Right (0)
                if x - 1 >= 0: out_dirs.append((1, self.var_map[('dir', k, x, y, 1)])) # Out Left (1)
                if y + 1 < M: out_dirs.append((2, self.var_map[('dir', k, x, y, 2)])) # Out Down (2)
                if y - 1 >= 0: out_dirs.append((3, self.var_map[('dir', k, x, y, 3)])) # Out Up (3)
                
                # 2. Implication: (in_dir & out_dir) -> turn_var, if directions are DIFFERENT (Turn)
                # CNF: (-idir_var OR -odir_var OR turn_var)
                for (din, idir_var) in in_dirs:
                    for (dout, odir_var) in out_dirs:
                        if din != dout:
                            self.add_clause([-idir_var, -odir_var, turn_var])

                # 3. Implication: (in_dir & out_dir) -> -turn_var, if directions are the SAME (Straight)
                # CNF: (-idir_var OR -odir_var OR -turn_var)
                # This explicitly limits the Turn variable which helps the SAT solver.
                for (din, idir_var) in in_dirs:
                    for (dout, odir_var) in out_dirs:
                        if din == dout:
                            self.add_clause([-idir_var, -odir_var, -turn_var])

                # --- Turn Count Storage ---
                self.turn_vars_by_line[k].append(turn_var)

        # --- Enforce Global Turn Limit J ---
        turn_vars_for_line = self.turn_vars_by_line[k]
        self.at_most_k_efficient(turn_vars_for_line, J, k)
        print(f" Added turn limit constraint for line {k} (J={J}) using efficient counter")
    
    def encode_anti_parallel_directions(self, k):
        # Adds constraint: A line cannot immediately reverse direction between two adjacent cells.
        # e.g., Dir(x,y,Right) AND Dir(x+1,y,Left) is forbidden.
        N, M = self.problem.N, self.problem.M

        for x in range(N):
            for y in range(M):
                # Out Right (0) to In Left (1)
                if x + 1 < N:
                    dir_out = self.var_map[('dir', k, x, y, 0)]      
                    dir_in = self.var_map[('dir', k, x + 1, y, 1)] 
                    self.add_clause([-dir_out, -dir_in])

                # Out Left (1) to In Right (0)
                if x - 1 >= 0:
                    dir_out = self.var_map[('dir', k, x, y, 1)]      
                    dir_in = self.var_map[('dir', k, x - 1, y, 0)] 
                    self.add_clause([-dir_out, -dir_in])

                # Out Down (2) to In Up (3)
                if y + 1 < M:
                    dir_out = self.var_map[('dir', k, x, y, 2)]      
                    dir_in = self.var_map[('dir', k, x, y + 1, 3)] 
                    self.add_clause([-dir_out, -dir_in])

                # Out Up (3) to In Down (2)
                if y - 1 >= 0:
                    dir_out = self.var_map[('dir', k, x, y, 3)]      
                    dir_in = self.var_map[('dir', k, x, y - 1, 2)] 
                    self.add_clause([-dir_out, -dir_in])

    def encode_no_overlap(self):
        # Constraint 1: There is at most 1 metro line under any location
        N, M, K = self.problem.N, self.problem.M, self.problem.K
        print(f"Encoding non-collision constraints (no cell occupied by >1 line)...")
        for x in range(N):
            for y in range(M):
                # Collect 'cell' variables for all lines k at (x, y)
                vars_in_cell = [self.var_map[('cell', k, x, y)] for k in range(K)]
                if len(vars_in_cell) > 1:
                    self.at_most_one(vars_in_cell)
        print(" Added cell non-overlap constraints")
        
    def encode_popular_cells(self):
        # Scenario II Constraint: Every popular cell must be covered by at least one line
        N, M, K = self.problem.N, self.problem.M, self.problem.K
        print(f"Encoding popular cell constraints for {self.problem.P} cells...")
        for x, y in self.problem.popular_cells:
            # Clause: (cell_0,x,y OR cell_1,x,y OR ...)
            vars_in_cell = [self.var_map[('cell', k, x, y)] for k in range(K)]
            self.add_clause(vars_in_cell)
        print(" Added popular cell constraints")


    def write_dimacs(self, filename):
        with open(filename, 'w') as f:
            num_vars = self.var_counter - 1
            num_clauses = len(self.clauses)
            f.write(f"p cnf {num_vars} {num_clauses}\n")
            for clause in self.clauses:
                f.write(' '.join(map(str, clause)) + ' 0\n')

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: encoder.py <basename>", file=sys.stderr)
        sys.exit(1)
    base = sys.argv[1]
    input_file = base + ".city"
    output_file = base + ".satinput"
    varmap_file = base + ".varmap"
    try:
        # NOTE: Assumes parser.py is available and working
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