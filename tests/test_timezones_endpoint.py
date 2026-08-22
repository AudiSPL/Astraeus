"""HTTP contract for GET /v1/timezones."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_endpoint_requires_full_datetime_when_at_is_supplied():
    r = client.get('/v1/timezones', params={'at': '2026-03-29'})
    assert r.status_code == 422
    assert 'date and time' in r.json()['detail']


def test_endpoint_rejects_aware_at_value():
    r = client.get('/v1/timezones', params={'at': '2026-08-22T12:00:00+02:00'})
    assert r.status_code == 422
    assert 'naive local datetime' in r.json()['detail']


def test_endpoint_returns_both_tzdata_version_identifiers():
    r = client.get('/v1/timezones', params={'at': '2026-08-22T12:00', 'q': 'belgrade'})
    assert r.status_code == 200
    body = r.json()
    assert body['tzdata_package_version']
    assert 'iana_version' in body


def test_endpoint_searches_country_and_returns_resolved_offset():
    r = client.get('/v1/timezones', params={'at': '2026-08-22T12:00', 'q': 'serbia'})
    assert r.status_code == 200
    belgrade = next(e for e in r.json()['timezones'] if e['id'] == 'Europe/Belgrade')
    assert belgrade['offset_label'] == 'GMT+02:00'
    assert belgrade['status'] == 'ok'


def test_endpoint_surfaces_gap_without_changing_chart_calculation_semantics():
    r = client.get('/v1/timezones', params={'at': '2026-03-29T02:30', 'q': 'belgrade'})
    assert r.status_code == 200
    belgrade = r.json()['timezones'][0]
    assert belgrade['id'] == 'Europe/Belgrade'
    assert belgrade['status'] == 'gap'
    assert belgrade['offset_label'] is None


def test_endpoint_surfaces_ambiguous_time_with_two_offsets():
    r = client.get('/v1/timezones', params={'at': '2026-10-25T02:30', 'q': 'belgrade'})
    assert r.status_code == 200
    belgrade = r.json()['timezones'][0]
    assert belgrade['status'] == 'ambiguous'
    assert [x['utc_offset'] for x in belgrade['possible_offsets']] == ['UTC+02:00', 'UTC+01:00']


def test_recommended_zones_are_resolved_and_deduplicated():
    r = client.get('/v1/timezones', params={
        'at': '2026-08-22T12:00',
        'q': 'tokyo',
        'recommended': 'Europe/Belgrade,Europe/Belgrade,Asia/Nicosia',
    })
    assert r.status_code == 200
    assert [e['id'] for e in r.json()['recommended']] == ['Europe/Belgrade', 'Asia/Nicosia']


def test_limit_is_clamped_but_all_zones_are_available():
    r = client.get('/v1/timezones', params={'at': '2026-08-22T12:00', 'limit': 1000})
    assert r.status_code == 200
    assert len(r.json()['timezones']) > 400
