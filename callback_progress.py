import gurobipy as gp
from gurobipy import GRB

def cb(model, where):
    if where == GRB.Callback.MIP:
        nodecnt = model.cbGet(GRB.Callback.MIP_NODCNT)
        objbst  = model.cbGet(GRB.Callback.MIP_OBJBST)   # best integer
        objbnd  = model.cbGet(GRB.Callback.MIP_OBJBND)   # best bound
        gap = None
        if objbst < GRB.INFINITY and abs(objbst) > 1e-12:
            gap = abs(objbst - objbnd) / abs(objbst)
        print(f"nodes={nodecnt:.0f} best={objbst:.6f} bound={objbnd:.6f} gap={gap}")

def main():
    # kleines MIP-Beispiel
    m = gp.Model("mip_with_cb")
    x = m.addVar(vtype=GRB.BINARY, name="x")
    y = m.addVar(vtype=GRB.BINARY, name="y")
    z = m.addVar(vtype=GRB.BINARY, name="z")

    m.setObjective(5*x + 3*y + 4*z, GRB.MAXIMIZE)
    m.addConstr(2*x + 2*y + 3*z <= 4, name="c")

    m.Params.OutputFlag = 0  # wir loggen selbst im Callback
    m.optimize(cb)

    if m.Status == GRB.OPTIMAL:
        print("\nOptimal:", {v.VarName: v.X for v in m.getVars()}, "Obj:", m.ObjVal)

if __name__ == "__main__":
    main()