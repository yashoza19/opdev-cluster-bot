"""Unit tests for config and identity helpers."""

from opdev_cluster_bot.config import Settings, _bool, _csv
from opdev_cluster_bot.identity import is_authorized, owner_annotations


def test_bool_parsing():
    assert _bool("true") is True
    assert _bool("yes") is True
    assert _bool("0") is False
    assert _bool(None, True) is True


def test_csv_parsing():
    assert _csv("a, b, c") == ["a", "b", "c"]
    assert _csv("") == []
    assert _csv(None) == []


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("ADMIN_SLACK_GROUP_IDS", "S1,S2")
    s = Settings.from_env()
    assert s.aws_region == "us-west-2"
    assert s.dry_run is True
    assert s.admin_slack_group_ids == ["S1", "S2"]


def test_owner_annotations():
    assert owner_annotations("U123", None) == {"opdev.io/owner-slack-id": "U123"}
    assert owner_annotations("U123", "a@b.com")["opdev.io/owner-email"] == "a@b.com"


def test_is_authorized_owner():
    settings = Settings()
    assert is_authorized(actor_slack_id="U1", owner_slack_id="U1", settings=settings) is True
    assert is_authorized(actor_slack_id="U2", owner_slack_id="U1", settings=settings) is False


def test_is_authorized_admin_group():
    settings = Settings(admin_slack_group_ids=["SADMIN"])

    class FakeClient:
        def usergroups_users_list(self, *, usergroup: str):
            assert usergroup == "SADMIN"
            return {"users": ["UADMIN"]}

    assert (
        is_authorized(
            actor_slack_id="UADMIN",
            owner_slack_id="UOTHER",
            settings=settings,
            client=FakeClient(),
        )
        is True
    )
    assert (
        is_authorized(
            actor_slack_id="USTRANGER",
            owner_slack_id="UOTHER",
            settings=settings,
            client=FakeClient(),
        )
        is False
    )
