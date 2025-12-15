import gurobipy as gp
from gurobipy import GRB

def main():
    # Modell erstellen
    m = gp.Model("lp_minimal")

    # Variablen
    x = m.addVar(lb=0.0, name="x")
    y = m.addVar(lb=0.0, name="y")

    # Zielfunktion: max 3x + 2y
    m.setObjective(3 * x + 2 * y, GRB.MAXIMIZE)

    # Nebenbedingungen
    # 2x + y <= 10
    m.addConstr(2 * x + y <= 10, name="c1")
    # x + 3y <= 12
    m.addConstr(x + 3 * y <= 12, name="c2")

    # Optional: Ausgabe steuern
    m.Params.OutputFlag = 1  # 0 = still, 1 = normal

    # Optimieren
    m.optimize()

    # Ergebnis
    if m.Status == GRB.OPTIMAL:
        print("\nOptimal:")
        print(f"x = {x.X:.6f}")
        print(f"y = {y.X:.6f}")
        print(f"Obj = {m.ObjVal:.6f}")
    else:
        print(f"\nKein OPTIMAL. Status = {m.Status}")

if __name__ == "__main__":
    main()