#!/usr/bin/env bash
#
# One monitoring run, driven by launchd (see com.pophunt.monitor.plist).
#
# The point of the pull/push around the run is shared state. GitHub Actions
# runs the same monitor and commits `state.json` to this repo; if the local
# schedule kept its own copy, each scheduler would re-detect the other's
# openings and you would get the same alert twice. So: start from whatever CI
# last pushed, run, push what changed.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

COMMIT_MESSAGE="data: update booking state [skip ci]"

log() {
    printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

GIT_DIR_ABS="$(git rev-parse --absolute-git-dir 2>/dev/null || true)"
if [ -z "$GIT_DIR_ABS" ]; then
    log "ERROR: $REPO_ROOT is not a git repository, and this schedule shares"
    log "ERROR: state with CI through git. Nothing to do."
    exit 1
fi

# The lock lives in .git deliberately: it is the same path no matter who starts
# the run (launchd's TMPDIR need not match your shell's, and a lock at two
# different paths guards nothing), it is scoped to the clone whose state it
# protects, and it stays out of `git status`.
LOCK_DIR="$GIT_DIR_ABS/pop-hunt.run.lock"

# --- lock -------------------------------------------------------------------
#
# A run takes ~95s against a 1800s interval, so overlap needs something to have
# gone wrong — a browser that never exits, or a hand-run alongside the timer.
# One `mkdir` is the atomic primitive here: macOS ships no `flock`.

release_lock() {
    rm -rf "$LOCK_DIR"
}

acquire_lock() {
    # The pid goes in the instant the directory is ours: a lock with no pid in
    # it reads as stale below, so the gap between the two must stay this small.
    if mkdir "$LOCK_DIR" 2>/dev/null; then
        printf '%s\n' "$$" >"$LOCK_DIR/pid"
        return 0
    fi

    # Held, or left behind by a run that was killed before it could clean up.
    # Without the second case a single crash would wedge the schedule silently
    # until someone noticed. (The takeover itself is not airtight: two runs
    # that find the same dead lock in the same instant could both claim it.
    # That needs a crashed run plus two starts in the same millisecond.)
    local holder=""
    if [ -f "$LOCK_DIR/pid" ]; then
        holder="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
    fi

    if [ -n "$holder" ] && kill -0 "$holder" 2>/dev/null; then
        return 1
    fi

    log "clearing a stale lock (pid ${holder:-unknown} is gone)"
    rm -rf "$LOCK_DIR"
    mkdir "$LOCK_DIR" 2>/dev/null || return 1
    printf '%s\n' "$$" >"$LOCK_DIR/pid"
}

if ! acquire_lock; then
    log "another run holds $LOCK_DIR — skipping this interval"
    exit 0
fi
trap release_lock EXIT

log "pop-hunt local run starting in $REPO_ROOT"

# --- environment ------------------------------------------------------------
#
# Absent `.env` is fine: the monitor logs the alert it would have sent and
# skips Telegram, which is a reasonable way to run it.

# Parsed rather than sourced. Sourcing under `set -e` turns one fat-fingered
# line into a run that never happens, and a config file should not be able to
# execute anything.

load_env() {
    local line key value
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%$'\r'}"                 # tolerate CRLF
        line="${line#"${line%%[![:space:]]*}"}"   # strip leading whitespace
        case "$line" in
            '' | '#'*) continue ;;
        esac
        line="${line#export }"
        key="${line%%=*}"
        if [ "$key" = "$line" ]; then
            log "WARNING: ignoring .env line without '=': $line"
            continue
        fi
        key="${key%"${key##*[![:space:]]}"}"      # strip trailing whitespace
        case "$key" in
            '' | *[!A-Za-z0-9_]* | [0-9]*)
                log "WARNING: ignoring .env line with an unusable name: $line"
                continue
                ;;
        esac
        value="${line#*=}"
        case "$value" in
            \"*\") value="${value#\"}"; value="${value%\"}" ;;
            \'*\') value="${value#\'}"; value="${value%\'}" ;;
            *)  # unquoted: trim surrounding whitespace. Quote it if you meant it.
                value="${value#"${value%%[![:space:]]*}"}"
                value="${value%"${value##*[![:space:]]}"}"
                ;;
        esac
        export "$key=$value"
    done <.env
}

if [ -f .env ]; then
    log "loading .env"
    load_env
else
    log "no .env — Telegram alerts will be logged, not sent"
fi

# --- pull -------------------------------------------------------------------
#
# --autostash because `data/` and `state.json` can be dirty here (a previous
# run that wrote but could not push); a plain rebase would refuse to start.

log "pulling latest state from origin"
if git pull --rebase --autostash; then
    log "pull ok"
else
    log "WARNING: pull failed — running against local state, which may be behind CI."
    log "WARNING: if CI has already recorded this opening you may get a duplicate alert."
fi

# --- run --------------------------------------------------------------------

log "running the monitor"
if .venv/bin/python -m pop_hunt.main; then
    log "monitor finished"
else
    status=$?
    log "ERROR: monitor exited $status — not committing"
    exit "$status"
fi

# --- commit and push --------------------------------------------------------
#
# Pathspecs throughout: unlike CI this runs in a repo someone works in, and a
# scheduled job has no business committing whatever else happens to be staged.

git add -- state.json data

if git diff --cached --quiet -- state.json data; then
    log "no data change"
    exit 0
fi

log "committing changed data"
git commit -q -m "$COMMIT_MESSAGE" -- state.json data

if git push; then
    log "pushed"
    exit 0
fi

# Most likely CI pushed between our pull and now.
log "push rejected — rebasing onto origin and retrying once"
if git pull --rebase --autostash && git push; then
    log "pushed on retry"
    exit 0
fi

log "ERROR: push failed twice. The data is committed locally but not on origin,"
log "ERROR: so CI is still working from older state and may re-alert. Sort it out"
log "ERROR: by hand in $REPO_ROOT."
exit 1
