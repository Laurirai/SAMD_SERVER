const $ = id => document.getElementById(id);

const overallChart = new Chart($("overallChart"), {
    type: "line",
    data: { datasets: [{ label: "Overall Status", data: [], parsing: false, borderWidth: 2.5, pointRadius: 0, fill: true, tension: 0.2 }] },
    options: chartOptions("Status (%)", 0, 100, true)
});
const sensorCharts = [
    createSensorChart("hrChart", "Heart Rate", "Heart Rate (BPM)", "#e05252"),
    createSensorChart("spo2Chart", "SpO₂", "SpO₂ (%)", "#24a184", 80, 100),
    createSensorChart("tempChart", "NTC Temperature", "Temperature (°C)", "#e5a13d")
];
const charts = [overallChart, ...sensorCharts];

let sessionId = null;
let received = 0;
let sensorData = [[], [], []];
let overallData = [];

function setStat(id, value, unit = "", digits = 0) {
    $(id).textContent = (value === null || value === undefined)
        ? "--" : value.toFixed(digits) + unit;
}

function updateStatus(s) {
    const st = s.device_state;
    $("stateOnline").checked = st !== "offline";
    $("stateReady").checked = st === "ready";
    $("stateSession").checked = st === "session";
    $("statePause").checked = st === "pause";
    $("stateStop").checked = st === "stop";
    $("deviceError").textContent = s.error ? `Sensor error: ${s.error}` : "";
}

const STAT_IDS = [
    "statDuration", "statHrAverage", "statHrMinimum", "statHrMaximum",
    "statSpo2Average", "statSpo2Minimum",
    "statTempAverage", "statTempMinimum", "statTempMaximum",
    "statMouthBreathing", "statNightmare", "statApnea"
];

function updateStats(stats) {
    if (!stats) {
        STAT_IDS.forEach(id => $(id).textContent = "--");
        return;
    }
    setStat("statDuration", stats.duration, " s");
    setStat("statHrAverage", stats.hr?.avg, " BPM", 1);
    setStat("statHrMinimum", stats.hr?.min, " BPM");
    setStat("statHrMaximum", stats.hr?.max, " BPM");
    setStat("statSpo2Average", stats.spo2?.avg, " %", 1);
    setStat("statSpo2Minimum", stats.spo2?.min, " %");
    setStat("statTempAverage", stats.temp?.avg, " °C", 2);
    setStat("statTempMinimum", stats.temp?.min, " °C", 2);
    setStat("statTempMaximum", stats.temp?.max, " °C", 2);
    setStat("statMouthBreathing", stats.mouth_breathing_s, " s");
    setStat("statNightmare", stats.nightmare_events);
    setStat("statApnea", stats.apnea_events);
}

async function poll() {
    try {
        let url = `/api/state?since=${received}`;
        if (sessionId !== null) url += `&session_id=${sessionId}`;

        const response = await fetch(url);
        if (!response.ok) throw new Error("Server returned " + response.status);
        const s = await response.json();

        // New session: wipe the old graphs (the server sends everything from 0)
        if (s.session_id !== sessionId) {
            sessionId = s.session_id;
            sensorData = [[], [], []];
            overallData = [];
        }

        for (const r of s.readings) {
            if (r.hr !== null) sensorData[0].push({ x: r.t, y: r.hr });
            if (r.spo2 !== null) sensorData[1].push({ x: r.t, y: r.spo2 });
            if (r.temp !== null) sensorData[2].push({ x: r.t, y: r.temp });
            if (r.score !== null && r.score !== undefined) overallData.push({ x: r.t, y: r.score });
        }
        received = s.total;

        sensorCharts.forEach((chart, i) => {
            chart.data.datasets[0].data = sensorData[i];

        });

        overallChart.data.datasets[0].data = overallData;

        const lastT = s.stats ? s.stats.duration : 0;
        const axisMax = Math.max(30, Math.ceil((lastT + 1) / 30) * 30);
        charts.forEach(chart => {
            chart.options.scales.x.max = axisMax;
            chart.update("none");
        });

        updateStatus(s);
        updateStats(s.stats);
        $("chartStatus").textContent = `Device state: ${s.device_state} — ${s.total} samples`;
    } catch (error) {
        console.error(error);
        $("chartStatus").textContent = "Lost connection to the server.";
    } finally {
        setTimeout(poll, 1000);
    }
}

async function sendCommand(command) {
    try {
        const response = await fetch(`/api/cmd/${command}`, { method: "POST" });
        if (!response.ok) throw new Error("Server returned " + response.status);
    } catch (error) {
        console.error(error);
    }
}

$("startButton").addEventListener("click", () => sendCommand("start"));
$("pauseButton").addEventListener("click", () => sendCommand("pause"));
$("continueButton").addEventListener("click", () => sendCommand("continue"));
$("finishButton").addEventListener("click", () => sendCommand("stop"));

poll();
function chartOptions(yAxisLabel, yMin = undefined, yMax = undefined, showPercent = false) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        interaction: { intersect: false, mode: "index" },
        scales: {
            x: {
                type: "linear",
                min: 0,
                max: 30,
                title: { display: true, text: "Time (seconds)" }
            },
            y: {
                min: yMin,
                max: yMax,
                title: { display: true, text: yAxisLabel },
                ticks: showPercent ? { callback: value => value + "%" } : {}
            }
        }
    };
}

function createSensorChart(canvasId, label, yAxisLabel, color, yMin = undefined, yMax = undefined) {
    return new Chart(document.getElementById(canvasId), {
        type: "line",
        data: {
            datasets: [{
                label,
                data: [],
                parsing: false,
                borderColor: color,
                borderWidth: 2,
                pointRadius: 0,
                fill: false,
                tension: 0.2
            }]
        },
        options: chartOptions(yAxisLabel, yMin, yMax)
    });
}