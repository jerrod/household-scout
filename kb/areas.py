from kb.household import AREAS


def choices(areas=AREAS, other="Fits no area."):
    return {**{name: area.get("about", name) for name, area in areas.items()}, "other": other}


def kinds(areas=AREAS):
    return {name: area["kinds"] for name, area in areas.items() if area.get("kinds")}


def vault(areas=AREAS):
    return {name for name, area in areas.items() if area.get("vault")}
