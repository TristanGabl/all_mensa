#!/usr/bin/env python3
"""Fetch today's menus and write data/menu.json (run by GitHub Actions)."""
import json, re, datetime, urllib.request
from zoneinfo import ZoneInfo

TODAY = datetime.datetime.now(ZoneInfo("Europe/Zurich")).date()
UA = {"User-Agent": "Mozilla/5.0 (all_mensa)"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read().decode("utf-8")


def eth(facility_id, name, link):
    url = ("https://idapps.ethz.ch/cookpit-pub-services/v1/weeklyrotas?client-id=ethz-wcms"
           f"&lang=en&rs-first=0&rs-size=50&valid-after={TODAY - datetime.timedelta(days=7)}")
    meals = []
    for rota in json.loads(get(url))["weekly-rota-array"]:
        if rota["facility-id"] != facility_id or not (rota["valid-from"] <= str(TODAY) <= rota["valid-to"]):
            continue
        for day in rota["day-of-week-array"]:
            if day["day-of-week-code"] != TODAY.isoweekday():
                continue
            for oh in day.get("opening-hour-array", []):
                for mt in oh.get("meal-time-array", []):
                    for line in mt.get("line-array", []):
                        m = line.get("meal")
                        if not m or m.get("name") == "novalue":
                            continue
                        prices = {p["customer-group-desc-short"]: p["price"] for p in m.get("meal-price-array", [])}
                        meals.append({
                            "time": mt["name"], "line": line["name"], "name": m["name"],
                            "description": m.get("description", "").replace(" | ", ", "),
                            "tags": [c["desc"] for c in m.get("meal-class-array", [])],
                            "price": prices.get("stud."),
                        })
    # Drop buffet/dessert lines; within each meal time list VEGAN, GARDEN, HOME first.
    meals = [m for m in meals if not m["line"].lower().startswith(("hot & cold", "dessert"))]
    top = ["VEGAN", "GARDEN", "HOME"]
    rank = lambda m: next((i for i, t in enumerate(top) if m["line"].upper().startswith(t)), len(top))
    times = list(dict.fromkeys(m["time"] for m in meals))
    meals.sort(key=lambda m: (times.index(m["time"]), rank(m)))
    return {"name": name, "link": link, "meals": meals}


def food2050(path, name, link):
    raw = get(f"https://app.food2050.ch/de/zfv/universitat-zurich,campus-zentrum/{path}/menu/weekly")
    s = raw.replace('\\"', '"')
    meals, seen = [], set()
    # Split payload into per-day chunks, keep only today's.
    for chunk in s.split('"__typename":"OutletMenuCategoryCalendarRangeDay"')[1:]:
        d = re.search(r'"dateLocal":"(\d{4}-\d{2}-\d{2})', chunk)
        if not d or d.group(1) != str(TODAY):
            continue
        for item in chunk.split('"__typename":"OutletMenuItemDish"')[1:]:
            cat = re.search(r'"OutletMenuCategory","id":"[^"]*","name":"([^"]*)"', item)
            nm = re.search(r'"name":"((?:[^"\\]|\\.)*)","description":"((?:[^"\\]|\\.)*)"', item)
            if not nm:
                continue
            url = re.search(r'"detailUrl":"[^"]*,([^",/]+)/\d{4}-', item)
            line = cat.group(1) if cat else url.group(1).replace("-", " ") if url else ""
            key = (line, nm.group(1))
            if key in seen:
                continue
            seen.add(key)
            tags = ["Vegan"] if '"isVegan":true' in item else ["Vegetarian"] if '"isVegetarian":true' in item else []
            meals.append({
                "time": "Lunch", "line": key[0].upper(), "name": json.loads(f'"{nm.group(1)}"').title(),
                "description": json.loads(f'"{nm.group(2)}"'), "tags": tags, "price": None,
            })
    return {"name": name, "link": link, "meals": meals}


def safe(fn, *args):
    try:
        return fn(*args)
    except Exception as e:  # keep other mensas working if one source breaks
        return {"name": args[1], "link": args[2], "meals": [], "error": str(e)}


out = {
    "date": str(TODAY),
    "updated": datetime.datetime.now(ZoneInfo("Europe/Zurich")).isoformat(timespec="minutes"),
    "mensas": [
        safe(eth, 9, "ETH Polymensa",
             f"https://ethz.ch/en/campus/erleben/gastronomie-und-einkaufen/gastronomie/menueplaene/offerDay.html?date={TODAY}&id=9"),
        safe(food2050, "untere-mensa/mittagsverpflegung", "UZH Untere Mensa", "https://www.zfv.ch/de/essen-gehen/untere-mensa-uzh"),
        safe(food2050, "obere-mensa/lunch", "UZH Obere Mensa", "https://www.zfv.ch/de/essen-gehen/obere-mensa-uzh"),
    ],
}
with open("data/menu.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
for m in out["mensas"]:
    print(m["name"], len(m["meals"]), m.get("error", ""))
