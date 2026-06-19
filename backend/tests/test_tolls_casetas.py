"""
Backend tests for the casetas/tolls pricing feature (Jan 2026).

Covers:
- /api/dimensions still returns 7 dims including 'tolls' (label 'Casetas').
- /api/vehicle-classes returns 8 categories + default 'auto'.
- /api/route CDMX -> Querétaro with tolls=min returns tolls>0 and tolls_detail
  with named real casetas (e.g. Tepotzotlán) including required fields.
- Vehicle category scaling: moto < auto < camion5 toll total.
- Omitted vehicle_class still works (defaults to auto, no validation failure).
- Other 6 dimensions still work; best.segments include both 'A*' and 'Manhattan'.
- Critical zones still work alongside the new feature.
- /api/geocode still works for 'Tepeji del Rio'.
"""
import os
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

CDMX = {"lat": 19.4326, "lng": -99.1332}
QRO = {"lat": 20.5888, "lng": -100.3899}


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _post_route(client, payload, retries=2):
    """POST /api/route with one retry to soak up flaky upstream (Overpass/OSRM)."""
    last = None
    for _ in range(retries):
        r = client.post(f"{BASE_URL}/api/route", json=payload, timeout=120)
        last = r
        if r.status_code == 200:
            return r
        if r.status_code == 502:
            continue
    return last


class TestDimensionsTolls:
    def test_dimensions_includes_tolls(self, client):
        r = client.get(f"{BASE_URL}/api/dimensions")
        assert r.status_code == 200
        dims = r.json()["dimensions"]
        assert len(dims) == 7
        keys = {d["key"] for d in dims}
        assert "tolls" in keys
        tolls = next(d for d in dims if d["key"] == "tolls")
        assert tolls["label"] == "Casetas"
        assert tolls["unit"] == "MXN"


class TestVehicleClasses:
    def test_vehicle_classes_endpoint(self, client):
        r = client.get(f"{BASE_URL}/api/vehicle-classes")
        assert r.status_code == 200
        data = r.json()
        assert data["default"] == "auto"
        vcs = data["vehicle_classes"]
        keys = {v["key"] for v in vcs}
        expected = {"moto", "auto", "autobus", "camion2", "camion3", "camion4", "camion5", "camion6"}
        assert keys == expected
        assert len(vcs) == 8
        # required fields
        for v in vcs:
            assert "label" in v and "axes" in v


class TestRouteTollsCDMXQro:
    def test_tolls_detail_named_casetas(self, client):
        payload = {
            "origin": CDMX, "destination": QRO,
            "dimensions": {"tolls": "min"},
            "critical_zones": [],
            "vehicle_class": "auto",
        }
        r = _post_route(client, payload)
        if r.status_code == 502:
            pytest.skip(f"OSRM unreachable: {r.text[:200]}")
        assert r.status_code == 200, r.text
        data = r.json()
        best = data["best"]
        # Tolls must be > 0
        assert best["metrics"]["tolls"] > 0, f"tolls={best['metrics']['tolls']}"
        details = best["tolls_detail"]
        assert isinstance(details, list)
        if not details:
            pytest.skip("Overpass returned no booths this run; cannot validate named casetas")
        # At least one named real caseta (non-estimated) — expect Tepotzotlán on the corridor
        real = [d for d in details if not d.get("estimated", False)]
        assert real, f"no real (non-estimated) casetas matched, details={details}"
        names = " | ".join(d["name"] for d in real).lower()
        assert "tepotzotlán" in names or "tepotzotlan" in names or "palmillas" in names or "polotitlán" in names, names
        # Required fields on each detail item
        for d in details:
            for f in ("name", "autopista", "price", "estimated", "lat", "lng"):
                assert f in d, f"missing field {f} in {d}"
            assert isinstance(d["price"], (int, float)) and d["price"] >= 0

    def test_vehicle_class_scaling(self, client):
        """moto < auto < camion5 for total toll cost on the same route."""
        results = {}
        for vc in ("moto", "auto", "camion5"):
            payload = {
                "origin": CDMX, "destination": QRO,
                "dimensions": {"tolls": "min"},
                "vehicle_class": vc,
            }
            r = _post_route(client, payload)
            if r.status_code == 502:
                pytest.skip(f"OSRM unreachable for vc={vc}")
            assert r.status_code == 200, r.text
            results[vc] = r.json()["best"]["metrics"]["tolls"]
        # If no booths matched at all this run, fallback wouldn't reflect scaling — skip
        if results["auto"] == 0:
            pytest.skip("no toll data (Overpass empty); cannot validate scaling")
        assert results["moto"] < results["auto"] < results["camion5"], results

    def test_omitted_vehicle_class_defaults_auto(self, client):
        payload = {
            "origin": CDMX, "destination": QRO,
            "dimensions": {"tolls": "min"},
            # vehicle_class intentionally omitted
        }
        r = _post_route(client, payload)
        if r.status_code == 502:
            pytest.skip("OSRM unreachable")
        # Must NOT 422 the validation
        assert r.status_code == 200, r.text


class TestRouteOtherDimensionsStillWork:
    def test_time_distance_dims_have_astar_and_manhattan(self, client):
        payload = {
            "origin": CDMX, "destination": QRO,
            "dimensions": {"time": "min", "distance": "min"},
        }
        r = _post_route(client, payload)
        if r.status_code == 502:
            pytest.skip("OSRM unreachable")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "best" in data and "alternatives" in data and "manhattan_refinement" in data
        assert "explanation" in data and len(data["explanation"]) > 0
        algos = [s["algorithm"] for s in data["best"]["segments"]]
        assert "A*" in algos and "Manhattan" in algos, algos
        # Metrics should be populated and tolls present even when not the chosen dim
        for k in ("time", "distance", "tolls", "fuel", "operator", "critical", "elevation", "score"):
            assert k in data["best"]["metrics"]


class TestRouteCriticalZonesStillWork:
    def test_critical_zone_on_route_does_not_break(self, client):
        # Put a critical zone roughly midway on the corridor
        zone = {"lat": 19.85, "lng": -99.33}
        payload = {
            "origin": CDMX, "destination": QRO,
            "dimensions": {"time": "min"},
            "critical_zones": [zone],
            "vehicle_class": "auto",
        }
        r = _post_route(client, payload)
        if r.status_code == 502:
            pytest.skip("OSRM unreachable")
        assert r.status_code == 200, r.text
        data = r.json()
        # Just verify a valid response structure (avoid-areas didn't crash)
        assert "best" in data
        assert "Evitando" in data["explanation"] or "No fue posible evitar" in data["explanation"]


class TestGeocodeStillWorks:
    def test_geocode_tepeji(self, client):
        r = client.get(f"{BASE_URL}/api/geocode", params={"q": "Tepeji del Rio"}, timeout=20)
        if r.status_code in (502, 503):
            pytest.skip(f"geocode upstream unavailable: {r.status_code}")
        assert r.status_code == 200, r.text
        results = r.json().get("results", [])
        assert len(results) >= 1
        joined = " | ".join(x["display_name"] for x in results).lower()
        assert "tepeji" in joined
