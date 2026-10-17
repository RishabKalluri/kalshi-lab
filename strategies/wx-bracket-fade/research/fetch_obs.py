"""Hourly/special METAR temperature obs from IEM for each station, dev dates only (to 2026-08-19)."""
import urllib.request, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from fetch_forecasts import CITIES  # noqa  (importing runs nothing heavy? guarded below)
D = Path(__file__).resolve().parent.parent / "data"
for s, (lat, lon, net, st) in CITIES.items():
    url = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=%s&data=tmpf&year1=2025&month1=9&day1=27"
           "&year2=2026&month2=8&day2=21&tz=Etc/UTC&format=onlycomma&latlon=no&missing=empty&trace=T&direct=no&report_type=3&report_type=4" % st)
    txt = urllib.request.urlopen(url, timeout=120).read().decode()
    (D / f"metar_{s}.csv").write_text(txt); print(s, txt.count("\n")); time.sleep(1)
