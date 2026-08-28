import re


CATEGORY_LABELS = {
    "regional": "regional",
    "s_bahn_local": "S-Bahn / local rail",
    "intercity": "intercity",
    "high_speed": "high-speed",
    "night_train": "night train",
}

CATEGORY_COLORS = {
    "regional": "#46c27a",
    "s_bahn_local": "#4aa3df",
    "intercity": "#e2564a",
    "high_speed": "#f0a642",
    "night_train": "#8f7bdc",
}

CATEGORY_ORDER = [
    "regional",
    "s_bahn_local",
    "intercity",
    "high_speed",
    "night_train",
]

HIGH_SPEED_PREFIXES = {"ICE", "ICE-T", "ICEC", "ECE", "RJ", "RJX", "TGV", "THA"}
INTERCITY_PREFIXES = {"IC", "ICD", "EC", "ECM", "D", "EX", "FLX"}
NIGHT_TRAIN_PREFIXES = {"EN", "NJ"}
LOCAL_PREFIXES = {
    "A",
    "C",
    "L",
    "P",
    "PE",
    "PPN",
    "RS",
    "RT",
    "S",
    "SAB",
    "SP",
    "SWB",
    "T",
    "U",
}


def route_prefix(route_short_name):
    value = str(route_short_name or "").strip().upper()
    if not value:
        return ""

    first_token = value.split()[0]
    match = re.match(r"([A-ZÄÖÜ]+)", first_token)
    return match.group(1) if match else ""


def classify_route(route_short_name, route_type=None, feed_label=None):
    route_type = str(route_type or "")
    prefix = route_prefix(route_short_name)
    feed_label = str(feed_label or "").lower()

    if route_type == "101" or prefix in HIGH_SPEED_PREFIXES:
        return "high_speed"
    if route_type == "105" or prefix in NIGHT_TRAIN_PREFIXES:
        return "night_train"
    if prefix == "N" and feed_label == "intercity":
        return "night_train"
    if route_type in {"102", "103"} or prefix in INTERCITY_PREFIXES:
        return "intercity"
    if prefix in LOCAL_PREFIXES:
        return "s_bahn_local"
    if feed_label == "intercity":
        return "intercity"
    return "regional"
