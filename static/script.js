/**
 * static/script.js
 * ===================
 * The actual "app" behavior for TripMate's planner card: submitting a
 * travel request to POST /api/travel, rendering the returned Markdown
 * answer, remembering the conversation's thread_id between requests, and
 * the copy/PDF-export buttons.
 *
 * This file does NOT know anything about the hero header or mega menu —
 * that's static/hero.js's job. The two are separate files on purpose, so
 * "the planner" and "the marketing hero" can each be read/changed on
 * their own. hero.js calls setPrompt() (defined below) when a traveler
 * picks a destination or quick prompt from the mega menu, which is the
 * only place the two files intentionally touch.
 */

// Remember the current conversation's thread_id in localStorage so a
// page refresh doesn't lose the ability to continue the same
// conversation (see agent/graph.py::run_travel_agent for how thread_id
// is used server-side to resume from a saved checkpoint).
let currentThreadId = localStorage.getItem("travel_thread_id") || null;

// The most recent answer's raw Markdown text, kept around so
// downloadPDF() has the original text available (the visible result box
// only contains the *rendered* HTML, not the Markdown source).
let latestAnswerMarkdown = "";

/**
 * Fill the textarea with a preset prompt. Used both by the quick-prompt
 * buttons on the planner card and by static/hero.js's menu handlers.
 */
function setPrompt(text) {
    document.getElementById("userInput").value = text;
}

/**
 * Toggle the "Generate Plan" button between its normal label and a
 * spinning loader while a request is in flight.
 */
function setLoading(isLoading) {
    const sendBtn = document.getElementById("sendBtn");
    const btnText = document.getElementById("btnText");
    const btnLoader = document.getElementById("btnLoader");

    sendBtn.disabled = isLoading;

    if (isLoading) {
        btnText.classList.add("hidden");
        btnLoader.classList.remove("hidden");
    } else {
        btnText.classList.remove("hidden");
        btnLoader.classList.add("hidden");
    }
}

function showError(message) {
    const errorBox = document.getElementById("errorBox");

    errorBox.textContent = message;
    errorBox.classList.remove("hidden");
}

function hideError() {
    const errorBox = document.getElementById("errorBox");

    errorBox.classList.add("hidden");
    errorBox.textContent = "";
}

/**
 * Render the finished travel plan into the result panel.
 *
 * @param {string} answer - Markdown text returned by POST /api/travel.
 * @param {string} threadId - The conversation id, shown to the user and
 *     also kept so the next request can continue this same conversation.
 */
function showResult(answer, threadId) {
    latestAnswerMarkdown = answer;

    const resultSection = document.getElementById("resultSection");
    const resultBox = document.getElementById("resultBox");
    const threadInfo = document.getElementById("threadInfo");

    // marked.parse() turns the agent's Markdown answer (see
    // agent/prompts.py, which explicitly instructs the LLM to reply in
    // Markdown for exactly this reason) into HTML. If the marked library
    // failed to load for some reason, fall back to plain text so the
    // answer is still readable, just unformatted.
    if (typeof marked !== "undefined") {
        resultBox.innerHTML = marked.parse(answer);
    } else {
        resultBox.innerText = answer;
    }

    threadInfo.textContent = `Thread ID: ${threadId}`;

    resultSection.classList.remove("hidden");

    resultSection.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}

/**
 * Submit the traveler's message to the backend and render the response.
 * Bound to the "Generate Plan" button's onclick in templates/index.html.
 */
async function sendMessage() {
    hideError();

    const input = document.getElementById("userInput");
    const message = input.value.trim();

    if (!message) {
        showError("Please enter your travel request first.");
        return;
    }

    setLoading(true);

    try {
        const response = await fetch("/api/travel", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: message,
                thread_id: currentThreadId
            })
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.error || "Something went wrong.");
        }

        currentThreadId = data.thread_id;
        localStorage.setItem("travel_thread_id", currentThreadId);

        showResult(data.answer, data.thread_id);

    } catch (error) {
        showError(error.message);
    } finally {
        setLoading(false);
    }
}

/**
 * Copy the rendered (plain-text) result to the clipboard, with a brief
 * "Copied!" confirmation on the button itself.
 */
function copyResult() {
    const resultBox = document.getElementById("resultBox");
    const text = resultBox.innerText;

    if (!text) {
        return;
    }

    navigator.clipboard.writeText(text)
        .then(() => {
            const copyBtn = document.querySelector(".copy-btn");
            const oldText = copyBtn.textContent;

            copyBtn.textContent = "Copied!";

            setTimeout(() => {
                copyBtn.textContent = oldText;
            }, 1400);
        })
        .catch(() => {
            showError("Could not copy result.");
        });
}

/**
 * Export the result panel as a downloadable PDF using html2pdf.js.
 * Renders #pdfContent specifically (not the whole page), which is why
 * that element has its own white-background styling in style.css — it
 * needs to look right standalone, not just inside the dark app theme.
 */
function downloadPDF() {
    const pdfContent = document.getElementById("pdfContent");

    if (!latestAnswerMarkdown || !pdfContent) {
        showError("No travel plan available to download.");
        return;
    }

    const downloadBtn = document.querySelector(".download-btn");
    const oldText = downloadBtn.textContent;

    downloadBtn.textContent = "Preparing PDF...";
    downloadBtn.disabled = true;

    const options = {
        margin: 0.5,
        filename: "ai-travel-plan.pdf",
        image: {
            type: "jpeg",
            quality: 0.98
        },
        html2canvas: {
            scale: 2,
            useCORS: true,
            backgroundColor: "#ffffff"
        },
        jsPDF: {
            unit: "in",
            format: "a4",
            orientation: "portrait"
        },
        pagebreak: {
            mode: ["avoid-all", "css", "legacy"]
        }
    };

    html2pdf()
        .set(options)
        .from(pdfContent)
        .save()
        .then(() => {
            downloadBtn.textContent = oldText;
            downloadBtn.disabled = false;
        })
        .catch(() => {
            downloadBtn.textContent = oldText;
            downloadBtn.disabled = false;
            showError("Could not download PDF.");
        });
}

// Keyboard shortcut: Ctrl+Enter submits the form from inside the textarea,
// so travelers don't have to reach for the mouse.
document.addEventListener("keydown", function(event) {
    if (event.ctrlKey && event.key === "Enter") {
        sendMessage();
    }
});
