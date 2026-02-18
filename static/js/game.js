const socket = io();

// --- State Variables ---
let mySymbol = null;
let myUsername = null;
let isSpectator = false;
let gameEnded = false;
let lastWinners = Array(9).fill(null);
let gameState = {};

// --- DOM Elements ---
const boardDiv = document.getElementById("board");
const status = document.getElementById("status");
const playerText = document.getElementById("player");
const actionBtn = document.getElementById("action");
const postGameDiv = document.getElementById("post-game-actions");
const rematchBtn = document.getElementById('rematch-btn');
const homeBtn = document.getElementById('home-btn');
const spectatorList = document.getElementById("spectator-list");
const chatMessages = document.getElementById("chat-messages");
const chatInput = document.getElementById("chat-input");
const sendChatBtn = document.getElementById("send-chat-btn");
const muteOpponentCheck = document.getElementById("mute-opponent");
const muteSpectatorsCheck = document.getElementById("mute-spectators");
const victoryModal = document.getElementById("victory-modal");
const victoryText = document.getElementById("victory-text");
const victorySubtext = document.getElementById("victory-subtext");

// --- Sound Effects ---
const sounds = {
    place: new Audio('/static/sounds/place.mp3'),
    win: new Audio('/static/sounds/win.mp3'),
    gameWin: new Audio('/static/sounds/game-win.mp3'),
    gameLose: new Audio('/static/sounds/lose.mp3'),
    chat: new Audio('/static/sounds/chat.mp3')
};
function playSound(sound) {
    sounds[sound].volume = 0.5;
    sounds[sound].currentTime = 0;
    sounds[sound].play().catch(e => console.log("Sound play failed:", e));
}

// --- Socket Listeners ---
socket.on('connect', () => { socket.emit("join", { room: ROOM }); });
socket.on("assign", s => { mySymbol = s; playerText.textContent = `You are ${s}`; });
socket.on("spectator", () => {
    isSpectator = true;
    playerText.textContent = "You are a spectator";
    if(actionBtn) actionBtn.style.display = "none";
});
socket.on("state", (newState) => { gameState = newState; draw(newState); });

socket.on("gameStatus", (data) => {
    status.textContent = data.text;
    if (data.button_action) {
        actionBtn.style.display = 'inline-block';
        postGameDiv.style.display = 'none';
        switch(data.button_action) {
            case 'start': actionBtn.textContent = 'Start'; actionBtn.disabled = false; break;
            case 'waiting': actionBtn.textContent = 'Waiting...'; actionBtn.disabled = true; break;
            case 'resign': actionBtn.textContent = 'Resign'; actionBtn.disabled = false; break;
            case 'hidden': actionBtn.style.display = 'none'; break;
        }
    }
    if (data.button_rematch) {
        actionBtn.style.display = 'none';
        postGameDiv.style.display = 'flex';
        switch(data.button_rematch) {
            case 'rematch': rematchBtn.textContent = 'Rematch'; rematchBtn.disabled = false; break;
            case 'waiting': rematchBtn.textContent = 'Waiting...'; rematchBtn.disabled = true; break;
            case 'prompted': rematchBtn.textContent = 'Opponent wants a rematch!'; rematchBtn.disabled = false; break;
            case 'declined': rematchBtn.textContent = 'Opponent Left'; rematchBtn.disabled = true; break;
        }
    }
});

socket.on("rematchAgreed", () => {
    gameEnded = false;
    lastWinners = Array(9).fill(null);
    victoryModal.style.display = "none";
});

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
    myUsername = document.body.dataset.username;
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
    chatMessages.innerHTML = '';
    data.history.forEach(renderMessage);
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
chatInput.onkeydown = (e) => { if (e.key === 'Enter') { e.preventDefault(); sendChatMessage(); } };

actionBtn.onclick = () => {
    if (isSpectator) return;
    if (actionBtn.textContent === "Start") {
        socket.emit("ready", { room: ROOM });
    } else if (actionBtn.textContent === "Resign") {
        socket.emit("resign", { room: ROOM, symbol: mySymbol });
    }
};
rematchBtn.onclick = () => { socket.emit("rematch", { room: ROOM }); };
homeBtn.onclick = () => {
    if (gameEnded) {
        socket.emit("leave_post_game", { room: ROOM });
    }
    window.location.href = "/home";
};

// --- Main Draw Function ---
function draw(state) {
    boardDiv.innerHTML = "";

    if (state.gameWinner && !gameEnded) {
        showVictoryAnimation(state.gameWinner);
    }
    gameEnded = !!state.gameWinner;

    for (let b = 0; b < 9; b++) {
        const mini = document.createElement("div");
        mini.className = "mini-board";
        if (state.winners[b] && state.winners[b] !== "D") {
            if (lastWinners[b] !== state.winners[b]) playSound('win');
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

function showVictoryAnimation(winner) {
    myUsername = document.body.dataset.username;
    if (winner === "D") {
        victoryText.textContent = "Draw!";
        victorySubtext.textContent = "A hard-fought battle.";
        playSound('win');
    } else if (winner === mySymbol) {
        victoryText.textContent = "You Won!";
        victorySubtext.textContent = "Outstanding move!";
        playSound('gameWin');
    } else {
        victoryText.textContent = "You Lost";
        victorySubtext.textContent = "Better luck next time!";
        playSound('gameLose');
    }
    victoryModal.style.display = "flex";
    setTimeout(() => { victoryModal.style.display = "none"; }, 3000);
}
victoryModal.onclick = () => { victoryModal.style.display = "none"; };
