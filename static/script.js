let timerInterval = null;

let totalSeconds = 25 * 60;

let remainingSeconds = totalSeconds;


function updateTimerDisplay() {

    let minutes = Math.floor(
        remainingSeconds / 60
    );

    let seconds = remainingSeconds % 60;


    minutes = String(minutes).padStart(2, "0");

    seconds = String(seconds).padStart(2, "0");


    const timer = document.getElementById("timer");


    if (timer) {

        timer.textContent =
            minutes + ":" + seconds;

    }

}


function startTimer() {

    if (timerInterval !== null) {
        return;
    }


    timerInterval = setInterval(function () {

        if (remainingSeconds > 0) {

            remainingSeconds--;

            updateTimerDisplay();

        }

        else {

            clearInterval(timerInterval);

            timerInterval = null;

            alert(
                "🎉 Study session completed!"
            );

        }

    }, 1000);

}


function pauseTimer() {

    if (timerInterval !== null) {

        clearInterval(timerInterval);

        timerInterval = null;

    }

}


function resetTimer() {

    clearInterval(timerInterval);

    timerInterval = null;

    remainingSeconds = totalSeconds;

    updateTimerDisplay();

}


document.addEventListener(
    "DOMContentLoaded",
    function () {

        updateTimerDisplay();

    }
);