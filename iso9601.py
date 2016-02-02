import re
from datetime import datetime, timedelta

def parse_iso9601(s):
    # returns a datetime. sometimes I hate python
    # note: look at http://pypi.python.org/pypi/iso8601plus/0.1.6
    mo = re.search(r'^([\d\-]+T(?:\d+):(?:\d+):(?:\d+))(.*)$', s)
    time_string = mo.group(1) ; tz_string = mo.group(2)
    if tz_string == "Z":
        tz_sign = ""; tz_hour = "0"; tz_min = "0"
    else:
        mo = re.search(r'^([+-]*)(\d+):(\d+)$', tz_string)
        tz_sign = mo.group(1) ; tz_hour = mo.group(2); tz_min = mo.group(3)
    d = datetime.strptime(time_string, "%Y-%m-%dT%H:%M:%S")
    offset_seconds = (60*int(tz_hour)+int(tz_min))*60
    if tz_sign == "-":
        offset_seconds = -offset_seconds
    return d + timedelta(seconds=-offset_seconds)

if __name__ == "__main__":
    parse_iso9601("2016-01-31T11:02:50-08:00")
    parse_iso9601("2016-02-02T18:55:34Z")
