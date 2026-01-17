.PHONY: push

push:
	git add .
	git commit -m "Auto-commit from Makefile"
	git push

tmux:
	@tmux has-session -t arbitrage 2>/dev/null || \
	tmux new-session -d -s arbitrage \; split-window -h \; split-window -v \; select-pane -t 0 \; split-window -v \; select-layout tiled
	@tmux attach-session -t arbitrage
