import gurobipy as gp
from gurobipy import GRB


def print_objective_breakdown(parts: dict[str, gp.LinExpr], obj_val: float):
    print("\n================ OBJECTIVE BREAKDOWN ================")
    total = 0.0
    for name, expr in parts.items():
        try:
            v = float(expr.getValue())
        except Exception:
            v = float("nan")
        print(f"{name:22s}: {v:12.6f}")
        if v == v:  # not NaN
            total += v
    print(f"{'SUM(components)':22s}: {total:12.6f}")
    print(f"{'OBJ (m.ObjVal)':22s}: {obj_val:12.6f}")
    print("====================================================\n")


def main():
    # ------------------ Data ------------------
    values = [10, 13, 7, 18, 12]
    weights = [2, 3, 2, 5, 3]
    capacity = 8
    n = len(values)

    # Optional: "Kategorie" je Item (nur um zusätzliche Softs demonstrieren zu können)
    # z.B. A/B = unterschiedliche Item-Typen
    categories = ["A", "A", "B", "B", "A"]

    # ------------------ Settings (ähnlich lp_minimal) ------------------
    ENABLE = {
        "BASE_VALUE": True,            # klassisches Value-Maximieren
        "PENALIZE_UNUSED_CAP": True,   # soft: ungenutzte Kapazität ist "schlecht"
        "MIN_ITEMS": True,             # soft: mindestens k items (als Strafe, wenn unterschritten)
        "MAX_ITEMS": False,            # soft: zu viele items bestrafen
        "PREFER_CATEGORY_A": True,     # soft: bevorzuge Kategorie A
    }

    # Gewichte/Skalierung für Soft-Terme (frei wählbar)
    W = {
        "UNUSED_CAP": 0.5,       # Strafe pro ungenutzter Kapazitätseinheit
        "MIN_ITEMS": 3.0,        # Strafe pro fehlendem Item unter Minimum
        "MAX_ITEMS": 1.0,        # Strafe pro Item über Maximum
        "PREFER_A": 1.0,         # Bonus pro A-Item (als zusätzlicher Wert)
    }

    MIN_K = 2  # gewünschte Mindestanzahl Items
    MAX_K = 4  # gewünschte Maximalanzahl Items

    # ------------------ Sanity checks ------------------
    assert len(weights) == n, "weights length mismatch"
    assert capacity >= 0, "capacity must be non-negative"
    for i in range(n):
        assert weights[i] >= 0, f"negative weight at i={i}"
    print("Data:", list(zip(range(n), values, weights, categories)), "capacity=", capacity)

    # ------------------ Model ------------------
    m = gp.Model("knapsack_extended")

    # 0/1 Decision: Item i wählen?
    x = m.addVars(n, vtype=GRB.BINARY, name="x")

    # Hard constraint: Kapazität
    used_weight = gp.quicksum(weights[i] * x[i] for i in range(n))
    m.addConstr(used_weight <= capacity, name="cap")

    # ------------------ Objective parts (wie Soft-Expressions) ------------------
    parts: dict[str, gp.LinExpr] = {}

    # Basis: Wert maximieren
    base_value = gp.quicksum(values[i] * x[i] for i in range(n))
    if ENABLE["BASE_VALUE"]:
        parts["BASE_VALUE"] = base_value

    # Soft 1: ungenutzte Kapazität bestrafen (macht Lösungen "dichter")
    # unused = capacity - used_weight (>= 0)
    if ENABLE["PENALIZE_UNUSED_CAP"]:
        unused = m.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="unused_cap")
        m.addConstr(unused == capacity - used_weight, name="unused_def")
        # Strafe in MAX-Objective => abziehen
        parts["- UNUSED_CAP"] = -W["UNUSED_CAP"] * unused

    # Soft 2: Mindestanzahl Items (als Soft, nicht hard)
    if ENABLE["MIN_ITEMS"]:
        count_items = gp.quicksum(x[i] for i in range(n))
        short = m.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="min_items_shortfall")
        m.addConstr(short >= MIN_K - count_items, name="min_items_short_lb")
        parts["- MIN_ITEMS_SHORT"] = -W["MIN_ITEMS"] * short

    # Soft 3: Maximalanzahl Items (als Soft)
    if ENABLE["MAX_ITEMS"]:
        count_items = gp.quicksum(x[i] for i in range(n))
        over = m.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="max_items_over")
        m.addConstr(over >= count_items - MAX_K, name="max_items_over_lb")
        parts["- MAX_ITEMS_OVER"] = -W["MAX_ITEMS"] * over

    # Soft 4: Kategoriepräferenz (z.B. A bevorzugen)
    if ENABLE["PREFER_CATEGORY_A"]:
        bonus_a = gp.quicksum((1 if categories[i] == "A" else 0) * x[i] for i in range(n))
        parts["+ PREFER_A"] = W["PREFER_A"] * bonus_a

    # Gesamt-Objective (MAX): Summe aller Parts
    m.setObjective(gp.quicksum(parts.values()), GRB.MAXIMIZE)

    # Solve
    m.Params.OutputFlag = 1
    m.optimize()

    # ------------------ Output ------------------
    if m.Status == GRB.OPTIMAL:
        chosen = [i for i in range(n) if x[i].X > 0.5]
        total_value = sum(values[i] for i in chosen)
        total_weight = sum(weights[i] for i in chosen)
        chosen_cats = [categories[i] for i in chosen]

        print("\nChosen items:", chosen)
        print("Chosen categories:", chosen_cats)
        print("Total raw value:", total_value)
        print("Total weight:", total_weight)

        print_objective_breakdown(parts, m.ObjVal)
    else:
        print(f"Status = {m.Status}")


if __name__ == "__main__":
    main()