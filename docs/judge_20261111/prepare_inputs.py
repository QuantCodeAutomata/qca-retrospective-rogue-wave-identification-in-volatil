"""Rebuild the three daily High inputs used in the 11 November 2026 figure refresh."""
import argparse
import hashlib
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd


HERE = Path(__file__).resolve().parent
CBOE = "https://cdn.cboe.com"
SOURCES = {
    "VIX_History.csv": CBOE + "/api/global/us_indices/daily_prices/VIX_History.csv",
    "VXO_cboe_archive_raw.xls": CBOE + "/resources/us/indices/vxoarchive.xls",
    "VXO_cboe_current_raw.csv": CBOE + "/resources/us/indices/vxocurrent.csv",
    "VXO_dashboard.json": CBOE + "/api/global/delayed_quotes/charts/historical/_VXO.json",
}


def source_bytes(cache, filename, url, download):
    path = cache / filename
    if path.is_file():
        return path.read_bytes()
    if not download:
        raise FileNotFoundError(f"{path} is missing. Populate the cache or pass --download.")
    request = Request(url, headers={"User-Agent": "QCA-replication-report/1.0"})
    with urlopen(request, timeout=40) as response:
        payload = response.read()
    path.write_bytes(payload)
    return payload


def parse_vxo_archive(frame):
    frame = frame.dropna(how="all").copy()
    frame.columns = [str(label).strip().lower() for label in frame]
    frame["date"] = pd.to_datetime(frame["date"], format="mixed")
    frame["high"] = pd.to_numeric(frame["high"], errors="raise")
    return frame[["date", "high"]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--download", action="store_true", help="Fetch missing raw files from their recorded source URLs.")
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    output = args.output
    if output.exists() and any(output.iterdir()):
        parser.error("Choose an empty output directory.")
    evidence = json.loads((HERE / "evidence.json").read_text())
    raw = {name: source_bytes(args.cache, name, url, args.download) for name, url in SOURCES.items()}

    vix = pd.read_csv(io.BytesIO(raw["VIX_History.csv"]), float_precision="round_trip")
    vix.columns = vix.columns.str.lower()
    vix["date"] = pd.to_datetime(vix["date"], format="%m/%d/%Y")
    vix = vix.loc[vix["date"].between("1990-01-02", "2026-11-10"), ["date", "high"]]

    early = pd.read_excel(io.BytesIO(raw["VXO_cboe_archive_raw.xls"]), sheet_name="Sheet1", skiprows=2)
    later = pd.read_csv(io.BytesIO(raw["VXO_cboe_current_raw.csv"]), skiprows=2)
    archive = pd.concat([parse_vxo_archive(early), parse_vxo_archive(later)])
    archive = archive.loc[archive["date"].le("2021-01-07")]
    dashboard = json.loads(raw["VXO_dashboard.json"])
    if dashboard["symbol"] != "_VXO":
        raise ValueError("Unexpected VXO chart instrument")
    tail = pd.DataFrame(dashboard["data"])[["date", "high"]]
    tail = tail.loc[tail["date"].between("2021-01-08", "2021-09-23")].copy()
    tail["date"] = pd.to_datetime(tail["date"], format="%Y-%m-%d")
    tail["high"] = pd.to_numeric(tail["high"], errors="raise")
    vxo = pd.concat([archive, tail])

    vstoxx_pages = []
    for page in json.loads((HERE / "vstoxx_downloads.json").read_text()):
        data = source_bytes(args.cache, page["raw_file"], page["url"], args.download)
        if b"A0C3QF" not in data.splitlines()[0] or b"Eurex" not in data.splitlines()[0]:
            raise ValueError(f"Unexpected instrument in {page['raw_file']}")
        frame = pd.read_csv(io.BytesIO(data), encoding="latin1", sep=";", decimal=",", skiprows=2)
        frame = frame.rename(columns={"Datum": "date", "Hoch": "high"})[["date", "high"]]
        frame["date"] = pd.to_datetime(frame["date"], format="%d.%m.%Y")
        vstoxx_pages.append(frame)
    vstoxx = pd.concat(vstoxx_pages)

    series = [("VIX.csv", vix, "%.17g", "vix_through_nov10"),
              ("VXO_complete.csv", vxo, "%.17g", "vxo_discontinuation"),
              ("VSTOXX_comdirect.csv", vstoxx, "%.4f", "vstoxx_comdirect")]
    verified = {}
    for filename, frame, fmt, run_id in series:
        frame = frame.sort_values("date")
        spec = evidence["refresh"][run_id]
        if len(frame) != spec["rows"] or not frame["date"].is_unique:
            raise ValueError(f"{filename}: unexpected observation count or duplicate dates")
        data = frame.to_csv(index=False, lineterminator="\n", float_format=fmt, date_format="%Y-%m-%d").encode()
        if hashlib.sha256(data).hexdigest() != spec["input_file_sha256"]:
            raise ValueError(f"{filename}: input differs from the archived snapshot; inspect source revisions and the parser")
        verified[filename] = data
    output.mkdir(parents=True, exist_ok=True)
    for filename, data in verified.items():
        (output / filename).write_bytes(data)
        print(f"{filename}: {hashlib.sha256(data).hexdigest()}")


if __name__ == "__main__":
    main()
