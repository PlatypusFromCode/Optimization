import sys
import gurobipy as gp
from gurobipy import GRB

def main(path: str):
    m = gp.read(path)  # liest .lp, .mps, .rew, ...
    m.Params.OutputFlag = 1
    m.optimize()

    if m.Status == GRB.OPTIMAL:
        print(f"Obj = {m.ObjVal:.6f}")
        # Optional: einige Variablen ausgeben
        for v in m.getVars():
            if abs(v.X) > 1e-9:
                print(f"{v.VarName} = {v.X}")
    else:
        print(f"Status = {m.Status}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python load_and_solve.py <model.lp|model.mps>")
        raise SystemExit(2)
    main(sys.argv[1])