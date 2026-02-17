const socket = io();

// The server will now manage the session, so we just need to join.
// The SID is handled on the server via the request context.
socket.emit("join", { room: ROOM });

let mySymbol = null;
let isSpectator = false;
let gameEnded = false;
let rematchClicked = false;

const boardDiv = document.getElementById("board");
const status = document.getElementById("status");
const playerText = document.getElementById("player");
const actionBtn = document.getElementById("action");
const spectatorCount = document.createElement("div");
spectatorCount.id = "spectator-count";
document.body.appendChild(spectatorCount);


socket.on("assign", s => {
    mySymbol = s;
    playerText.textContent = `You are ${s}`;
});

socket.on("spectator", () => {
    isSpectator = true;
    playerText.textContent = "You are a spectator";
    if(actionBtn) actionBtn.style.display = "none";
});

socket.on("spectatorCount", count => {
    spectatorCount.textContent = `Spectators: ${count}`;
});


if(actionBtn) {
    actionBtn.onclick = () => {
        if (isSpectator) return;

        if (actionBtn.textContent === "Start") {
            socket.emit("ready", { room: ROOM });
            actionBtn.textContent = "Resign";
        } else if (!gameEnded) {
            socket.emit("resign", { room: ROOM, symbol: mySymbol });
        } else if (gameEnded && !rematchClicked) {
            rematchClicked = true;
            socket.emit("rematch", { room: ROOM });
            actionBtn.disabled = true;
        }
    };
}

socket.on("state", draw);

socket.on("rematchStarted", () => {
    if (isSpectator) return;
    rematchClicked = false;
    gameEnded = false;
    if(actionBtn) {
        actionBtn.disabled = false;
        actionBtn.textContent = "Start";
    }
});

function draw(state) {
    boardDiv.innerHTML = "";

    if (!state.started) {
        status.textContent = "Waiting for both players…";
        return;
    }

    if (!isSpectator && actionBtn && !state.gameWinner) {
        actionBtn.textContent = "Resign";
    }

    if (state.gameWinner) {
        gameEnded = true;
        if (!isSpectator && actionBtn) {
            actionBtn.textContent = "Rematch";
            actionBtn.disabled = false;
        }
        status.textContent =
            state.gameWinner === "D"
            ? "Draw!"
            : `${state.gameWinner} wins!`;
    } else {
        status.textContent = `Turn: ${state.player}`;
    }

    for (let b = 0; b < 9; b++) {
        const mini = document.createElement("div");
        mini.className = "mini-board";

        if (state.winners[b] && state.winners[b] !== "D") {
            mini.classList.add(`won-${state.winners[b]}`);
            const overlay = document.createElement("span");
            overlay.className = `overlay ${state.winners[b]}`;
            overlay.textContent = state.winners[b];
            mini.appendChild(overlay);
        }

        if (state.forced === b) mini.classList.add("forced");

        for (let c = 0; c < 9; c++) {
            const cell = document.createElement("div");
            const symbol = state.boards[b][c];
            cell.className = "cell";
            if (symbol) {
                cell.classList.add(symbol);
                cell.textContent = symbol;
            }

            cell.onclick = () => {
                if (!isSpectator && mySymbol === state.player && !state.gameWinner) {
                    socket.emit("move", { room: ROOM, board: b, cell: c });
                }
            };
            mini.appendChild(cell);
        }
        boardDiv.appendChild(mini);
    }
}
