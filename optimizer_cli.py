#!/usr/bin/env python3
import argparse
import json
import sys
from typing import Any, Dict, List, Optional

import gurobipy as gp
from gurobipy import GRB


# -----------------------------
# Callback
# -----------------------------
def mip_progress_cb(model: gp.Model, where: int):
    if where == GRB.Callback.MIP:
        nodecnt = model.cbGet(GRB.Callback.MIP_NODCNT)
        objbst  = model.cbGet(GRB.Callback.MIP_OBJBST)   # best integer
        objbnd  = model.cbGet(GRB.Callback.MIP_OBJBND)   # best bound

        gap = None
        if objbst < GRB.INFINITY and abs(objbst) > 1e-12:
            gap = abs(objbst - objbnd) / abs(objbst)

        print(f"nodes={nodecnt:.0f} best={objbst:.6f} bound={objbnd:.6f} gap={gap}")


def optimize_and_report(
    m: gp.Model,
    use_callback: bool,
    output_flag: int,
    export_path: Optional[str] = None,
):
    m.Params.OutputFlag = int(output_flag)

    if export_path:
        # Export vor dem Solve
        m.write(export_path)

    if use_callback:
        m.optimize(mip_progress_cb)
    else:
        m.optimize()

    return m


# -----------------------------
# Knapsack
# -----------------------------
def load_knapsack_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    values = data["values"]
    weights = data["weights"]
    capacity = data["capacity"]

    if not isinstance(values, list) or not isinstance(weights, list):
        raise ValueError("values und weights müssen Listen sein.")
    if len(values) != len(weights):
        raise ValueError("values und weights müssen die gleiche Länge haben.")
    if capacity < 0:
        raise ValueError("capacity muss >= 0 sein.")

    return {"values": values, "weights": weights, "capacity": capacity}


def build_knapsack_model(values: List[float], weights: List[float], capacity: float) -> gp.Model:
    n = len(values)
    m = gp.Model("knapsack")

    x = m.addVars(n, vtype=GRB.BINARY, name="x")

    m.setObjective(gp.quicksum(values[i] * x[i] for i in range(n)), GRB.MAXIMIZE)
    m.addConstr(gp.quicksum(weights[i] * x[i] for i in range(n)) <= capacity, name="capacity")

    return m


def report_knapsack_solution(m: gp.Model):
    if m.Status == GRB.OPTIMAL:
        xvars = [v for v in m.getVars() if v.VarName.startswith("x[")]
        chosen = [int(v.VarName.split("[")[1].split("]")[0]) for v in xvars if v.X > 0.5]
        print(f"Status: OPTIMAL\nObj: {m.ObjVal:.6f}\nChosen items: {chosen}")
    else:
        print(f"Status: {m.Status} (not OPTIMAL)")


