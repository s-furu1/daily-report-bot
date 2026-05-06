from __future__ import annotations


PANEL_ACTION_IDS = {
    "report.today.show",
    "report.week.show",
    "report.jobs.show",
    "report.github.show",
}


def server_report_panel_blocks(
    *,
    today_success_rate_text: str,
    today_commit_count_text: str,
    latest_failed_job_text: str,
) -> list[dict]:
    return [
        {"type": "header", "text": {"type": "plain_text", "text": "Server Report"}},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"今日のジョブ成功率: {today_success_rate_text}\n"
                    f"今日のcommit数: {today_commit_count_text}\n"
                    f"最新失敗job: {latest_failed_job_text}"
                ),
            },
        },
        {
            "type": "actions",
            "elements": [
                _button("今日のレポート", "report.today.show"),
                _button("週次レポート", "report.week.show"),
                _button("ジョブ状況", "report.jobs.show"),
                _button("GitHub活動", "report.github.show"),
            ],
        },
    ]


def report_message_blocks(title: str, body_text: str) -> list[dict]:
    return [
        {"type": "header", "text": {"type": "plain_text", "text": title}},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"```\n{body_text}\n```"},
        },
    ]


def _button(text: str, action_id: str) -> dict:
    return {
        "type": "button",
        "text": {"type": "plain_text", "text": text},
        "action_id": action_id,
    }
