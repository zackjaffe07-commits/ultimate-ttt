const socket = io();

document.getElementById("create").onclick = () => {
    socket.emit("create");
};

socket.on("created", room => {
    window.location.href = `/game/${room}`;
});

document.getElementById("join").onclick = () => {
    const room = document.getElementById("room").value;
    if (room) {
        window.location.href = `/game/${room}`;
    }
};

socket.on('already_in_game', (data) => {
    const homeCard = document.querySelector('.home-card');
    if (!homeCard) return;

    // Find existing error div or create a new one
    let errorDiv = homeCard.querySelector('.error');
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.className = 'error';
        // Insert it after the subtitle
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
