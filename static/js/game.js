const socket = io();

// Create or retrieve a persistent session ID
let sid = sessionStorage.getItem("sid");
if (!sid) {
    sid = Math.random().toString(36).slice(2);
    sessionStorage.setItem("sid", sid);
}

socket.emit("join", { room: ROOM, sid });

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
    actionBtn.style.display = "none";
});

socket.on("spectatorCount", count => {
    spectatorCount.textContent = `Spectators: ${count}`;
});


actionBtn.onclick = () => {
    if (isSpectator) return;

    if (actionBtn.textContent === "Start") {
        socket.emit("ready", { room: ROOM, sid });
        actionBtn.textContent = "Resign";
    } else if (!gameEnded) {
        // Resign -> lose
        socket.emit("resign", { room: ROOM, symbol: mySymbol });
    } else if (gameEnded && !rematchClicked) {
        rematchClicked = true;
        socket.emit("rematch", { room: ROOM, sid });
        actionBtn.disabled = true;
    }
};

socket.on("state", draw);

socket.on("rematchStarted", () => {
    if (isSpectator) return;
    rematchClicked = false;
    gameEnded = false;
    actionBtn.disabled = false;
    actionBtn.textContent = "Start";
});

function draw(state) {
    boardDiv.innerHTML = "";

    if (!state.started) {
        status.textContent = "Waiting for both players…";
        return;
    }

    // If game has started, ensure button shows "Resign"
    if (!isSpectator && !state.gameWinner) {
        actionBtn.textContent = "Resign";
    }

    if (state.gameWinner) {
        gameEnded = true;
        if (!isSpectator) {
            actionBtn.textContent = "Rematch";
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
            mini.classList.add("won");
            mini.innerHTML = `<span class="overlay">${state.winners[b]}</span>`;
        }

        if (state.forced === b) mini.classList.add("forced");

        for (let c = 0; c < 9; c++) {
            const cell = document.createElement("div");
            cell.className = "cell";
            cell.textContent = state.boards[b][c] || "";

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