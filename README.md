# daily-report-bot

daily-report-bot は、ホームサーバーの運用状況と開発活動を集計して Slack に通知するアプリです。

このアプリは 1アプリ1コンテナで動かします。Slack / worker / wrapper はコード上で責務分離しますが、コンテナは分割しません。

## 目的

- ジョブ実行記録 (`job_runs`) の集計と日次成功率
- GitHub API による commit 集計
- ディスク / メモリ / load average の server metrics
- 日次 / 週次レポートの生成
- Slack `#server-report` 固定パネルでのレポート参照
- Slack `#server-alert` への重要通知 (このフェーズでは関数のみ)

## GitHub commit 集計

GitHub API を使います。ローカル `git log` には依存しません。

- token は `GITHUB_TOKEN` 環境変数で受け取り、コードに値を書きません
- 対象リポジトリは `DAILY_REPORT_REPOSITORIES` をカンマ区切りで指定します
  - 例: `<owner>/life-bot,<owner>/ai-feed-bot,<owner>/daily-report-bot,<owner>/homeserver`
- token 未設定時は commit 集計を skip し、`github.commit.failed` イベントを記録します
- アプリ全体は落としません

## run-and-log wrapper

cron / 単発ジョブの結果を `job_runs` に記録するラッパーです。

```bash
python scripts/run-and-log.py backup-life-db -- /scripts/backup-life-db.sh
```

`--` の前にジョブ名、後ろに実行コマンドを置きます。

記録項目:

- 実行開始時刻 / 終了時刻
- status (`success` / `failed` / `timeout`)
- exit_code
- duration_seconds
- stdout_tail / stderr_tail (末尾のみ保存し肥大化しない)

DB は `DAILY_REPORT_DB_PATH` を使います。

## job_runs の考え方

- 各ジョブの最新成功率を計算するための一次ソース
- Slack `#server-report` 固定パネルに集計値を出す
- 直近の `failed` を Slack で参照しやすくする
- データ正本は SQLite。Slack 履歴を正本にしない

## server metrics の範囲

- disk usage は `shutil.disk_usage`
- load average は `os.getloadavg`
- memory usage は `/proc/meminfo` (Linux) 経由
- container status はこのフェーズでは取得しない
- Docker daemon に依存しない
- 取得できない値は `unavailable` として扱う

metrics 取得の失敗でアプリ全体は落としません。

## Slack UI

通常操作は `#server-report` 固定パネルとボタンで行います。
slash command は主 UI にしません。`/report ping` だけが管理疎通確認用に提供されます。

固定パネルの操作:

- 今日のレポート
- 週次レポート
- ジョブ状況
- GitHub活動

action_id:

- `report.today.show`
- `report.week.show`
- `report.jobs.show`
- `report.github.show`

`#server-alert` は重要通知専用です。このフェーズでは alert 通知用の関数のみを用意し、過剰には通知しません。

Slack token / secret はコードや `.env.example` に書きません。

## ローカル起動

```bash
DAILY_REPORT_DB_PATH=/tmp/daily-report.db python -m app.main
```

Slack を有効にする場合:

```bash
DAILY_REPORT_ENABLE_SLACK=true python -m app.main
```

worker を有効にする場合:

```bash
DAILY_REPORT_ENABLE_WORKER=true python -m app.main
```

## 環境変数

- `APP_ENV`
- `LOG_LEVEL`
- `DAILY_REPORT_DB_PATH`
- `DAILY_REPORT_ENABLE_SLACK`
- `DAILY_REPORT_ENABLE_WORKER`
- `DAILY_REPORT_TIMEZONE`
- `DAILY_REPORT_DAILY_HOUR`
- `DAILY_REPORT_DAILY_MINUTE`
- `DAILY_REPORT_WEEKLY_DAY`
- `DAILY_REPORT_WEEKLY_HOUR`
- `DAILY_REPORT_WEEKLY_MINUTE`
- `DAILY_REPORT_REPOSITORIES`
- `GITHUB_TOKEN`
- `SLACK_BOT_TOKEN`
- `SLACK_APP_TOKEN`
- `SLACK_SIGNING_SECRET`
- `SLACK_CHANNEL_SERVER_REPORT`
- `SLACK_CHANNEL_SERVER_ALERT`

secret 実値は `.env.example`、README、コードに書きません。

## DB

実運用時のDB配置想定:

```text
~/homeserver/docker/daily-report-bot/data/daily-report.db
```

ローカルデフォルトは `/data/daily-report.db` です。テストでは `DAILY_REPORT_DB_PATH` で一時 DB を指定します。

## 次フェーズ

次フェーズは homeserver compose 整備です。
