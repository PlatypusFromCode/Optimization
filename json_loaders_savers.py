import json
import inspect
from typing import Any

import structures
from structures import Teacher, Course, Room, Faculty


# -------------------- helpers --------------------

def _read_json_list(path: str, root_key: str | None = None) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if root_key and isinstance(data, dict):
        data = data.get(root_key)

    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a JSON list, got {type(data)}")
    return data


def _enum_from_string(enum_cls, value: Any):
    """
    Try to map string codes like 'M' or 'SEMINAR' to Enum members.
    If mapping fails, return the raw value (string).
    """
    if value is None:
        return None

    # already enum
    if hasattr(value, "name") and hasattr(value, "value"):
        return value

    if isinstance(value, str):
        key = value.strip()
        # try exact attribute lookup: Faculty.M / RoomType.SEMINAR ...
        if hasattr(enum_cls, key):
            return getattr(enum_cls, key)
        # try upper-case
        if hasattr(enum_cls, key.upper()):
            return getattr(enum_cls, key.upper())
        # try enum_cls['M']
        try:
            return enum_cls[key]
        except Exception:
            pass
        try:
            return enum_cls[key.upper()]
        except Exception:
            pass

    # fallback
    return value


def _construct_flex(cls, payload: dict):
    """
    Construct cls(**kwargs) but only passes parameters that cls.__init__ accepts.
    Also handles common renames (course_names -> course_name).
    """
    sig = inspect.signature(cls.__init__)
    accepted = {p.name for p in sig.parameters.values() if p.name != "self"}

    kwargs = {}

    # Common field mappings
    # Teacher JSON -> Teacher class
    if cls is Teacher:
        # mandatory-ish
        kwargs["teacher_id"] = payload.get("teacher_id")
        kwargs["teacher_name"] = payload.get("teacher_name", payload.get("name"))
        kwargs["faculty"] = _enum_from_string(Faculty, payload.get("faculty"))

        # time constraints
        kwargs["hard_time_constr"] = payload.get("hard_time_constr", [])
        kwargs["soft_time_constr"] = payload.get("soft_time_constr", [])

        # courses taught: JSON uses course_names (list)
        cn = payload.get("course_names", payload.get("course_name"))
        if isinstance(cn, list):
            # some Teacher classes expect course_name (singular) or course_names (plural)
            if "course_names" in accepted:
                kwargs["course_names"] = cn
            elif "course_name" in accepted:
                kwargs["course_name"] = ", ".join(cn)
        elif isinstance(cn, str):
            if "course_names" in accepted:
                kwargs["course_names"] = [cn]
            elif "course_name" in accepted:
                kwargs["course_name"] = cn

    # Room JSON -> Room class
    elif cls is Room:
        kwargs["room_id"] = payload.get("room_id")
        # your Room constructor earlier: Room(id, Building/addr, name, RoomType, Faculty, capacity)
        # We keep address as string (works fine for your objectives that compare address)
        kwargs["address"] = payload.get("address")
        kwargs["name"] = payload.get("name")
        # type is a RoomType enum in your earlier code
        kwargs["type"] = _enum_from_string(structures.RoomType, payload.get("type"))
        kwargs["faculty"] = _enum_from_string(Faculty, payload.get("faculty"))
        kwargs["capacity"] = payload.get("capacity", 0)

        # Some Room classes might use 'room_type' instead of 'type'
        if "room_type" in accepted and "type" in kwargs:
            kwargs["room_type"] = kwargs.pop("type")

    # Course JSON -> Course class
    elif cls is Course:
        kwargs["course_id"] = payload.get("course_id")
        kwargs["course_name"] = payload.get("course_name")
        # course_type might be an enum in your project; if yes, map here similarly
        if hasattr(structures, "CourseType"):
            kwargs["course_type"] = _enum_from_string(structures.CourseType, payload.get("course_type"))
        else:
            kwargs["course_type"] = payload.get("course_type")

        kwargs["faculty"] = _enum_from_string(Faculty, payload.get("faculty"))
        kwargs["semester"] = payload.get("semester", [])
        kwargs["duration_minutes"] = payload.get("duration_minutes", 90)
        kwargs["facility_constr"] = payload.get("facility_constr", [])
        kwargs["teacher_ids"] = payload.get("teacher_ids", [])
        kwargs["room_name"] = payload.get("room_name")
        kwargs["expected_num_students"] = payload.get("expected_num_students", 0)
        kwargs["times_per_week"] = payload.get("times_per_week", 1.0)

    else:
        # generic: pass through only accepted keys
        for k, v in payload.items():
            if k in accepted:
                kwargs[k] = v

    # filter to accepted
    kwargs = {k: v for k, v in kwargs.items() if k in accepted}

    return cls(**kwargs)


# -------------------- loaders --------------------

def load_teachers(path: str) -> list[Teacher]:
    data = _read_json_list(path)
    out = []
    for item in data:
        out.append(_construct_flex(Teacher, item))
    return out


def load_rooms(path: str) -> list[Room]:
    data = _read_json_list(path)
    out = []
    for item in data:
        out.append(_construct_flex(Room, item))
    return out


def load_courses(path: str) -> list[Course]:
    data = _read_json_list(path)
    out = []
    for item in data:
        out.append(_construct_flex(Course, item))
    return out


def load_timeslots(path: str) -> list[dict]:
    """
    Returns raw timeslot dicts as in your JSON.
    Example item: {"timeslot_id": 1, "day": "Montag", "start": "07:30", "end": "09:00"}
    """
    return _read_json_list(path)