# -----------------------------
# Stundenplan
# -----------------------------
def build_schedule_model(
    teachers_path: str,
    courses_path: str,
    rooms_path: str,
    num_slots: int,
    weights: Dict[str, float],
):
    # Erwartet die bestehenden Module
    from gurobipy import Model
    import hard_constrains
    import soft_constrains
    import json_loaders_savers
    from structures import Teacher, Course, Room

    m = Model("schedule")

    teachers_objects: List[Teacher] = json_loaders_savers.load_teachers(teachers_path)
    courses_objects: List[Course] = json_loaders_savers.load_courses(courses_path)
    rooms_objects: List[Room] = json_loaders_savers.load_rooms(rooms_path)

    teachers_id_list = [t.teacher_id for t in teachers_objects]
    courses_id_list  = [c.course_id for c in courses_objects]
    rooms_id_list    = [r.room_id for r in rooms_objects]

    slots = range(num_slots)

    teacher_by_id = {t.teacher_id: t for t in teachers_objects}
    course_by_id  = {c.course_id: c for c in courses_objects}
    room_by_id    = {r.room_id: r for r in rooms_objects}

    semesters = {sem for c in courses_objects for sem in c.semester}

    x = m.addVars(slots, teachers_id_list, courses_id_list, rooms_id_list,
                  vtype=GRB.BINARY, name="x")

    # Hard constraints
    hard_constrains.add_single_room_single_course_constr(m, x, slots, teachers_id_list, courses_id_list, rooms_id_list)
    hard_constrains.add_single_teacher_single_course_constr(m, x, slots, teachers_id_list, courses_id_list, rooms_id_list)
    hard_constrains.add_no_semester_overlapping_constr(m, x, semesters, course_by_id, slots, teachers_id_list, courses_id_list, rooms_id_list)
    hard_constrains.add_teacher_hard_time_constraints(m, x, teachers_id_list, teacher_by_id, courses_id_list, rooms_id_list)
    hard_constrains.add_room_capacity_constr(m, x, courses_id_list, rooms_id_list, course_by_id, room_by_id, slots, teachers_id_list)
    hard_constrains.add_room_type_constraints(m, x, slots, teachers_id_list, courses_id_list, rooms_id_list, course_by_id, room_by_id)
    hard_constrains.add_all_courses_scheduled_constraint(m, x, courses_id_list, teachers_id_list, rooms_id_list, slots)

    # Soft objective parts
    teacher_soft = soft_constrains.add_teacher_soft_time_objective(
        m, x, teachers_id_list, teacher_by_id, courses_id_list, rooms_id_list,
        weight=weights.get("TEACHER_SOFT_TIME", 0.1)
    )
    room_waste = soft_constrains.add_room_waste_objective(
        m, x, courses_id_list, rooms_id_list, course_by_id, room_by_id, slots, teachers_id_list,
        weight=weights.get("ROOM_WASTE", 0.7)
    )
    faculty_mismatch = soft_constrains.add_faculty_mismatch_objective(
        m, x, courses_id_list, rooms_id_list, course_by_id, room_by_id, slots, teachers_id_list,
        weight=weights.get("FACULTY_MISMATCH", 0.1)
    )

    m.setObjective(teacher_soft + room_waste + faculty_mismatch, GRB.MINIMIZE)

    # Rückgabe: Model + relevante Objekte fürs Reporting/Speichern
    ctx = dict(
        x=x,
        slots=slots,
        teachers_id_list=teachers_id_list,
        courses_id_list=courses_id_list,
        rooms_id_list=rooms_id_list,
        teacher_by_id=teacher_by_id,
        course_by_id=course_by_id,
        room_by_id=room_by_id,
    )
    return m, ctx


def report_schedule_solution(m: gp.Model, ctx: Dict[str, Any], semester_print: Optional[str], save_json: Optional[str]):
    import json_loaders_savers

    if m.Status == GRB.INFEASIBLE:
        print("Model infeasible, computing IIS...")
        m.computeIIS()
        m.write("schedule_model.ilp")
        print("IIS written to schedule_model.ilp")
        return

    if m.Status != GRB.OPTIMAL:
        print(f"NO OPTIMAL SOLUTION. Status = {m.Status}")
        return

    print(f"Optimal solution found. Obj = {m.ObjVal:.6f}")

    if semester_print:
        json_loaders_savers.print_schedule_for_semester(
            m,
            ctx["x"],
            semester=semester_print,
            slots=ctx["slots"],
            teachers_id_list=ctx["teachers_id_list"],
            courses_id_list=ctx["courses_id_list"],
            rooms_id_list=ctx["rooms_id_list"],
            teacher_by_id=ctx["teacher_by_id"],
            course_by_id=ctx["course_by_id"],
            room_by_id=ctx["room_by_id"],
        )

    if save_json:
        json_loaders_savers.save_schedule_to_json(
            m,
            ctx["x"],
            ctx["slots"],
            ctx["teachers_id_list"],
            ctx["courses_id_list"],
            ctx["rooms_id_list"],
            path=save_json,
        )
        print(f"Saved schedule to: {save_json}")


# -----------------------------
# Read & solve arbitrary .lp/.mps
# -----------------------------
def solve_model_file(path: str, use_callback: bool, output_flag: int, export_path: Optional[str]):
    m = gp.read(path)
    optimize_and_report(m, use_callback=use_callback, output_flag=output_flag, export_path=export_path)

    if m.Status == GRB.OPTIMAL:
        print(f"Obj = {m.ObjVal:.6f}")
        for v in m.getVars():
            if abs(v.X) > 1e-9:
                print(f"{v.VarName} = {v.X}")
    else:
        print(f"Status = {m.Status}")


