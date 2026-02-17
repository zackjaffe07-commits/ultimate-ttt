const socket = io();

document.getElementById("create").onclick = () => {
    socket.emit("create");
};

socket.on("created", room => {
    window.location = `/game/${room}`;
});

document.getElementById("join").onclick = () => {
    const room = document.getElementById("room").value;
    if (room) {
        // We don't know if the user is in a game yet, so we just navigate.
        // The server will handle the error if they try to join.
        // A better implementation might check with the server first.
        window.location = `/game/${room}`;
    }
};

socket.on('already_in_game', (data) => {
    // Find the error display area on the home page and show the message
    const errorDiv = document.querySelector('.home-card .error');
    if (errorDiv) {
        errorDiv.textContent = data.error;
        errorDiv.style.display = 'block';
    } else {
        // Fallback if the error div doesn't exist for some reason
        alert(data.error);
    }
});
