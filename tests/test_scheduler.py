from __future__ import annotations

from types import SimpleNamespace

from turritopsis.scheduler import install_schedule, remove_schedule, show_schedule


def test_cron_schedule_is_path_scoped_idempotent_and_removable(data_path, monkeypatch):
    state = {"crontab": "15 1 * * * /usr/local/bin/unrelated\n"}

    monkeypatch.setattr("turritopsis.scheduler.platform.system", lambda: "Linux")
    monkeypatch.setattr(
        "turritopsis.scheduler.shutil.which",
        lambda name: "/usr/bin/crontab" if name == "crontab" else "/usr/local/bin/turritopsis",
    )

    def run(argv, *, text, capture_output, check, input=None):
        if argv == ["crontab", "-l"]:
            return SimpleNamespace(returncode=0, stdout=state["crontab"], stderr="")
        assert argv == ["crontab", "-"]
        state["crontab"] = input
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("turritopsis.scheduler.subprocess.run", run)

    result = install_schedule(data_path, "0 3 * * *", "cheap-model", 14)
    assert result["installed"] is True
    assert state["crontab"].count("# BEGIN TURRITOPSIS") == 1
    assert "0 3 * * *" in state["crontab"]
    assert "--model cheap-model" in state["crontab"]
    assert "unrelated" in state["crontab"]

    install_schedule(data_path, "30 4 * * *", "cheaper-model", 14)
    assert state["crontab"].count("# BEGIN TURRITOPSIS") == 1
    assert show_schedule(data_path)["entry"].startswith("30 4 * * *")

    assert remove_schedule(data_path)["removed"] is True
    assert "TURRITOPSIS" not in state["crontab"]
    assert "unrelated" in state["crontab"]
