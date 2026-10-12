import json
import tempfile
import unittest
from pathlib import Path

from jobradar.db import DB
from jobradar.models import Job, normalize_employment
from jobradar.rank import score_row
from jobradar.sources import ams, jobsat, karriere, willhaben


class FakeResp:
    def __init__(self, text="", data=None):
        self.text = text
        self._data = data

    def json(self):
        return self._data


class TestNormalize(unittest.TestCase):
    def test_values(self):
        self.assertEqual(normalize_employment("Teilzeit"), "teilzeit")
        self.assertEqual(normalize_employment("Vollzeit"), "vollzeit")
        self.assertEqual(normalize_employment("Teilzeit/Vollzeit"), "beide")
        self.assertEqual(normalize_employment("geringfügig"), "teilzeit")
        self.assertEqual(normalize_employment(""), "unbekannt")


class TestRank(unittest.TestCase):
    rank = {
        "core": ["it", "linux", "python"],
        "employment": {"teilzeit": 40, "beide": 25},
        "weights": {"python": 8, "linux": 7, "leiter": -15},
        "boost": ["teilzeit", "homeoffice"],
        "location": 10,
        "homeoffice": 5,
    }

    def test_teilzeit_boost(self):
        score, reasons = score_row(
            {"title": "IT Support", "employment": "teilzeit", "location": "Graz",
             "summary": "Linux und Python", "company": "X", "salary": ""},
            self.rank, "Graz")
        self.assertGreater(score, 40)
        self.assertTrue(any("Teilzeit" in r for r in reasons))

    def test_penalty(self):
        base, _ = score_row(
            {"title": "IT Support", "employment": "vollzeit", "location": "Graz",
             "summary": "", "company": "X", "salary": ""}, self.rank, "Graz")
        pen, reasons = score_row(
            {"title": "IT Leiter", "employment": "vollzeit", "location": "Graz",
             "summary": "", "company": "X", "salary": ""}, self.rank, "Graz")
        self.assertLess(pen, base)
        self.assertTrue(any("Lücken" in r for r in reasons))


class TestKarriere(unittest.TestCase):
    def test_parse(self):
        item = {"jobsItem": {
            "id": "42", "title": "Dev", "company": {"name": "ACME"},
            "locations": [{"name": "Graz"}], "employmentTypes": "Teilzeit",
            "link": "https://www.karriere.at/jobs/42", "salary": "ab 3000",
            "summary": "Linux", "isHomeOffice": True, "date": "heute"}}
        html = ("<script>window.VUE_INITIAL_STATE = "
                + json.dumps({"jobsSearchList": {"activeItems": {"items": [item]}}})
                + "</script>")
        karriere.get = lambda *a, **k: FakeResp(text=html)
        jobs = karriere.search("IT", {"location": "Graz", "radius_km": 20})
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].uid, "karriere:42")
        self.assertEqual(jobs[0].employment, "teilzeit")
        self.assertTrue(jobs[0].homeoffice)


class TestWillhaben(unittest.TestCase):
    def test_parse(self):
        data = {
            "rowsFound": 1,
            "advertSummaryList": [{
                "id": "99", "description": "Sysadmin",
                "attributes": [
                    {"name": "ORGNAME", "values": ["ACME"]},
                    {"name": "LOCATION", "values": ["Graz"]},
                    {"name": "EMPLOYMENT_TYPE", "values": ["Teilzeit"]},
                ],
            }],
        }
        willhaben.get = lambda *a, **k: FakeResp(data=data)
        jobs = willhaben.search("IT", {"location": "Graz", "max_pages": 1})
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].company, "ACME")
        self.assertEqual(jobs[0].employment, "teilzeit")


class TestJobsAt(unittest.TestCase):
    def test_salary(self):
        self.assertEqual(jobsat._salary(
            {"salary-type": "monatlich", "salary-from": 3000, "salary-to": 4000}),
            "€ 3000 - 4000 monatlich")
        self.assertEqual(jobsat._salary({}), "")

    def test_parse(self):
        data = {"jobs": {"last_page": 1, "data": [{
            "id": 7, "title": "Support", "company": {"name": "ACME"},
            "location": "Graz", "_employment_types": ["Vollzeit"],
            "salary": {}, "snippet": "SQL", "homeoffice": True,
        }]}}
        jobsat.get = lambda *a, **k: FakeResp(data=data)
        jobs = jobsat.search("IT", {"location": "Graz", "max_pages": 1})
        self.assertEqual(jobs[0].uid, "jobsat:7")
        self.assertTrue(jobs[0].homeoffice)


class TestAms(unittest.TestCase):
    def test_sign(self):
        rnd, ts, sig, query = ams._sign("key", "/public/emps/api/search",
                                        {"query": "IT", "page": "1"})
        self.assertEqual(len(sig), 128)
        self.assertEqual(len(rnd), 16)
        self.assertTrue(ts.isdigit())
        self.assertEqual(query, "page=1&query=IT")


class TestDB(unittest.TestCase):
    def test_upsert_preserves_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = DB(Path(tmp) / "t.db")
            job = Job(source="s", source_id="1", title="T", company="C")
            self.assertTrue(db.upsert(job))
            self.assertFalse(db.upsert(job))
            db.set_status(job.uid, "beworben")
            job.title = "T2"
            db.upsert(job)
            self.assertEqual(db.get(job.uid)["title"], "T2")
            self.assertEqual(db.get(job.uid)["status"], "beworben")


if __name__ == "__main__":
    unittest.main()
