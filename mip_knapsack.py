import gurobipy as gp
from gurobipy import GRB

def main():
    values = [10, 13, 7, 18, 12]
    weights = [ 2,  3, 2,  5,  3]
    capacity = 8
    n = len(values)

    m = gp.Model("knapsack")

    # 0/1-Variablen: nehme Item i oder nicht
    x = m.addVars(n, vtype=GRB.BINARY, name="x")

    # max Sum(value_i * x_i)
    m.setObjective(gp.quicksum(values[i] * x[i] for i in range(n)), GRB.MAXIMIZE)

    # Sum(weight_i * x_i) <= capacity
    m.addConstr(gp.quicksum(weights[i] * x[i] for i in range(n)) <= capacity, name="cap")

    m.Params.OutputFlag = 1
    m.optimize()

    if m.Status == GRB.OPTIMAL:
        chosen = [i for i in range(n) if x[i].X > 0.5]
        total_value = sum(values[i] for i in chosen)
        total_weight = sum(weights[i] for i in chosen)
        print("\nChosen items:", chosen)
        print("Total value:", total_value)
        print("Total weight:", total_weight)
    else:
        print(f"Status = {m.Status}")

if __name__ == "__main__":
    main()