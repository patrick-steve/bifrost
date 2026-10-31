"""Sealed outcome fields never reach an agent or coordinator view (static part)."""
from dn import config
from dn.consensus_log import canonical_json


def test_views_have_no_sealed_columns(showcase):
    views = [canonical_json(showcase.for_coordinator())]
    for r in config.ROLES:
        v = showcase.for_agent(r)
        views.append(canonical_json({"public": v["public"], "private": v["private"]}))
    for text in views:
        for col in config.SEALED_COLUMNS:
            assert col not in text
            assert col.lower() not in text
