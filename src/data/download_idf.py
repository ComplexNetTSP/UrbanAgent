"""Download core Île-de-France datasets and record provenance.

Usage:
    python src/data/download_idf.py
    python src/data/download_idf.py --only osm,gtfs
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = REPO_ROOT / "dataset" / "ile_de_france"

DATASETS = {
    "osm": {
        "directory": "osm",
        "filename": "ile-de-france-latest.osm.pbf",
        "url": "https://download.geofabrik.de/europe/france/ile-de-france-latest.osm.pbf",
        "source_page": "https://download.geofabrik.de/europe/france/ile-de-france.html",
        "source": "OpenStreetMap via Geofabrik",
        "source_type": "regional PBF bulk download",
        "dataset_version": "latest at retrieval time",
        "license": "OpenStreetMap ODbL 1.0",
        "geographic_coverage": "Île-de-France",
        "temporal_coverage": "latest extract at retrieval time",
    },
    "gtfs": {
        "directory": "gtfs_idfm",
        "filename": "IDFM-gtfs.zip",
        "url": "https://eu.ftp.opendatasoft.com/stif/GTFS/IDFM-gtfs.zip",
        "source_page": "https://data.iledefrance-mobilites.fr/explore/dataset/offre-horaires-tc-gtfs-idfm/",
        "source": "Île-de-France Mobilités",
        "source_type": "official GTFS bulk download",
        "dataset_version": "current feed at retrieval time",
        "license": "Licence Mobilité",
        "geographic_coverage": "Île-de-France public transport network",
        "temporal_coverage": "planned service for the published future period",
        "extract": True,
    },
    "iris": {
        "directory": "iris_2023",
        "filename": "reference_IRIS_geo2023.zip",
        "url": "https://www.insee.fr/fr/statistiques/fichier/7708995/reference_IRIS_geo2023.zip",
        "source_page": "https://www.insee.fr/fr/information/7708995",
        "source": "INSEE / IGN",
        "source_type": "official IRIS geography bulk download",
        "dataset_version": "IRIS geography 2023",
        "license": "INSEE / IGN open data; see source page",
        "geographic_coverage": "France, filtered to Île-de-France during processing",
        "temporal_coverage": "geography at 2023-01-01",
        "extract": True,
    },
    "population": {
        "directory": "insee_iris_2021/population",
        "filename": "base-ic-evol-struct-pop-2021_csv.zip",
        "url": "https://www.insee.fr/fr/statistiques/fichier/8268806/base-ic-evol-struct-pop-2021_csv.zip",
        "source_page": "https://www.insee.fr/fr/statistiques/8268806",
        "source": "INSEE Recensement de la population",
        "source_type": "official IRIS CSV bulk download",
        "dataset_version": "RP 2021",
        "license": "INSEE open data; see source page",
        "geographic_coverage": "France hors Mayotte; filter to Île-de-France during processing",
        "temporal_coverage": "2021, geography at 2023-01-01",
        "extract": True,
    },
    "activity": {
        "directory": "insee_iris_2021/activity",
        "filename": "base-ic-activite-residents-2021_csv.zip",
        "url": "https://www.insee.fr/fr/statistiques/fichier/8268843/base-ic-activite-residents-2021_csv.zip",
        "source_page": "https://www.insee.fr/fr/statistiques/8268843",
        "source": "INSEE Recensement de la population",
        "source_type": "official IRIS CSV bulk download",
        "dataset_version": "RP 2021",
        "license": "INSEE open data; see source page",
        "geographic_coverage": "France hors Mayotte; filter to Île-de-France during processing",
        "temporal_coverage": "2021, geography at 2023-01-01",
        "extract": True,
    },
    "housing": {
        "directory": "insee_iris_2021/housing",
        "filename": "base-ic-logement-2021_csv.zip",
        "url": "https://www.insee.fr/fr/statistiques/fichier/8268838/base-ic-logement-2021_csv.zip",
        "source_page": "https://www.insee.fr/fr/statistiques/8268838",
        "source": "INSEE Recensement de la population",
        "source_type": "official IRIS CSV bulk download",
        "dataset_version": "RP 2021",
        "license": "INSEE open data; see source page",
        "geographic_coverage": "France hors Mayotte; filter to Île-de-France during processing",
        "temporal_coverage": "2021, geography at 2023-01-01",
        "extract": True,
    },
    "sirene": {
        "directory": "sirene_geolocation",
        "filename": "sirene_geolocation.parquet",
        "url": "https://www.data.gouv.fr/api/1/datasets/r/672007af-0146-491f-835c-8314d63fa44e",
        "source_page": "https://www.data.gouv.fr/datasets/geolocalisation-des-etablissements-du-repertoire-sirene-pour-les-etudes-statistiques",
        "source": "INSEE SIRENE",
        "source_type": "official stable resource URL, Parquet",
        "dataset_version": "latest monthly release at retrieval time",
        "license": "Licence Ouverte 2.0",
        "geographic_coverage": "France hors Mayotte; filter to Île-de-France during processing",
        "temporal_coverage": "latest monthly establishment geolocation snapshot",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> str:
    if destination.exists():
        print(f"skip  {destination} (already exists)")
        return url

    temporary = destination.with_name(destination.name + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "UrbanGraphPlanner/0.1"})
    destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"get   {url}")
    try:
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as file:
            total = int(response.headers.get("Content-Length", 0))
            received = 0
            next_report = 100 * 1024 * 1024
            while chunk := response.read(1024 * 1024):
                file.write(chunk)
                received += len(chunk)
                if received >= next_report:
                    suffix = f" / {total / 1024**2:.0f} MiB" if total else ""
                    print(f"      {received / 1024**2:.0f} MiB{suffix}")
                    next_report += 100 * 1024 * 1024
        temporary.replace(destination)
        return response.url
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def extract(archive: Path, target: Path) -> list[str]:
    target.mkdir(parents=True, exist_ok=True)
    if not any(target.iterdir()):
        print(f"unzip {archive} -> {target}")
        with zipfile.ZipFile(archive) as file:
            bad_file = file.testzip()
            if bad_file:
                raise ValueError(f"corrupt ZIP member: {bad_file}")
            file.extractall(target)
    else:
        print(f"skip  extraction {target} (already contains files)")
    return sorted(str(path.relative_to(target)) for path in target.rglob("*") if path.is_file())


def save_metadata(spec: dict[str, object], root: Path, destination: Path, resolved_url: str, extracted: list[str]) -> Path:
    metadata = {
        key: value
        for key, value in spec.items()
        if key not in {"directory", "filename", "extract"}
    }
    metadata.update(
        {
            "retrieved_at": datetime.now(UTC).isoformat(),
            "resolved_url": resolved_url,
            "file": str(destination.relative_to(root)),
            "size_bytes": destination.stat().st_size,
            "sha256": sha256(destination),
            "extracted_files": extracted,
        }
    )
    path = destination.parent / "metadata.json"
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="comma-separated dataset names; default: all")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="target dataset directory")
    args = parser.parse_args()

    selected = list(DATASETS)
    if args.only:
        selected = [name.strip() for name in args.only.split(",") if name.strip()]
        unknown = sorted(set(selected) - DATASETS.keys())
        if unknown:
            parser.error(f"unknown dataset(s): {', '.join(unknown)}")

    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, object]] = []
    for name in selected:
        spec = DATASETS[name]
        destination = root / str(spec["directory"]) / str(spec["filename"])
        resolved_url = download(str(spec["url"]), destination)
        extracted = extract(destination, destination.parent / "extracted") if spec.get("extract") else []
        metadata = save_metadata(spec, root, destination, resolved_url, extracted)
        manifest.append(
            {
                "name": name,
                "metadata": str(metadata.relative_to(root)),
                "file": str(destination.relative_to(root)),
                "size_bytes": destination.stat().st_size,
                "sha256": sha256(destination),
            }
        )

    (root / "manifest.json").write_text(
        json.dumps(
            {"study_area": "Île-de-France", "created_at": datetime.now(UTC).isoformat(), "datasets": manifest},
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(f"done  {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
