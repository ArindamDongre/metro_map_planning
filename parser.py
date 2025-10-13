#!/usr/bin/env python3
"""Parser for .city files"""

class MetroProblem:
    def __init__(self, filename):
        with open(filename, 'r') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        
        self.scenario = int(lines[0])
        params = list(map(int, lines[1].split()))
        
        self.N = params[0]  # columns
        self.M = params[1]  # rows
        self.K = params[2]  # number of metro lines
        self.J = params[3]  # max turns
        self.P = params[4] if len(params) > 4 else 0
        
        self.lines = []
        for i in range(2, 2 + self.K):
            coords = list(map(int, lines[i].split()))
            start = (coords[0], coords[1])
            end = (coords[2], coords[3])
            self.lines.append((start, end))
        
        self.popular_cells = []
        if self.P > 0:
            coords = list(map(int, lines[2 + self.K].split()))
            for i in range(0, len(coords), 2):
                self.popular_cells.append((coords[i], coords[i+1]))
    
    def __str__(self):
        return f"MetroProblem(N={self.N}, M={self.M}, K={self.K}, J={self.J}, P={self.P})"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        problem = MetroProblem(sys.argv[1])
        print(problem)
        print(f"Lines: {problem.lines}")
        if problem.popular_cells:
            print(f"Popular: {problem.popular_cells}")
