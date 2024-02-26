#!/bin/bash

create_tmux_session() {
    local session_name="$1"
    local command1="$2"
    local command2="$3"

    tmux has-session -t "$session_name" 2>/dev/null
    if [ $? == 0 ]; then
        tmux kill-session -t "$session_name"
    fi

    # Split horizontally to get 2 panels
    tmux new-session -d -s "$session_name"
    tmux split-window -h -t "$session_name"

    # tmux send-keys -t {session}:{window}.{pane} {keys}
    tmux send-keys -t "$session_name:0.0" "$command1" C-m
    tmux send-keys -t "$session_name:0.1" "$command2" C-m

    tmux attach-session -t "$session_name"
}

bot_session="bot"
start_bot="source .venv/bin/activate && nb run"
start_lagrange="cd ~/Lagrange.Core/ && dotnet run --project Lagrange.OneBot --framework net8.0"

start() {
    create_tmux_session "$bot_session" "$start_bot" "$start_lagrange"
}

stop() {
    # kill session if it exists
    tmux has-session -t "$bot_session" 2>/dev/null
    if [ $? == 0 ]; then
        tmux kill-session -t "$bot_session"
    fi
}

restart() {
    # only restart the bot, not the lagrange
    tmux has-session -t "$bot_session" 2>/dev/null
    if [ $? != 0 ]; then
        echo "Bot is not running"
        exit 1
    fi

    tmux send-keys -t "$bot_session:0.0" C-c
    tmux send-keys -t "$bot_session:0.0" "$start_bot" C-m

    tmux attach-session -t "$bot_session"
}

case "$1" in
start)
    start
    ;;
stop)
    stop
    ;;
restart)
    restart
    ;;
*)
    echo "Usage: $0 {start|stop}"
    exit 1
    ;;
esac