# -----------------------------
# CLI
# -----------------------------
def parse_weights(weight_args: List[str]) -> Dict[str, float]:
    """
    Erwartet z.B.: ["TEACHER_SOFT_TIME=0.1", "ROOM_WASTE=0.7", "FACULTY_MISMATCH=0.1"]
    """
    w: Dict[str, float] = {}
    for item in weight_args:
        if "=" not in item:
            raise ValueError(f"Invalid weight format: {item}. Use NAME=value")
        k, v = item.split("=", 1)
        w[k.strip()] = float(v.strip())
    return w


def main():
    ap = argparse.ArgumentParser(prog="optimizer_cli")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # knapsack
    ap_k = sub.add_parser("knapsack", help="Solve a knapsack instance from JSON")
    ap_k.add_argument("input", help="Path to knapsack JSON (values/weights/capacity)")
    ap_k.add_argument("--export", default=None, help="Export model to .lp/.mps etc.")
    ap_k.add_argument("--callback", action="store_true", help="Print MIP progress via callback")
    ap_k.add_argument("--output-flag", type=int, default=1, help="Gurobi OutputFlag (0/1)")

    # schedule
    ap_s = sub.add_parser("schedule", help="Solve the schedule model from teachers/courses/rooms JSON")
    ap_s.add_argument("--teachers", required=True, help="teachers.json")
    ap_s.add_argument("--courses", required=True, help="courses.json")
    ap_s.add_argument("--rooms", required=True, help="rooms.json")
    ap_s.add_argument("--slots", type=int, default=5, help="Number of time slots (default: 5)")
    ap_s.add_argument("--weight", action="append", default=[], help="Set weights: NAME=value (repeatable)")
    ap_s.add_argument("--semester-print", default=None, help="Print schedule for one semester (e.g. CS4DMsem1)")
    ap_s.add_argument("--save-json", default=None, help="Write schedule_solution.json")
    ap_s.add_argument("--export", default=None, help="Export model to .lp/.mps etc.")
    ap_s.add_argument("--callback", action="store_true", help="Print MIP progress via callback")
    ap_s.add_argument("--output-flag", type=int, default=1, help="Gurobi OutputFlag (0/1)")

    # solve model file
    ap_f = sub.add_parser("solve-file", help="Read and solve an existing .lp/.mps/.rew model file")
    ap_f.add_argument("path", help="Path to model file (.lp/.mps/...)")
    ap_f.add_argument("--export", default=None, help="Export model after reading (optional)")
    ap_f.add_argument("--callback", action="store_true", help="Print MIP progress via callback")
    ap_f.add_argument("--output-flag", type=int, default=1, help="Gurobi OutputFlag (0/1)")

    args = ap.parse_args()

    if args.cmd == "knapsack":
        data = load_knapsack_json(args.input)
        m = build_knapsack_model(**data)
        optimize_and_report(m, use_callback=args.callback, output_flag=args.output_flag, export_path=args.export)
        report_knapsack_solution(m)

    elif args.cmd == "schedule":
        weights = {
            "TEACHER_SOFT_TIME": 0.1,
            "ROOM_WASTE": 0.7,
            "FACULTY_MISMATCH": 0.1,
        }
        weights.update(parse_weights(args.weight))

        m, ctx = build_schedule_model(
            teachers_path=args.teachers,
            courses_path=args.courses,
            rooms_path=args.rooms,
            num_slots=args.slots,
            weights=weights,
        )
        optimize_and_report(m, use_callback=args.callback, output_flag=args.output_flag, export_path=args.export)
        report_schedule_solution(m, ctx, semester_print=args.semester_print, save_json=args.save_json)

    elif args.cmd == "solve-file":
        solve_model_file(args.path, use_callback=args.callback, output_flag=args.output_flag, export_path=args.export)

    else:
        raise RuntimeError("Unknown command")


if __name__ == "__main__":
    main()