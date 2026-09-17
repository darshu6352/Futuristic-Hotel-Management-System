document.addEventListener("DOMContentLoaded", function () {

    let toggle = document.getElementById("modeToggle");

    // saved mode
    if (localStorage.getItem("mode") === "dark") {
        document.body.classList.add("dark-mode");
        toggle.checked = true;
    }

    toggle.addEventListener("change", function () {

        if (this.checked) {
            document.body.classList.add("dark-mode");
            document.body.classList.remove("light-mode");
            localStorage.setItem("mode", "dark");
        } else {
            document.body.classList.add("light-mode");
            document.body.classList.remove("dark-mode");
            localStorage.setItem("mode", "light");
        }

    });

});