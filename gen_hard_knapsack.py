# gen_hard_knapsack.py
import json, random

random.seed(7)
n = 1200
weights = [random.randint(40, 60) for _ in range(n)]
values  = [w + random.randint(-3, 3) for w in weights]  # sehr ähnlich -> schwerer
capacity = int(sum(weights) * 0.50)

with open("knapsack_hard.json", "w") as f:
    json.dump({"values": values, "weights": weights, "capacity": capacity}, f)