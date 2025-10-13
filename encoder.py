#!/usr/bin/env python3
"""Encodes metro problem as SAT"""

import sys
import pickle
from parser import MetroProblem

class SATEncoder:
    def __init__(self, problem):
        self.problem = problem
        self.var_counter = 1
        self.clauses = []
        self.var_map = {}
    
    def new_var(self, description):
        """Create new SAT variable"""
        if description not in self.var_map:
            self.var_map[description] = self.var_counter
            self.var_counter += 1
        return self.var_map[description]
    
    def add_clause(self, literals):
        """Add a clause"""
        if literals:
            self.clauses.append(literals)
    
    def create_variables(self):
        """Create all necessary variables"""
        N, M, K = self.problem.N, self.problem.M, self.problem.K
        
        print(f"Creating variables for {N}x{M} grid, {K} lines...")
        
        # Variable: cell[k][x][y] - metro line k uses cell (x,y)
        for k in range(K):
            for x in range(N):
                for y in range(M):
                    self.new_var(('cell', k, x, y))
        
        # Variable: dir[k][x][y][d] - line k moves in direction d at (x,y)
        # d: 0=Right, 1=Left, 2=Down, 3=Up
        for k in range(K):
            for x in range(N):
                for y in range(M):
                    for d in range(4):
                        self.new_var(('dir', k, x, y, d))
        
        print(f"Created {self.var_counter - 1} variables")
    
    def encode_constraints(self):
        """Encode all constraints as CNF clauses"""
        print("Encoding constraints...")
        self.encode_start_end()
        self.encode_no_collision()
        self.encode_basic_connectivity()
        print(f"Generated {len(self.clauses)} clauses")
    
    def encode_start_end(self):
        """Each metro line must occupy its start and end points"""
        for k in range(self.problem.K):
            sx, sy = self.problem.lines[k][0]
            ex, ey = self.problem.lines[k][1]
            
            start_var = self.var_map[('cell', k, sx, sy)]
            self.add_clause([start_var])
            
            end_var = self.var_map[('cell', k, ex, ey)]
            self.add_clause([end_var])
    
    def encode_no_collision(self):
        """At most one metro line per cell"""
        N, M, K = self.problem.N, self.problem.M, self.problem.K
        
        for x in range(N):
            for y in range(M):
                for k1 in range(K):
                    for k2 in range(k1 + 1, K):
                        var1 = self.var_map[('cell', k1, x, y)]
                        var2 = self.var_map[('cell', k2, x, y)]
                        self.add_clause([-var1, -var2])
    
    def encode_basic_connectivity(self):
        """Basic path connectivity"""
        N, M, K = self.problem.N, self.problem.M, self.problem.K
        
        for k in range(K):
            for x in range(N):
                for y in range(M):
                    cell_var = self.var_map[('cell', k, x, y)]
                    
                    possible_dirs = []
                    
                    if x + 1 < N:
                        dir_var = self.var_map[('dir', k, x, y, 0)]
                        possible_dirs.append(dir_var)
                        next_cell = self.var_map[('cell', k, x+1, y)]
                        self.add_clause([-dir_var, next_cell])
                    
                    if x - 1 >= 0:
                        dir_var = self.var_map[('dir', k, x, y, 1)]
                        possible_dirs.append(dir_var)
                        next_cell = self.var_map[('cell', k, x-1, y)]
                        self.add_clause([-dir_var, next_cell])
                    
                    if y + 1 < M:
                        dir_var = self.var_map[('dir', k, x, y, 2)]
                        possible_dirs.append(dir_var)
                        next_cell = self.var_map[('cell', k, x, y+1)]
                        self.add_clause([-dir_var, next_cell])
                    
                    if y - 1 >= 0:
                        dir_var = self.var_map[('dir', k, x, y, 3)]
                        possible_dirs.append(dir_var)
                        next_cell = self.var_map[('cell', k, x, y-1)]
                        self.add_clause([-dir_var, next_cell])
                    
                    sx, sy = self.problem.lines[k][0]
                    ex, ey = self.problem.lines[k][1]
                    
                    if (x, y) != (ex, ey) and possible_dirs:
                        self.add_clause([-cell_var] + possible_dirs)
    
    def write_dimacs(self, filename):
        """Write CNF in DIMACS format"""
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
        problem = MetroProblem(input_file)
        print(f"Loaded problem: {problem}")
        
        encoder = SATEncoder(problem)
        encoder.create_variables()
        encoder.encode_constraints()
        encoder.write_dimacs(output_file)
        
        with open(varmap_file, 'wb') as f:
            pickle.dump(encoder.var_map, f)
        
        print(f"Success! Created {output_file}")
        print(f"Variables: {encoder.var_counter-1}, Clauses: {len(encoder.clauses)}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)