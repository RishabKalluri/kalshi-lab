"""Download hourly forecasts (Open-Meteo previous-runs API) and observed daily highs (IEM) per settlement station.

Source: https://previous-runs-api.open-meteo.com  (temperature_2m_previous_dayN = the forecast issued N days before
the valid hour; no hindsight, unlike the Historical Forecast API which stitches short-lead hours).
Observed: Iowa Environmental Mesonet daily summaries (ASOS), dev dates only (before the lockbox start).
Output: strategies/wx-bracket-fade/data/fc_<CITY>.json  {"time":[utc hours], model_dayN: [..C..]}
"""
import json, sys, time, urllib.request, urllib.parse
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data"
CITIES = {  # series: (lat, lon, IEM network, IEM station)
    "KXHIGHNY": (40.7789, -73.9692, "NY_ASOS", "NYC"),
    "KXHIGHLAX": (33.9425, -118.4081, "CA_ASOS", "LAX"),
    "KXHIGHMIA": (25.7959, -80.2870, "FL_ASOS", "MIA"),
    "KXHIGHCHI": (41.7868, -87.7522, "IL_ASOS", "MDW"),
    "KXHIGHAUS": (30.1945, -97.6699, "TX_ASOS", "AUS"),
    "KXHIGHTDAL": (32.8998, -97.0403, "TX_ASOS", "DFW"),
    "KXHIGHTPHX": (33.4373, -112.0078, "AZ_ASOS", "PHX"),
    "KXHIGHTHOU": (29.6454, -95.2789, "TX_ASOS", "HOU"),
    "KXHIGHTATL": (33.6407, -84.4277, "GA_ASOS", "ATL"),
    "KXHIGHTBOS": (42.3656, -71.0096, "MA_ASOS", "BOS"),
}
MODELS = ["ecmwf_ifs025", "gfs_seamless"]
START, END = "2025-09-28", "2026-10-13"
OBS_END = "2026-08-19"  # last development day

def get(url):
    for i in range(5):
        try:
            return urllib.request.urlopen(url, timeout=60).read().decode()
        except Exception as e:
            print("retry", e, file=sys.stderr); time.sleep(5 * (i + 1))
    raise SystemExit("failed " + url)

def main():
  for s, (lat, lon, net, st) in CITIES.items():
      res = {}
      for model in MODELS:
          vars_ = ",".join(f"temperature_2m_previous_day{d}" for d in (1, 2, 3))
          q = dict(latitude=lat, longitude=lon, start_date=START, end_date=END, hourly=vars_, models=model,
                   timezone="GMT")
          j = json.loads(get("https://previous-runs-api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(q)))
          res.setdefault("time", j["hourly"]["time"])
          for k, v in j["hourly"].items():
              if k != "time":
                  res[f"{model}:{k.split('_')[-1]}"] = v
          time.sleep(1)
      (OUT / f"fc_{s}.json").write_text(json.dumps(res))
      url = (f"https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py?network={net}&stations={st}"
             f"&year1=2025&month1=9&day1=28&year2=2026&month2=8&day2=19&format=csv&na=blank")
      (OUT / f"obs_{s}.csv").write_text(get(url))
      print(s, len(res["time"]), flush=True)


if __name__ == "__main__":
    main()