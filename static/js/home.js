const socket = io();

document.getElementById("create").onclick = () => {
    socket.emit("create");
};

socket.on("created", room => {
    window.location = `/game/${room}`;
});

document.getElementById("join").onclick = () => {
    const room = document.getElementById("room").value;
    if (room) window.location = `/game/${room}`;
};
