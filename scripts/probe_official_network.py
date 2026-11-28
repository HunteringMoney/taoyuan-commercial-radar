#!/usr/bin/env python3
"""Bounded network diagnosis for the municipal GIS endpoint on Actions.

Does not fetch parcel or zoning records. Prints only timing and HTTP metadata.
"""
import json
import socket
import subprocess
from urllib.parse import urlsplit

URLS = [
    "https://urbandatasrv.tycg.gov.tw/server/rest/services/TY_UPGIS/TYMap_SDE/MapServer?f=pjson",
    "https://urplanning.tycg.gov.tw/gisMap/Map.aspx",
]


def probe(url):
    host = urlsplit(url).hostname
    result = {"host": host}
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        result["dns_families"] = sorted({"IPv6" if row[0] == socket.AF_INET6 else "IPv4" for row in addresses})
    except OSError as exc:
        result["dns_error"] = str(exc)[:160]
    for family in ("-4", "-6"):
        cmd = ["curl", family, "--connect-timeout", "6", "--max-time", "18",
               "--silent", "--show-error", "--output", "/dev/null",
               "--write-out", "http=%{http_code} remote=%{remote_ip} dns=%{time_namelookup} connect=%{time_connect} tls=%{time_appconnect} total=%{time_total}",
               url]
        try:
            run = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            result[family] = {"exit_code": run.returncode, "timings": run.stdout[:180], "error": run.stderr[:180]}
        except subprocess.TimeoutExpired:
            result[family] = {"error": "process_timeout"}
    return result


if __name__ == "__main__":
    for endpoint in URLS:
        print("OFFICIAL_NETWORK_PROBE:", json.dumps(probe(endpoint), ensure_ascii=False))
