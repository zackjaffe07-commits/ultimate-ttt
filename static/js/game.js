const socket = io();

socket.emit("join", { room: ROOM });

// --- Sound Effects ---
const sounds = {
    place: new Audio('/static/sounds/place.mp3'),
    win: new Audio('/static/sounds/win.mp3'),
    gameWin: new Audio('/static/sounds/game-win.mp3'),
    chat: new Audio('/static/sounds/chat.mp3')
};
function playSound(sound) {
    sounds[sound].volume = 0.5;
    sounds[sound].currentTime = 0;
    sounds[sound].play().catch(e => console.log("Sound play failed:", e));
}

// --- State Variables ---
let mySymbol = null;
let myUsername = null;
let isSpectator = false;
let gameEnded = false;
let lastWinners = Array(9).fill(null);

// --- DOM Elements ---
const boardDiv = document.getElementById("board");
const status = document.getElementById("status");
const playerText = document.getElementById("player");
const actionBtn = document.getElementById("action");
const postGameDiv = document.getElementById("post-game-actions");
const spectatorList = document.getElementById("spectator-list");
const chatMessages = document.getElementById("chat-messages");
const chatInput = document.getElementById("chat-input");
const sendChatBtn = document.getElementById("send-chat-btn");
const muteOpponentCheck = document.getElementById("mute-opponent");
const muteSpectatorsCheck = document.getElementById("mute-spectators");

// --- Socket Listeners ---
socket.on('connect', () => {
    socket.emit("join", { room: ROOM });
});

socket.on("assign", s => { mySymbol = s; playerText.textContent = `You are ${s}`; });
socket.on("spectator", () => { isSpectator = true; playerText.textContent = "You are a spectator"; if(actionBtn) actionBtn.style.display = "none"; });
socket.on("state", draw);

socket.on("spectatorList", data => {
    spectatorList.innerHTML = "";
    if (data.spectators.length > 0) {
        data.spectators.forEach(name => {
            const li = document.createElement("li");
            li.textContent = name;
            spectatorList.appendChild(li);
        });
    } else {
        spectatorList.innerHTML = "<li>No spectators yet.</li>";
    }
});

function renderMessage(data) {
    const isMyMsg = data.username === myUsername;
    const isSpectatorMsg = data.is_spectator;
    const isOpponentMsg = !isMyMsg && !isSpectatorMsg;

    if (isOpponentMsg && muteOpponentCheck.checked) return;
    if (isSpectatorMsg && muteSpectatorsCheck.checked) return;

    if (!isMyMsg) playSound('chat');

    const msgDiv = document.createElement("div");
    msgDiv.classList.add("chat-message");

    const userSpan = document.createElement("span");
    userSpan.className = "username";
    userSpan.textContent = data.username;

    msgDiv.appendChild(userSpan);

    if (data.is_spectator) {
        const tagSpan = document.createElement("span");
        tagSpan.className = "spectator-tag";
        tagSpan.textContent = "Spectator";
        msgDiv.appendChild(tagSpan);
    }

    msgDiv.append(`: ${data.message}`);
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

socket.on("chatMessage", renderMessage);

socket.on("chatHistory", data => {
    chatMessages.innerHTML = ''; // Clear chat on receiving history
    data.history.forEach(renderMessage);
});

socket.on("rematchStarted", () => {
    if (isSpectator) return;
    gameEnded = false;
    lastWinners = Array(9).fill(null);
    if(actionBtn) {
        actionBtn.style.display = "inline-block";
        actionBtn.textContent = "Start";
    }
    postGameDiv.style.display = "none";
});

// --- UI Handlers ---
function sendChatMessage() {
    const message = chatInput.value;
    if (message.trim()) {
        socket.emit('chat', { room: ROOM, message: message });
        chatInput.value = '';
    }
}
sendChatBtn.onclick = sendChatMessage;
chatInput.onkeydown = (e) => { if (e.key === 'Enter') sendChatMessage(); };

if(actionBtn) {
    actionBtn.onclick = () => {
        if (isSpectator) return;
        if (actionBtn.textContent === "Start") {
            socket.emit("ready", { room: ROOM });
            actionBtn.textContent = "Resign";
        } else if (!gameEnded) {
            socket.emit("resign", { room: ROOM, symbol: mySymbol });
        }
    };
}

document.getElementById('rematch-btn').onclick = () => {
    socket.emit("rematch", { room: ROOM });
};

document.getElementById('home-btn').onclick = () => {
    window.location.href = "/home";
};

// --- Main Draw Function ---
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
        if (!gameEnded) {
            playSound('gameWin');
        }
        gameEnded = true;
        if (!isSpectator) {
            actionBtn.style.display = "none";
            postGameDiv.style.display = "flex";
        }
        status.textContent = state.gameWinner === "D" ? "Draw!" : `${state.gameWinner} wins!`;
    } else {
        status.textContent = `Turn: ${state.player}`;
    }

    for (let b = 0; b < 9; b++) {
        const mini = document.createElement("div");
        mini.className = "mini-board";

        if (state.winners[b] && state.winners[b] !== "D") {
            if (lastWinners[b] !== state.winners[b]) {
                playSound('win');
            }
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
                    playSound('place');
                    socket.emit("move", { room: ROOM, board: b, cell: c });
                }
            };
            mini.appendChild(cell);
        }
        boardDiv.appendChild(mini);
    }
    lastWinners = [...state.winners];
}
