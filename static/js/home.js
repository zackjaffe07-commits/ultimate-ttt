const socket = io();

const createBtn = document.getElementById("create");
const joinBtn = document.getElementById("join");
const roomInput = document.getElementById("room");

createBtn.onclick = () => {
    socket.emit("create");
};

socket.on("created", room => {
    window.location.href = `/game/${room}`;
});

function joinGame() {
    const room = roomInput.value;
    if (room) {
        window.location.href = `/game/${room}`;
    }
}

joinBtn.onclick = joinGame;

roomInput.onkeydown = (e) => {
    if (e.key === 'Enter') {
        joinGame();
    }
};

socket.on('already_in_game', (data) => {
    const homeCard = document.querySelector('.home-card');
    if (!homeCard) return;

    let errorDiv = homeCard.querySelector('.error');
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.className = 'error';
        const subtitle = homeCard.querySelector('.subtitle');
        if (subtitle) {
            subtitle.insertAdjacentElement('afterend', errorDiv);
        } else {
            homeCard.prepend(errorDiv);
        }
    }

    errorDiv.textContent = data.error;
    errorDiv.style.display = 'block';
});
