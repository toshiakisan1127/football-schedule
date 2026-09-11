from __future__ import annotations

from copy import deepcopy

import pytest

import validation


def valid_document() -> dict:
    return {
        "schemaVersion": 1,
        "generatedAt": "2026-09-11T02:00:00Z",
        "range": {"from": "2026-09-10", "to": "2026-09-25"},
        "fixtures": [
            {
                "id": "1001",
                "competition": {
                    "id": "epl",
                    "name": "Premier League",
                    "country": "England",
                },
                "home": {"id": "40", "name": "Home FC"},
                "away": {"id": "33", "name": "Away FC"},
                "kickoff": "2026-09-12T06:00:00Z",
                "status": "scheduled",
                "score": None,
            }
        ],
    }


def validate(document: dict) -> None:
    validation.validate_fixture_document(document, competition_ids={"epl", "laliga"})


def test_accepts_valid_document() -> None:
    validate(valid_document())


def test_rejects_unknown_schema_version() -> None:
    document = valid_document()
    document["schemaVersion"] = 2

    with pytest.raises(validation.FixtureDocumentValidationError, match="schemaVersion"):
        validate(document)


def test_rejects_duplicate_fixture_ids() -> None:
    document = valid_document()
    document["fixtures"].append(deepcopy(document["fixtures"][0]))

    with pytest.raises(validation.FixtureDocumentValidationError, match="duplicate fixture id"):
        validate(document)


def test_rejects_unknown_competition() -> None:
    document = valid_document()
    document["fixtures"][0]["competition"]["id"] = "unknown"

    with pytest.raises(validation.FixtureDocumentValidationError, match="not configured"):
        validate(document)


def test_rejects_same_home_and_away_team() -> None:
    document = valid_document()
    document["fixtures"][0]["away"] = {"id": "40", "name": "Home FC"}

    with pytest.raises(validation.FixtureDocumentValidationError, match="same home and away"):
        validate(document)


def test_rejects_fixture_outside_document_range() -> None:
    document = valid_document()
    document["fixtures"][0]["kickoff"] = "2026-09-26T06:00:00Z"

    with pytest.raises(validation.FixtureDocumentValidationError, match="outside the document range"):
        validate(document)


def test_rejects_negative_score() -> None:
    document = valid_document()
    document["fixtures"][0]["score"] = {"home": -1, "away": 0}

    with pytest.raises(validation.FixtureDocumentValidationError, match="non-negative integer"):
        validate(document)


def test_rejects_inconsistent_team_name_for_same_id() -> None:
    document = valid_document()
    second = deepcopy(document["fixtures"][0])
    second["id"] = "1002"
    second["kickoff"] = "2026-09-13T06:00:00Z"
    second["home"]["name"] = "Renamed FC"
    document["fixtures"].append(second)

    with pytest.raises(validation.FixtureDocumentValidationError, match="multiple team names"):
        validate(document)


def test_rejects_unsorted_fixtures() -> None:
    document = valid_document()
    second = deepcopy(document["fixtures"][0])
    second["id"] = "1000"
    second["kickoff"] = "2026-09-11T06:00:00Z"
    document["fixtures"].append(second)

    with pytest.raises(validation.FixtureDocumentValidationError, match="sorted"):
        validate(document)
