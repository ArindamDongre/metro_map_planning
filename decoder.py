#!/usr/bin/env python3
"""Decodes SAT solution to metro map"""

import sys
import pickle
from parser import MetroProblem

class SATDecoder:
    def __init__(self, problem, var_map, sat_output_file):
        self.problem = problem
        self.var_map = var_map
        self.reverse_map = {v: k for k, v in var_map.items()}
        
        with open(sat_output_file, 'r') as f:
            lines = f.readlines()
        
        if not lines or lines[0].strip() == "UNSAT":
            self.satisfiable = False
            self.assignment = {}
        else:
            self.satisfiable = True
            assignments = []
            for line in lines[1:]:
                assignments.extend(map(int, line.strip().split()))
            
            self.assignment = {}
            for var in assignments:
                if var == 0:
                    break
                if var > 0:
                    self.assignment[var] = True
                else:
                    self.assignment[-var] = False
    
    def decode(self):
        """Convert SAT solution to paths"""
        if not self.satisfiable:
            return None
        
        paths = []
        for k in range(self.problem.K):
            path = self.extract_path_for_line(k)
            paths.append(path)
        
        return paths
    
    def extract_path_for_line(self, k):
        """Extract the path for a single metro line"""
        start_x, start_y = self.problem.lines[k][0]
        end_x, end_y = self.problem.lines[k][1]
        
        path = []
        current = (start_x, start_y)
        visited = set([current])
        
        # Direction mapping: 0=R, 1=L, 2=D, 3=U
        dir_map = {0: ('R', 1, 0), 1: ('L', -1, 0), 2: ('D', 0, 1), 3: ('U', 0, -1)}
        
        while current != (end_x, end_y):
            x, y = current
            moved = False
            
            # Check which direction is active
            for d in range(4):
                dir_var = self.var_map.get(('dir', k, x, y, d))
                if dir_var and self.assignment.get(dir_var, False):
                    symbol, dx, dy = dir_map[d]
                    next_pos = (x + dx, y + dy)
                    
                    if next_pos not in visited:
                        path.append(symbol)
                        current = next_pos
                        visited.add(current)
                        moved = True
                        break
            
            if not moved:
                # Couldn't find next move - path is incomplete
                break
            
            # Safety check: don't loop forever
            if len(visited) > self.problem.N * self.problem.M:
                break
        
        return path

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: decoder.py <basename>", file=sys.stderr)
        sys.exit(1)
    
    base = sys.argv[1]
    input_file = base + ".city"
    sat_output = base + ".satoutput"
    output_file = base + ".metromap"
    varmap_file = base + ".varmap"
    
    try:
        problem = MetroProblem(input_file)
        
        with open(varmap_file, 'rb') as f:
            var_map = pickle.load(f)
        
        decoder = SATDecoder(problem, var_map, sat_output)
        paths = decoder.decode()
        
        with open(output_file, 'w') as f:
            if paths is None:
                f.write("0\n")
            else:
                for path in paths:
                    if path:
                        f.write(' '.join(path) + ' 0\n')
                    else:
                        f.write("0\n")
        
        print(f"Success! Created {output_file}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)